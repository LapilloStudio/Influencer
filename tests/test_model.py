"""Test del motore di stima (creatorlift.model)."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from creatorlift.model import Fit, daily_paths, estimate, fit_and_draw, verdict
from creatorlift.simulate import simulate

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"

# Seed fissi: il risultato del test di calibrazione e' deterministico.
# Su 20 gruppi da 30 negozi (seed 0-599) nessun gruppo esce dall'intervallo
# di copertura 80-97% e uno solo supera il 15% di falsi positivi: con seed
# diversi il test potrebbe fallire per caso, non per un errore del motore.
CALIBRATION_SEEDS = range(30)
ORDERS_PER_DAY = 20


def _run(size, seed, **kw):
    daily, posts, truth = simulate(size, seed)
    aov = daily["revenue_eur"].sum() / daily["orders"].sum()
    out, hl = estimate(daily, posts, seed=seed, aov=aov, margin=0.55, **kw)
    return out.merge(truth, on="creator"), hl


@pytest.fixture(scope="module")
def calibration():
    rows = []
    for seed in CALIBRATION_SEEDS:
        m, _ = _run(ORDERS_PER_DAY, seed)
        m["seed"] = seed
        m["giudizio"] = m.apply(verdict, axis=1)
        rows.append(m)
    df = pd.concat(rows, ignore_index=True)
    df["covered"] = (df.true_incremental_orders >= df.low_90) & (df.true_incremental_orders <= df.high_90)
    return df


@pytest.mark.slow
def test_intervallo_contiene_effetto_vero(calibration):
    coverage = calibration["covered"].mean()
    per_creator = calibration.groupby("creator")["covered"].mean().round(2).to_dict()
    print(f"\ncopertura al 90% su {len(calibration)} casi: {coverage:.3f}; per creator: {per_creator}")
    assert 0.80 <= coverage <= 0.97


@pytest.mark.slow
def test_creator_senza_effetto_raramente_giudicato_utile(calibration):
    zero = calibration[calibration["creator"] == "luca_tech"]
    assert (zero["true_incremental_orders"] == 0).all()
    false_pos = (zero["giudizio"] != "nessun effetto chiaro").mean()
    print(f"\ncreator senza effetto giudicato utile: {false_pos:.3f} ({len(zero)} negozi)")
    assert false_pos < 0.15


@pytest.mark.parametrize("mode", ["windows", "halflife"])
def test_uguale_al_prototipo(mode):
    """Il motore spostato nel pacchetto da' esattamente i numeri del prototipo
    originale. fixtures/golden_originale.csv e' stato generato con
    `git show 7086e5a:estimate.py` (primo commit, prototipo invariato)."""
    golden = pd.read_csv(FIXTURES / "golden_originale.csv")
    for seed in (0, 1, 2):
        daily, posts, _ = simulate(20, seed)
        aov = daily["revenue_eur"].sum() / daily["orders"].sum()
        out, hl = estimate(daily, posts, seed=seed, aov=aov, margin=0.55, mode=mode)
        exp = golden[(golden.seed == seed) & (golden["mode"] == mode)]
        assert str(hl) == str(exp["forma"].iloc[0])
        cols = list(out.columns)
        pd.testing.assert_frame_equal(
            out.reset_index(drop=True), exp[cols].reset_index(drop=True), check_dtype=False, check_exact=True
        )


def test_colonne_e_coerenza_intervallo():
    out, hl = estimate(*simulate(20, 1)[:2], seed=1, aov=45.0, margin=0.55)
    assert hl == "finestre 0 / 1-2 / 3-6 / 7-13 giorni"
    for col in ("creator", "incremental_orders", "low_90", "high_90", "prob_effect_positive",
                "cost_eur", "roi", "roi_low", "roi_high"):
        assert col in out.columns
    assert (out.low_90 <= out.high_90).all()
    assert out.prob_effect_positive.between(0, 1).all()
    # ROI = ordini in piu' x scontrino x margine / costo
    np.testing.assert_allclose(out.roi, (out.incremental_orders * 45 * 0.55 / out.cost_eur).round(2))


def test_daily_paths_coerente_con_stima():
    daily, posts, _ = simulate(20, 3)
    out, _, f = estimate(daily, posts, seed=3, aov=45.0, margin=0.55, return_fit=True)
    for creator in out.creator:
        p = daily_paths(f, creator)
        assert len(p) == len(daily)
        assert (p.orders.to_numpy() == daily.orders.to_numpy()).all()
        point = out.set_index("creator").loc[creator, "incremental_orders"]
        assert p.incremental.sum() == pytest.approx(point, abs=0.06)
        assert ((p.without_lo < p.without_creator) & (p.without_creator < p.without_hi)).all()
        assert (p.normal_lo <= p.without_lo + 1).all() and (p.normal_hi >= p.without_hi - 1).all()
        # lontano dai post la previsione con e senza il creator coincide
        days = [daily.index[daily.date == d][0] for d in posts.loc[posts.creator == creator, "date"]]
        far = np.ones(len(daily), bool)
        for d in days:
            far[d:d + 14] = False
        np.testing.assert_allclose(p.with_creator[far], p.without_creator[far])
    with pytest.raises(KeyError):
        daily_paths(f, "Giulia_Style")


def test_fascia_normale_contiene_circa_il_90_percento_dei_giorni():
    """Sui giorni senza nessun post, gli ordini reali cadono nella fascia di
    variazione normale circa il 90% delle volte."""
    daily, posts, _ = simulate(20, 4)
    out, _, f = estimate(daily, posts, seed=4, return_fit=True)
    p = daily_paths(f, out.creator.iloc[0])
    no_post = np.ones(len(daily), bool)
    for d in posts.date:
        i = daily.index[daily.date == d][0]
        no_post[i:i + 14] = False
    inside = ((p.orders >= p.normal_lo) & (p.orders <= p.normal_hi))[no_post].mean()
    assert 0.80 <= inside <= 0.98


def test_fascia_normale_segue_la_sovradispersione():
    """Su dati molto piu' variabili del previsto la fascia si allarga: con la
    sola Poisson coprirebbe circa il 60% dei giorni."""
    daily, posts, _ = simulate(20, 4)
    rng = np.random.default_rng(104)
    daily = daily.assign(orders=rng.poisson(daily.orders.to_numpy() * rng.gamma(8.0, 1 / 8.0, len(daily))))
    f = fit_and_draw(daily, posts, seed=4)
    p = daily_paths(f, f.creators[0])
    no_post = np.ones(len(daily), bool)
    for d in posts.date:
        i = daily.index[daily.date == d][0]
        no_post[i:i + 14] = False
    inside = ((p.orders >= p.normal_lo) & (p.orders <= p.normal_hi))[no_post].mean()
    assert 0.85 <= inside <= 0.97


@pytest.mark.filterwarnings("ignore:covariance is not symmetric")
def test_giorno_del_post_senza_ordini_non_rompe_i_grafici():
    """Se il giorno di un post ha zero ordini quel coefficiente non e'
    stimabile: le fasce restano vuote (NaN) solo in quel giorno, senza errori."""
    daily, posts, _ = simulate(20, 1)
    day = posts.loc[posts.creator == "elena_fit", "date"].iloc[0]
    i = daily.index[daily.date == day][0]
    daily.loc[i, "orders"] = 0
    f = fit_and_draw(daily, posts, seed=1)
    for c in f.creators:
        p = daily_paths(f, c)
        assert np.isfinite(p.with_creator).all() and np.isfinite(p.without_creator).all()
        missing = np.flatnonzero(p.normal_hi.isna().to_numpy())
        assert set(missing) <= {i}


def test_nomi_simili_non_si_confondono():
    """'giulia' e 'giulia_' sono due creator diversi."""
    daily, posts, _ = simulate(20, 2)
    posts = posts.copy()
    posts.loc[posts.creator == "giulia_style", "creator"] = "giulia"
    posts.loc[posts.creator == "fede_vlog", "creator"] = "giulia_"
    f = fit_and_draw(daily, posts, seed=2)
    cols = [f.X.columns[j] for j in f.creator_columns("giulia")]
    assert cols == ["cr_giulia__0_0", "cr_giulia__1_2", "cr_giulia__3_6", "cr_giulia__7_13"]


def test_comandi_del_prototipo(tmp_path):
    """python simulate.py / python estimate.py funzionano come prima."""
    subprocess.run([sys.executable, "simulate.py", "--orders-per-day", "20", "--seed", "1", "--out", str(tmp_path)],
                   cwd=ROOT, check=True, capture_output=True)
    subprocess.run([sys.executable, "estimate.py", str(tmp_path)], cwd=ROOT, check=True, capture_output=True)
    stima = pd.read_csv(tmp_path / "stima.csv")
    assert list(stima.columns) == ["creator", "orders_with_code", "incremental_orders", "low_90", "high_90",
                                   "prob_effect_positive", "cost_eur", "roi", "roi_low", "roi_high", "giudizio"]
    daily = pd.read_csv(tmp_path / "ordini_giornalieri.csv")
    posts = pd.read_csv(tmp_path / "post_creator.csv")
    out, _ = estimate(daily, posts, aov=daily.revenue_eur.sum() / daily.orders.sum(), margin=0.55)
    pd.testing.assert_frame_equal(stima[out.columns], out, check_dtype=False)
    assert (stima.giudizio == stima.apply(verdict, axis=1)).all()


@pytest.mark.parametrize("row,expected", [
    ({"prob_effect_positive": 0.90, "roi": 3.0, "roi_low": 1.5}, "nessun effetto chiaro"),
    ({"prob_effect_positive": 0.99, "roi": 3.0, "roi_low": 1.2}, "si ripaga quasi certamente"),
    ({"prob_effect_positive": 0.99, "roi": 1.4, "roi_low": 0.6}, "probabilmente si ripaga"),
    ({"prob_effect_positive": 0.99, "roi": 0.7, "roi_low": 0.2}, "porta vendite ma non si ripaga"),
])
def test_giudizio(row, expected):
    assert verdict(pd.Series(row)) == expected
