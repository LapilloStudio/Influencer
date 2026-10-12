"""Esperimento non adottato: incertezza Newey-West (HAC) al posto del quasi-Poisson.
Risultato: intervalli piu stretti, non piu larghi (vedi docs/prova-post-finti.md).
Uso: python scripts/esperimento_newey_west.py percorso/online-retail-dataset.csv
"""
import sys, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/Influencer"); sys.path.insert(0, "/home/user/Influencer/scripts")
warnings.simplefilter("ignore")
import statsmodels.api as sm
import creatorlift.model as M
from creatorlift.placebo import fake_posts, thin
from creatorlift.simulate import simulate
from prova_dati_pubblici import load_online_retail

ORIG_FIT = M.fit
def make_fit(lags):
    def fit_hac(daily, posts, half_life):
        n = len(daily); day_index = {d: i for i, d in enumerate(daily["date"])}
        X = M.base_design(daily); creators = sorted(posts["creator"].unique())
        for c in creators:
            days = [day_index[d] for d in posts.loc[posts.creator == c, "date"]]
            for (a, b), x in zip(M.WINDOWS, M.windows(n, days)):
                X[f"cr_{c}__{a}_{b}"] = x
        res = sm.GLM(daily["orders"].astype(float), X, family=sm.families.Poisson()).fit(
            cov_type="HAC", cov_kwds={"maxlags": lags})
        return res, X, creators
    return fit_hac

def init(lags):
    warnings.simplefilter("ignore")
    if lags: M.fit = make_fit(lags)

def placebo_job(args):
    daily, rep = args
    rng = np.random.default_rng([7, rep])
    est, _ = M.estimate(daily, fake_posts(daily, rng), seed=rep)
    return est

def sim_job(rep):
    daily, posts, truth = simulate(20, rep)
    est, _ = M.estimate(daily, posts, seed=rep)
    return est.merge(truth, on="creator")

if __name__ == "__main__":
    real = load_online_retail(sys.argv[1])
    datasets = [("vero ~65/g", real), ("20/g", thin(real, 20, np.random.default_rng(1))),
                ("10/g", thin(real, 10, np.random.default_rng(2)))]
    for lags in [None, 7, 14]:
        name = "attuale (quasi-Poisson)" if lags is None else f"Newey-West, {lags} giorni"
        with ProcessPoolExecutor(4, initializer=init, initargs=(lags,)) as ex:
            for lab, d in datasets:
                r = pd.concat(ex.map(placebo_job, [(d, k) for k in range(100)])).dropna(subset=["low_90"])
                fp = (r.prob_effect_positive >= .95).mean(); z = ((r.low_90 <= 0) & (r.high_90 >= 0)).mean()
                print(f"{name:26} | post finti, negozio {lab:10}: effetto 'chiaro' {fp:5.1%}  zero nell'intervallo {z:5.1%}", flush=True)
            s = pd.concat(ex.map(sim_job, range(100)))
            cov = ((s.true_incremental_orders >= s.low_90) & (s.true_incremental_orders <= s.high_90)).mean()
            det = s[s.creator == "giulia_style"].prob_effect_positive.ge(.95).mean()
            det2 = s[s.creator == "sara_mom"].prob_effect_positive.ge(.95).mean()
            fps = s[s.creator == "luca_tech"].prob_effect_positive.ge(.95).mean()
            print(f"{name:26} | simulati 20/g (100 negozi): copertura {cov:5.1%}, giulia rilevata {det:5.1%}, "
                  f"sara rilevata {det2:5.1%}, luca (zero) falso positivo {fps:5.1%}\n", flush=True)
