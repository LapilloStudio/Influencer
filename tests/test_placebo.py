"""Test dello strumento dei post finti (creatorlift.placebo)."""
import numpy as np

from creatorlift.placebo import fake_posts, inflation_factor, placebo, summary, thin
from creatorlift.simulate import simulate


def test_post_finti_nel_periodo_giusto():
    daily, _, _ = simulate(20, 1)
    p = fake_posts(daily, np.random.default_rng(0))
    assert p["creator"].nunique() == 6
    assert p["date"].isin(daily["date"].iloc[7:-14]).all()


def test_placebo_valuta_solo_i_creator_finti():
    daily, posts, _ = simulate(20, 4)
    res = placebo(daily, n_rep=3, workers=1, posts=posts, seed=1)
    assert set(res["creator"]) <= {f"finto_{k}" for k in range(1, 7)}
    assert len(res) == 18
    s = summary(res)
    assert set(s) >= {"falsi_positivi", "zero_nell_intervallo", "fattore", "creator_finti"}
    assert 0 <= s["falsi_positivi"] <= 1 and s["fattore"] > 0
    assert inflation_factor(res) == s["fattore"]


def test_negozio_piu_piccolo_stesso_andamento():
    daily, _, _ = simulate(80, 1)
    small = thin(daily, 20, np.random.default_rng(0))
    assert abs(small["orders"].mean() - 20) < 1
    assert np.corrcoef(small["orders"], daily["orders"])[0, 1] > 0.5


def test_allargamento_non_cambia_le_stime_puntuali():
    from creatorlift.model import estimate
    daily, posts, _ = simulate(20, 2)
    a, _ = estimate(daily, posts, seed=2)
    b, _ = estimate(daily, posts, seed=2, widen=1.0)
    c, _ = estimate(daily, posts, seed=2, widen=1.5)
    assert a.equals(b)  # fattore 1: numeri identici al motore senza taratura
    assert (c.incremental_orders == a.incremental_orders).all()
    assert ((c.high_90 - c.low_90) > (a.high_90 - a.low_90)).all()
    assert ((c.prob_effect_positive - 0.5).abs() <= (a.prob_effect_positive - 0.5).abs() + 1e-9).all()


def test_taratura_usa_solo_allargamenti():
    from creatorlift.placebo import calibrate
    daily, posts, _ = simulate(20, 1)
    steps = []
    cal = calibrate(daily, posts, n_rep=4, progress=steps.append)
    assert cal["fattore_usato"] == max(1.0, cal["fattore"])
    assert steps[-1] == 1.0 and len(steps) == 4
