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
