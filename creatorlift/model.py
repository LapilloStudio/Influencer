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

Il metodo e' quello del prototipo (estimate.py) senza modifiche. Rispetto al
prototipo, il calcolo e' diviso in due: `fit_and_draw` stima il modello ed
estrae i coefficienti, `estimate` riassume per creator. Cosi' `daily_paths`
puo' riusare la stessa stima e le stesse estrazioni per i grafici giorno per
giorno.

Uso:
    python -m creatorlift.model dati_simulati
"""
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HALF_LIFE_GRID = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
N_DRAWS = 2000
LAM_MAX = 1e15  # sotto il limite di numpy per la Poisson (~9.2e18)


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
    # senza nessun giorno di promozione la colonna sarebbe tutta a zero: non
    # aggiunge nulla alla stima e renderebbe il modello singolare
    if daily["promo"].astype(bool).any():
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


@dataclass
class Fit:
    """Stima del modello e 2.000 estrazioni dei coefficienti."""
    res: object
    X: pd.DataFrame
    creators: list
    shape: object  # descrizione della forma dell'effetto (finestre o meta' vita)
    draws: np.ndarray  # N_DRAWS x n_coefficienti
    dates: pd.Series
    orders: np.ndarray

    def creator_columns(self, creator):
        # nomi esatti delle colonne: un confronto per prefisso confonderebbe
        # "giulia" con "giulia_" o "giulia__style"
        if creator not in self.creators:
            raise KeyError(f"creator {creator!r} non presente nella stima; creator disponibili: {self.creators}")
        names = {f"cr_{creator}__{a}_{b}" for a, b in WINDOWS} | {f"cr_{creator}__hl"}
        return [i for i, col in enumerate(self.X.columns) if col in names]

    def without(self, creator) -> np.ndarray:
        """Matrice del modello con i post del creator azzerati."""
        X0 = self.X.values.copy()
        X0[:, self.creator_columns(creator)] = 0.0
        return X0


def fit_and_draw(daily: pd.DataFrame, posts: pd.DataFrame, seed: int = 0, mode="windows", widen: float = 1.0) -> Fit:
    """`widen` > 1 allarga l'incertezza dei coefficienti di quel fattore (taratura
    con i post finti, vedi creatorlift.placebo): le stime puntuali non cambiano."""
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
    if widen != 1.0:
        draws = beta + widen * (draws - beta)
    return Fit(res, X, creators, hl, draws, daily["date"].reset_index(drop=True),
               daily["orders"].to_numpy())


def estimate(daily: pd.DataFrame, posts: pd.DataFrame, seed: int = 0, aov=None, margin=None, mode="windows",
             return_fit=False, widen: float = 1.0):
    f = fit_and_draw(daily, posts, seed=seed, mode=mode, widen=widen)
    res, X, creators, hl, draws = f.res, f.X, f.creators, f.shape, f.draws
    beta = res.params.values
    Xv = X.values
    rows = []
    for c in creators:
        X0 = f.without(c)
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
    if return_fit:
        return out, hl, f
    return out, hl


def daily_paths(f: Fit, creator: str, seed: int = 0) -> pd.DataFrame:
    """Previsioni giorno per giorno per i grafici, dalla stessa stima di `estimate`.

    Colonne:
      orders           ordini reali
      with_creator     previsione del modello con tutti i post
      without_creator  previsione se i post di questo creator non ci fossero stati
      without_lo/hi    intervallo al 90% della previsione senza il creator
                       (solo incertezza sui coefficienti, come nella tabella)
      normal_lo/hi     intervallo al 90% degli ordini di un giorno qualsiasi
                       senza il creator: aggiunge la variabilita' giornaliera
                       (sovradispersione stimata dal modello). E' la fascia
                       con cui ha senso confrontare i singoli giorni reali.
                       Gli ordini sono numeri interi, quindi con pochi ordini
                       al giorno la fascia contiene un po' piu' del 90% dei
                       giorni normali (circa 95% a 5 ordini/giorno).
      incremental      with_creator - without_creator (sommato su tutti i
                       giorni da' la stima puntuale di `estimate`)

    Le fasce sono NaN nei giorni in cui non sono definite: succede quando una
    finestra di qualche creator cade solo su giorni con zero ordini, e il suo
    coefficiente non si puo' stimare (in quel caso anche `estimate` restituisce
    un intervallo NaN per i creator coinvolti).
    """
    beta = f.res.params.values
    Xv = f.X.values
    X0 = f.without(creator)
    with np.errstate(over="ignore", invalid="ignore"):
        mu0_draws = np.exp(X0 @ f.draws.T)  # giorni x estrazioni
        with_c = np.exp(Xv @ beta)
        without_c = np.exp(X0 @ beta)
        lo, hi = np.percentile(mu0_draws, [5, 95], axis=1)

        # ordini simulati con varianza = scale * media (quasi-Poisson), tramite
        # gamma-Poisson; con scale <= 1 si usa la Poisson semplice
        rng = np.random.default_rng(seed + 1)
        phi = float(f.res.scale)
        if phi > 1:
            k = phi - 1.0
            lam = rng.gamma(shape=mu0_draws / k, scale=k)
        else:
            lam = mu0_draws
        # estrazioni esplose (coefficiente non stimabile): restano infinite
        # invece di far fallire rng.poisson; con lam = 0 non si consumano
        # numeri casuali, quindi sui dati normali il risultato non cambia
        bad = ~(lam <= LAM_MAX)
        sim = rng.poisson(np.where(bad, 0.0, lam)).astype(float)
        sim[bad] = np.inf
        nlo, nhi = np.percentile(sim, [5, 95], axis=1)
    undefined = ~(np.isfinite(hi) & np.isfinite(nhi))
    for a in (lo, hi, nlo, nhi):
        a[undefined] = np.nan

    return pd.DataFrame({
        "date": pd.to_datetime(f.dates).to_numpy(),
        "orders": f.orders,
        "with_creator": with_c,
        "without_creator": without_c,
        "without_lo": lo,
        "without_hi": hi,
        "normal_lo": nlo,
        "normal_hi": nhi,
        "incremental": with_c - without_c,
    })


def verdict(row) -> str:
    if row["prob_effect_positive"] < 0.95:
        return "nessun effetto chiaro"
    if "roi_low" in row and row["roi_low"] >= 1:
        return "si ripaga quasi certamente"
    if "roi" in row and row["roi"] >= 1:
        return "probabilmente si ripaga"
    return "porta vendite ma non si ripaga"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    folder = Path(argv[0] if argv else "dati_simulati")
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
