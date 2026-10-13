"""Verifica della taratura sul negozio reale pubblico: si misura il fattore con
`calibrate` (come fa l'app), poi si rifa' la prova con creator finti diversi
usando gli intervalli allargati. I falsi positivi devono tornare vicini al 5%.

Uso: python scripts/verifica_taratura.py percorso/online-retail-dataset.csv
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creatorlift.placebo import calibrate, placebo, summary, thin  # noqa: E402
from prova_dati_pubblici import load_online_retail  # noqa: E402

if __name__ == "__main__":
    real = load_online_retail(sys.argv[1])
    for label, d in [("vero ~65/g", real), ("20/g", thin(real, 20, np.random.default_rng(1))),
                     ("10/g", thin(real, 10, np.random.default_rng(2)))]:
        cal = calibrate(d, None, seed=0, workers=None)
        k = cal["fattore_usato"]
        prima = summary(placebo(d, n_rep=100, seed=99))
        dopo = summary(placebo(d, n_rep=100, seed=99, widen=k))
        print(f"{label:>10}: fattore {k:.2f} | effetto 'chiaro' {prima['falsi_positivi']:.1%} -> "
              f"{dopo['falsi_positivi']:.1%} | zero nell'intervallo {prima['zero_nell_intervallo']:.1%} -> "
              f"{dopo['zero_nell_intervallo']:.1%}", flush=True)
