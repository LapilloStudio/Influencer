"""Test del motore: su molti negozi simulati, il motore ritrova l'effetto vero?

Per ogni dimensione di negozio (ordini al giorno) simula N negozi con seed
diversi, stima e confronta con la verita' nascosta. Riporta:
  - copertura: % di volte in cui l'effetto vero cade nell'intervallo al 90%
    (dovrebbe essere circa 90%)
  - errore medio della stima puntuale
  - falsi positivi: per il creator senza effetto, % di volte che il motore
    dice "si ripaga"
  - con il solo codice sconto: quanto si sbaglia contando gli ordini con codice
"""
import sys

import numpy as np
import pandas as pd

from estimate import estimate, verdict
from simulate import CREATORS, simulate

SIZES = [5, 20, 80]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60

rows = []
for size in SIZES:
    for seed in range(N):
        daily, posts, truth = simulate(size, seed)
        aov = daily["revenue_eur"].sum() / daily["orders"].sum()
        est, _ = estimate(daily, posts, seed=seed, aov=aov, margin=0.55)
        m = est.merge(truth, on="creator")
        m["size"] = size
        m["seed"] = seed
        m["giudizio"] = m.apply(verdict, axis=1)
        rows.append(m)
df = pd.concat(rows)
df["covered"] = (df.true_incremental_orders >= df.low_90) & (df.true_incremental_orders <= df.high_90)
df["abs_err"] = (df.incremental_orders - df.true_incremental_orders).abs()
df["code_abs_err"] = (df.orders_with_code - df.true_incremental_orders).abs()
df["detected"] = df.prob_effect_positive >= 0.95

summary = df.groupby(["size", "creator"]).agg(
    vero=("true_incremental_orders", "mean"),
    stima=("incremental_orders", "mean"),
    con_codice=("orders_with_code", "mean"),
    copertura_90=("covered", "mean"),
    err_medio=("abs_err", "mean"),
    err_codice=("code_abs_err", "mean"),
    rilevato=("detected", "mean"),
).round(2)
print(summary.to_string())

overall = df.groupby("size").agg(copertura_90=("covered", "mean"), err_medio=("abs_err", "mean"), err_codice=("code_abs_err", "mean")).round(3)
print("\nRiepilogo per dimensione del negozio")
print(overall.to_string())

fp = df[df.creator == "luca_tech"].groupby("size")["giudizio"].apply(lambda s: (s != "nessun effetto chiaro").mean()).round(3)
print("\nFalsi positivi (creator senza effetto giudicato utile)")
print(fp.to_string())
df.to_csv("risultati_test.csv", index=False)
summary.to_csv("riepilogo_test.csv")
