"""Motore di stima: quante vendite in piu' ha portato ogni creator.

Idea: si modellano gli ordini giornalieri come conseguenza di
  - andamento di fondo (trend), giorno della settimana, stagionalita' annuale
  - giorni di promozione
  - un "effetto post" per ogni creator, che parte il giorno del post e si
    spegne nei giorni successivi (decadimento con meta' vita)
Il modello (regressione di Poisson con sovradispersione) stima l'effetto di
ogni creator. Le vendite in piu' sono la differenza tra gli ordini previsti
con e senza i post di quel creator. L'incertezza si ottiene ripetendo il
calcolo con 2.000 estrazioni dei coefficienti dalla loro distribuzione.

Uso:
    python estimate.py dati_simulati
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HALF_LIFE_GRID = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
N_DRAWS = 2000


def adstock(n_days: int, post_days, half_life: float) -> np.ndarray:
    t = np.arange(n_days)
    x = np.zeros(n_days)
    for p in post_days:
        x += np.where(t >= p, 0.5 ** ((t - p) / half_life), 0.0)
    return x


def base_design(daily: pd.DataFrame) -> pd.DataFrame:
    n = len(daily)
    t = np.arange(n)
    d = pd.to_datetime(daily["date"])
    X = pd.DataFrame({"const": 1.0, "trend": t / n}, index=daily.index)
    dow = pd.get_dummies(d.dt.dayofweek, prefix="dow", drop_first=True).astype(float)
    X = pd.concat([X, dow.set_index(daily.index)], axis=1)
    for k in (1, 2):
        X[f"sin{k}"] = np.sin(2 * np.pi * k * t / 365.25)
        X[f"cos{k}"] = np.cos(2 * np.pi * k * t / 365.25)
    X["promo"] = daily["promo"].astype(float)
    return X


WINDOWS = [(0, 0), (1, 2), (3, 6), (7, 13)]  # giorno del post, 1-2, 3-6 e 7-13 giorni dopo


def windows(n_days: int, post_days):
    t = np.arange(n_days)
    cols = []
    for a, b in WINDOWS:
        x = np.zeros(n_days)
        for p in post_days:
            x += ((t - p >= a) & (t - p <= b)).astype(float)
        cols.append(x)
    return cols


def fit(daily: pd.DataFrame, posts: pd.DataFrame, half_life):
    """half_life=None: effetto libero per finestre di giorni (ogni creator ha
    la sua forma); altrimenti decadimento con meta' vita comune."""
    n = len(daily)
    day_index = {d: i for i, d in enumerate(daily["date"])}
    X = base_design(daily)
    creators = sorted(posts["creator"].unique())
    for c in creators:
        days = [day_index[d] for d in posts.loc[posts.creator == c, "date"]]
        if half_life is None:
            for (a, b), x in zip(WINDOWS, windows(n, days)):
                X[f"cr_{c}__{a}_{b}"] = x
        else:
            X[f"cr_{c}__hl"] = adstock(n, days, half_life)
    model = sm.GLM(daily["orders"].astype(float), X, family=sm.families.Poisson())
    res = model.fit(scale="X2")  # quasi-Poisson: tiene conto della sovradispersione
    return res, X, creators


def estimate(daily: pd.DataFrame, posts: pd.DataFrame, seed: int = 0, aov=None, margin=None, mode="windows"):
    if mode == "windows":
        res, X, creators = fit(daily, posts, None)
        hl = "finestre 0 / 1-2 / 3-6 / 7-13 giorni"
    else:
        # sceglie la meta' vita comune che spiega meglio i dati (devianza minima)
        best = None
        for h in HALF_LIFE_GRID:
            r, Xh, cr = fit(daily, posts, h)
            if best is None or r.deviance < best[0].deviance:
                best = (r, Xh, cr, h)
        res, X, creators, hl = best

    rng = np.random.default_rng(seed)
    beta = res.params.values
    cov = res.cov_params().values
    draws = rng.multivariate_normal(beta, cov, size=N_DRAWS)
    Xv = X.values
    cols = list(X.columns)
    rows = []
    for c in creators:
        js = [i for i, col in enumerate(cols) if col.startswith(f"cr_{c}__")]
        X0 = Xv.copy()
        X0[:, js] = 0.0
        # vendite in piu' = previsione con il creator - previsione senza
        incr = (np.exp(Xv @ draws.T) - np.exp(X0 @ draws.T)).sum(axis=0)
        point = float((np.exp(Xv @ beta) - np.exp(X0 @ beta)).sum())
        lo, hi = np.percentile(incr, [5, 95])
        p_positive = float((incr > 0).mean())
        rows.append({
            "creator": c,
            "incremental_orders": round(point, 1),
            "low_90": round(float(lo), 1),
            "high_90": round(float(hi), 1),
            "prob_effect_positive": round(p_positive, 3),
        })
    out = pd.DataFrame(rows)
    if aov is not None and margin is not None:
        cost = posts.groupby("creator")["cost_eur"].sum()
        out["cost_eur"] = out["creator"].map(cost).round(0)
        for col in ("incremental_orders", "low_90", "high_90"):
            out[col.replace("incremental_orders", "roi").replace("low_90", "roi_low").replace("high_90", "roi_high")] = (
                out[col] * aov * margin / out["cost_eur"]
            ).round(2)
    return out, hl


def verdict(row) -> str:
    if row["prob_effect_positive"] < 0.95:
        return "nessun effetto chiaro"
    if "roi_low" in row and row["roi_low"] >= 1:
        return "si ripaga quasi certamente"
    if "roi" in row and row["roi"] >= 1:
        return "probabilmente si ripaga"
    return "porta vendite ma non si ripaga"


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "dati_simulati")
    daily = pd.read_csv(folder / "ordini_giornalieri.csv")
    posts = pd.read_csv(folder / "post_creator.csv")
    aov = (daily["revenue_eur"].sum() / daily["orders"].sum())
    margin = 0.55
    out, hl = estimate(daily, posts, aov=aov, margin=margin)
    out["giudizio"] = out.apply(verdict, axis=1)
    codes = {c: int(daily[f"code_{c}"].sum()) for c in out["creator"] if f"code_{c}" in daily}
    out.insert(1, "orders_with_code", out["creator"].map(codes))
    print(f"Forma dell'effetto: {hl}; scontrino medio {aov:.2f} EUR")
    print(out.to_string(index=False))
    out.to_csv(folder / "stima.csv", index=False)


if __name__ == "__main__":
    main()
