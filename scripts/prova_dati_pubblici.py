"""Prova dei post finti su ordini reali pubblici ("Online Retail", UCI,
licenza CC BY 4.0): un negozio online britannico, dicembre 2010 - dicembre 2011.

Il file non e' nel repository (45 MB). Si scarica da una copia pubblica:
    https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/master/data/retail-data/all/online-retail-dataset.csv

Uso:
    python scripts/prova_dati_pubblici.py percorso/online-retail-dataset.csv [--prove 100]

Il negozio e' chiuso il sabato e nei festivi: il modello non puo' stimare un
giorno della settimana sempre a zero, quindi si tengono solo i giorni di
apertura. Si prova il negozio vero (circa 65 ordini al giorno) e due versioni
piu' piccole con lo stesso andamento (20 e 10 ordini al giorno).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creatorlift.placebo import placebo, summary, thin  # noqa: E402


def load_online_retail(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"InvoiceNo": str}, encoding="latin-1")
    df = df[~df["InvoiceNo"].str.startswith("C") & (df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
    day = pd.to_datetime(df["InvoiceDate"], format="%m/%d/%Y %H:%M").dt.strftime("%Y-%m-%d")
    daily = df.groupby(day)["InvoiceNo"].nunique().rename("orders").rename_axis("date").reset_index()
    return daily.assign(promo=0)  # solo i giorni con ordini (negozio aperto)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--prove", type=int, default=100)
    a = ap.parse_args()
    real = load_online_retail(a.csv)
    print(f"Negozio reale: {len(real)} giorni di apertura, {real.orders.mean():.1f} ordini al giorno in media\n")
    rows = []
    for label, d in [("vero", real),
                     ("20/giorno", thin(real, 20, np.random.default_rng(1))),
                     ("10/giorno", thin(real, 10, np.random.default_rng(2)))]:
        s = summary(placebo(d, n_rep=a.prove, seed=7))
        rows.append({"negozio": label, "ordini al giorno": round(d.orders.mean(), 1), **s})
        print(f"{label:>10}: effetto 'chiaro' {s['falsi_positivi']:.1%} ± {s['falsi_positivi_margine']:.1%} "
              f"(atteso 5%), zero nell'intervallo {s['zero_nell_intervallo']:.1%} (atteso 90%), "
              f"{s['creator_finti']} creator finti")
    pd.DataFrame(rows).to_csv("prova_post_finti_risultati.csv", index=False)


if __name__ == "__main__":
    main()
