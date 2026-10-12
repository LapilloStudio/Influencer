"""Test di tabella, frasi, grafici e report (creatorlift.report)."""
import re
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from creatorlift import report as R
from creatorlift.io_shopify import from_simulation
from creatorlift.model import estimate


@pytest.fixture(scope="module")
def sim():
    d = from_simulation(20, 1)
    est, shape, fit = R.analyze(d, seed=1)
    return d, est, fit


def test_roi_uguale_al_motore(sim):
    d, est, _ = sim
    res = R.results(est, d, 0.55)
    e = est.set_index("creator").loc[res.creator].reset_index()
    for col in ("roi", "roi_low", "roi_high"):
        np.testing.assert_array_equal(res[col].to_numpy(), e[col].to_numpy())
    # col margine cambia solo il ROI, non le vendite in piu'
    res30 = R.results(est, d, 0.30)
    e30 = est.set_index("creator").loc[res30.creator].reset_index()
    np.testing.assert_allclose(res30["roi"], (e30["incremental_orders"] * d.aov * 0.30 / e30["cost_eur"]).round(2))
    assert set(res30["creator"]) == set(est["creator"])
    # ordine: prima chi si ripaga
    assert list(res["giudizio"])[0] == "si ripaga quasi certamente"


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("margin", [0.2, 0.55, 0.9])
def test_nessun_numero_negativo_mostrato(seed, margin):
    d = from_simulation(20, seed)
    est, _ = estimate(d.daily, d.posts, seed=seed, aov=d.aov, margin=0.55)
    res = R.results(est, d, margin)
    table = R.display_table(res)
    for v in table.to_numpy().ravel():
        assert not re.search(r"-\s*\d|−\s*\d", str(v)), v
    for r in res.itertuples(index=False):
        assert not re.search(r"-\d", R.sentence(r))
        if r.roi < 0:
            assert table.set_index("Creator").loc[r.creator, "ROI sul margine"] == R.NO_EFFECT
    truth = R.truth_table(res, d.truth)
    for v in truth.to_numpy().ravel():
        assert not re.search(r"-\s*\d", str(v)), v


def _row(**kw):
    base = dict(creator="X", n_posts=1, cost_eur=500.0, low_90=40.0, high_90=120.0, incremental_orders=80.0,
                estimable=True, orders_with_code=30, giudizio="si ripaga quasi certamente")
    base.update(kw)
    return SimpleNamespace(**base)


def test_frasi():
    assert R.sentence(_row()) == ("Il post di X ha portato tra 40 e 120 ordini in più. Con un costo di 500\u00a0€, "
                                  "quasi certamente si è ripagato.")
    assert R.sentence(_row(n_posts=3, giudizio="probabilmente si ripaga")) == (
        "I 3 post di X hanno portato tra 40 e 120 ordini in più. Con un costo di 500\u00a0€, probabilmente si sono "
        "ripagati, ma non è sicuro.")
    assert R.sentence(_row(giudizio="porta vendite ma non si ripaga", cost_eur=1200.5)) == (
        "Il post di X ha portato tra 40 e 120 ordini in più, ma con un costo di 1.200,50\u00a0€ probabilmente non si è "
        "ripagato.")
    s = R.sentence(_row(giudizio="nessun effetto chiaro", low_90=-30.0, n_posts=2))
    assert "tra 0 e 120" in s and "potrebbero anche essere nessuna" in s and "si siano ripagati" in s
    s = R.sentence(_row(giudizio="nessun effetto chiaro", low_90=-50.0, high_90=-5.0))
    assert "non ha portato vendite in più" in s
    assert "non bastano" in R.sentence(_row(estimable=False))
    assert R.code_note(_row()) == "Gli ordini con il suo codice sconto sono 30."
    assert R.code_note(_row(orders_with_code=None)) == ""


def test_casi_limite_tabella(sim):
    d, est, _ = sim
    e2 = est.copy()
    e2.loc[0, ["low_90", "high_90"]] = np.nan
    e2.loc[1, "cost_eur"] = 0.0
    res = R.results(e2, d, 0.55)
    t = R.display_table(res).set_index("Creator")
    assert t.loc[e2.creator[0], "Intervallo probabile"] == R.NOT_ENOUGH
    assert t.loc[e2.creator[0], "Giudizio"] == R.NOT_ENOUGH
    assert t.loc[e2.creator[1], "ROI sul margine"] == "costo zero"
    R.fig_png(R.roi_figure(res))  # non deve fallire


def test_formati_italiani():
    assert R.fmt_int(1234567) == "1.234.567"
    assert R.fmt_dec(2.345, 1) == "2,3" and R.fmt_dec(1234.5, 2) == "1.234,50"
    assert R.fmt_eur(500) == "500\u00a0€" and R.fmt_eur(83.333) == "83,33\u00a0€"
    assert R.fmt_date("2025-02-10") == "10 feb 2025"


def test_grafici(sim):
    d, est, fit = sim
    for c in est.creator:
        png = R.fig_png(R.creator_figure(fit, d, c))
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
    png = R.fig_png(R.roi_figure(R.results(est, d, 0.55)))
    assert png[:4] == b"\x89PNG"


def test_report_html_autonomo(sim):
    d, est, fit = sim
    res = R.results(est, d, 0.55)
    h = R.html_report(d, res, fit, 0.55, now=datetime(2026, 1, 5))
    assert h.startswith("<!doctype html>") and "lang='it'" in h
    assert not re.search(r"(src|href)\s*=\s*['\"]?(https?:)?//", h)  # nessuna risorsa esterna
    assert "http://" not in h and "https://" not in h
    assert h.count("data:image/png;base64,") == 1 + len(res)
    for c in res.creator:
        assert c in h
    assert "Confronto con la verità" in h and "5 gen 2026" in h
    assert "intervallo di confidenza" not in h.lower()
    d2 = from_simulation(20, 1)
    d2.truth = None
    assert "Confronto con la verità" not in R.html_report(d2, res, fit, 0.55)


def test_nomi_con_caratteri_speciali_nel_report(sim):
    d, est, fit = sim
    res = R.results(est, d, 0.55).assign(creator=lambda x: x.creator.where(x.index > 0, "<b>Niccolò & co</b>"))
    h = R.html_report(d, res.iloc[1:], fit, 0.55)
    t = R._table_html(R.display_table(res))
    assert "<b>Niccolò" not in t and "&lt;b&gt;Niccolò &amp; co&lt;/b&gt;" in t
    assert h
