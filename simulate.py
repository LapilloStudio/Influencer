"""Simula un anno di ordini di un negozio online con collaborazioni creator.

Ogni creator ha un effetto VERO noto (vendite in piu' dopo il post), cosi'
si puo' controllare se il motore di stima lo ritrova.

Uso:
    python simulate.py --orders-per-day 20 --seed 1 --out dati_simulati
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Creator, date dei post (giorno dell'anno, 0 = 1 gennaio), effetto vero sul
# giorno del post (+40% = 0.40 ordini in piu' rispetto al normale), meta' vita
# dell'effetto in giorni, costo della collaborazione in euro.
CREATORS = [
    {"creator": "giulia_style", "posts": [40, 160, 290], "lift": 0.60, "half_life": 2.0, "cost": 600},
    {"creator": "marco_daily", "posts": [75, 215], "lift": 0.25, "half_life": 1.5, "cost": 400},
    {"creator": "sara_mom", "posts": [110, 250], "lift": 0.40, "half_life": 3.0, "cost": 500},
    {"creator": "luca_tech", "posts": [130, 305], "lift": 0.00, "half_life": 2.0, "cost": 450},
    {"creator": "elena_fit", "posts": [190], "lift": 0.90, "half_life": 1.0, "cost": 900},
    {"creator": "fede_vlog", "posts": [60, 230, 335], "lift": 0.10, "half_life": 2.0, "cost": 250},
]
PROMO_DAYS = list(range(3, 10)) + list(range(180, 187)) + list(range(326, 333))  # saldi e Black Friday
CODE_SHARE_OF_INCREMENTAL = 0.35   # quota degli ordini "portati" dal creator che usa il codice
CODE_LEAK_RATE = 0.01              # ordini normali che usano il codice trovato su siti di coupon
AOV_MEAN = 45.0                    # scontrino medio in euro
GROSS_MARGIN = 0.55                # margine lordo sul venduto


def decay_curve(days_since: np.ndarray, half_life: float) -> np.ndarray:
    out = np.where(days_since >= 0, 0.5 ** (days_since / half_life), 0.0)
    return out


def simulate(orders_per_day: float, seed: int, n_days: int = 365):
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")

    trend = 1 + 0.25 * t / n_days
    weekly = np.array([0.95, 0.92, 0.95, 1.0, 1.05, 1.12, 1.01])[dates.dayofweek]
    yearly = 1 + 0.15 * np.sin(2 * np.pi * (t - 80) / 365)
    promo = np.isin(t, PROMO_DAYS).astype(float)
    base = orders_per_day * trend * weekly * yearly * (1 + 0.5 * promo)
    base = base * np.exp(rng.normal(0, 0.08, n_days))  # rumore giornaliero non spiegato

    creator_multiplier = np.zeros(n_days)
    per_creator_expected = {}
    for c in CREATORS:
        curve = np.zeros(n_days)
        for p in c["posts"]:
            curve += decay_curve(t - p, c["half_life"])
        creator_multiplier += c["lift"] * curve
        per_creator_expected[c["creator"]] = base * c["lift"] * curve

    lam = base * (1 + creator_multiplier)
    orders = rng.poisson(lam)

    # Ordini con codice: una parte degli incrementali + un po' di "fuga" dei codici
    incremental_expected = lam - base
    share_incr = np.divide(incremental_expected, lam, out=np.zeros(n_days), where=lam > 0)
    incr_orders = rng.binomial(orders, np.clip(share_incr, 0, 1))
    organic_orders = orders - incr_orders
    code_orders_by_creator = {c["creator"]: np.zeros(n_days, dtype=int) for c in CREATORS}
    for day in range(n_days):
        if incr_orders[day] > 0 and incremental_expected[day] > 0:
            weights = np.array([per_creator_expected[c["creator"]][day] for c in CREATORS])
            weights = weights / weights.sum()
            split = rng.multinomial(incr_orders[day], weights)
            for c, k in zip(CREATORS, split):
                code_orders_by_creator[c["creator"]][day] += rng.binomial(k, CODE_SHARE_OF_INCREMENTAL)
        # codici trapelati: assegnati ai creator con post nell'anno, a caso
        leaks = rng.binomial(organic_orders[day], CODE_LEAK_RATE)
        if leaks:
            who = rng.integers(0, len(CREATORS), leaks)
            for i in who:
                code_orders_by_creator[CREATORS[i]["creator"]][day] += 1

    revenue = np.array([rng.gamma(4.0, AOV_MEAN / 4.0, n).sum() if n else 0.0 for n in orders])

    daily = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "orders": orders,
        "revenue_eur": revenue.round(2),
        "promo": promo.astype(int),
    })
    for c in CREATORS:
        daily[f"code_{c['creator']}"] = code_orders_by_creator[c["creator"]]

    posts = pd.DataFrame([
        {"creator": c["creator"], "date": dates[p].strftime("%Y-%m-%d"), "cost_eur": c["cost"] / len(c["posts"])}
        for c in CREATORS for p in c["posts"]
    ]).sort_values("date")

    truth = []
    for c in CREATORS:
        exp_incr = per_creator_expected[c["creator"]].sum()
        truth.append({
            "creator": c["creator"],
            "true_incremental_orders": round(float(exp_incr), 1),
            "orders_with_code": int(code_orders_by_creator[c["creator"]].sum()),
            "cost_eur": c["cost"],
        })
    return daily, posts, pd.DataFrame(truth)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders-per-day", type=float, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="dati_simulati")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    daily, posts, truth = simulate(a.orders_per_day, a.seed)
    daily.to_csv(out / "ordini_giornalieri.csv", index=False)
    posts.to_csv(out / "post_creator.csv", index=False)
    truth.to_csv(out / "verita_nascosta.csv", index=False)
    meta = {"orders_per_day": a.orders_per_day, "seed": a.seed, "aov_eur": AOV_MEAN, "gross_margin": GROSS_MARGIN}
    (out / "parametri.json").write_text(json.dumps(meta, indent=1))
    print(truth.to_string(index=False))


if __name__ == "__main__":
    main()
