"""Prova dei post finti: il motore vede effetti che non esistono?

Si prendono gli ordini giornalieri veri di un negozio, si inventano creator con
date di post a caso e si stima il loro effetto. Siccome i post non sono mai
esistiti, l'effetto vero e' zero:
  - il creator dovrebbe risultare con un effetto chiaro (probabilita' >= 95%)
    circa il 5% delle volte;
  - l'intervallo probabile al 90% dovrebbe contenere lo zero circa il 90%
    delle volte.
Se succede molto piu' spesso, sui dati veri gli intervalli sono troppo stretti.

Il metodo di stima e' quello di creatorlift.model, senza modifiche.

Uso:
    python -m creatorlift.placebo dati_simulati/ordini_giornalieri.csv
"""
from __future__ import annotations

import argparse
import warnings
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from creatorlift.model import estimate

MARGIN_START = 7    # nessun post finto nei primi giorni
MARGIN_END = 14     # ne' negli ultimi 14, dove l'effetto non si vedrebbe tutto


def fake_posts(daily: pd.DataFrame, rng: np.random.Generator, n_creators: int = 6,
               posts_per_creator=(1, 3)) -> pd.DataFrame:
    """Creator inventati con date di post a caso tra i giorni del negozio."""
    days = daily["date"].to_numpy()[MARGIN_START:len(daily) - MARGIN_END]
    rows = []
    for k in range(n_creators):
        n = int(rng.integers(posts_per_creator[0], posts_per_creator[1] + 1))
        for d in rng.choice(days, size=n, replace=False):
            rows.append({"creator": f"finto_{k + 1}", "date": d, "cost_eur": 100.0})
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def thin(daily: pd.DataFrame, orders_per_day: float, rng: np.random.Generator) -> pd.DataFrame:
    """Negozio piu' piccolo con lo stesso andamento: ogni ordine resta con
    probabilita' costante (si conservano stagionalita' e rumore veri)."""
    p = min(1.0, orders_per_day / daily["orders"].mean())
    return daily.assign(orders=rng.binomial(daily["orders"].to_numpy(), p))


def _one(args):
    daily, real_posts, rep, n_creators, posts_per_creator, seed, widen = args
    rng = np.random.default_rng([seed, rep])
    fake = fake_posts(daily, rng, n_creators, posts_per_creator)
    posts = fake if real_posts is None else pd.concat([real_posts[["creator", "date", "cost_eur"]], fake])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est, _ = estimate(daily, posts, seed=seed * 100_000 + rep, widen=widen)
    est = est[est["creator"].isin(set(fake["creator"]))].copy()
    est["rep"] = rep
    return est


def placebo(daily: pd.DataFrame, n_rep: int = 100, n_creators: int = 6, posts_per_creator=(1, 3),
            seed: int = 0, workers: int | None = None, posts: pd.DataFrame | None = None,
            widen: float = 1.0) -> pd.DataFrame:
    """Una riga per creator finto, con la stima e due colonne:
    falso_positivo (effetto 'chiaro' che non esiste) e zero_dentro
    (l'intervallo contiene lo zero). `posts`: i post veri del negozio, che
    restano nel modello insieme a quelli finti (cosi' il loro effetto non
    finisce nel rumore); si valutano solo i creator finti."""
    daily = daily.reset_index(drop=True)
    if "promo" not in daily:
        daily = daily.assign(promo=0)
    jobs = [(daily, posts, r, n_creators, posts_per_creator, seed, widen) for r in range(n_rep)]
    if workers == 1:
        parts = [_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(workers) as ex:
            parts = list(ex.map(_one, jobs))
    out = pd.concat(parts, ignore_index=True)
    out["falso_positivo"] = out["prob_effect_positive"] >= 0.95
    out["zero_dentro"] = (out["low_90"] <= 0) & (out["high_90"] >= 0)
    return out


def inflation_factor(res: pd.DataFrame) -> float:
    """Di quanto andrebbero allargati gli intervalli perche' sui post finti
    l'errore standardizzato abbia deviazione standard 1."""
    r = res.dropna(subset=["low_90", "high_90"])
    se = (r["high_90"] - r["low_90"]) / (2 * 1.645)
    return float((r["incremental_orders"] / se).std())


def summary(res: pd.DataFrame) -> dict:
    """Quota di falsi positivi e di intervalli che contengono lo zero, con un
    intervallo al 95% dovuto al numero finito di prove."""
    valid = res.dropna(subset=["low_90", "high_90"])
    n = len(valid)
    fp = float(valid["falso_positivo"].mean())
    cov = float(valid["zero_dentro"].mean())
    se = lambda p: 1.96 * np.sqrt(p * (1 - p) / n)  # noqa: E731
    return {"creator_finti": n, "non_stimabili": len(res) - n,
            "falsi_positivi": fp, "falsi_positivi_margine": se(fp),
            "zero_nell_intervallo": cov, "zero_nell_intervallo_margine": se(cov),
            "fattore": inflation_factor(res)}


CALIBRATION_REPS = 50


def calibrate(daily: pd.DataFrame, posts: pd.DataFrame, n_rep: int = CALIBRATION_REPS, seed: int = 0,
              workers: int | None = 1, progress=None) -> dict:
    """Taratura dell'incertezza sul negozio: prova dei post finti con i post
    veri nel modello. Il fattore si usa solo per allargare (minimo 1): la sua
    stima su un solo negozio oscilla, e sotto 1 il motore e' gia' prudente."""
    if progress is None:
        res = placebo(daily, n_rep=n_rep, seed=seed, workers=workers, posts=posts)
    else:  # una prova alla volta, per mostrare l'avanzamento
        parts = []
        for k in range(n_rep):
            parts.append(placebo_one(daily, posts, k, seed))
            progress((k + 1) / n_rep)
        res = pd.concat(parts, ignore_index=True)
        res["falso_positivo"] = res["prob_effect_positive"] >= 0.95
        res["zero_dentro"] = (res["low_90"] <= 0) & (res["high_90"] >= 0)
    s = summary(res)
    s["fattore_usato"] = max(1.0, s["fattore"])
    return s


def placebo_one(daily, posts, rep, seed=0, n_creators=6, posts_per_creator=(1, 3)):
    daily = daily.reset_index(drop=True)
    if "promo" not in daily:
        daily = daily.assign(promo=0)
    return _one((daily, posts, rep, n_creators, posts_per_creator, seed, 1.0))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="tabella giornaliera con colonne date, orders (e facoltativa promo)")
    ap.add_argument("--prove", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    daily = pd.read_csv(a.csv)
    s = summary(placebo(daily, n_rep=a.prove, seed=a.seed))
    print(f"{s['creator_finti']} creator finti: effetto 'chiaro' nel {s['falsi_positivi']:.1%} "
          f"(± {s['falsi_positivi_margine']:.1%}, atteso 5%); zero nell'intervallo nel "
          f"{s['zero_nell_intervallo']:.1%} (atteso 90%)")


if __name__ == "__main__":
    main()
