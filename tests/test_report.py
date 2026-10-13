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
    # ordine: prima chi si ripaga; tra quelli senza un effetto chiaro, prima chi e' costato di piu'
    assert list(res["giudizio"])[0] == "si ripaga quasi certamente"
    nessuno = res[res["giudizio"] == "nessun effetto chiaro"]["cost_eur"].to_numpy()
    assert (np.diff(nessuno) <= 0).all()


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
    assert h.count("data:image/svg+xml;base64,") == len(res)  # un grafico giornaliero per creator
    for c in res.creator:
        assert c in h
    assert "Confronto con la verità" in h and "5 gennaio 2026" in h
    # senza nome del brand e autore i campi non compaiono (mai segnaposto tra parentesi)
    assert "Preparato per" not in h and "Preparato da" not in h and "[" not in _visible(h)
    d2 = from_simulation(20, 1)
    d2.truth = None
    assert "Confronto con la verità" not in R.html_report(d2, res, fit, 0.55)


def _visible(h: str) -> str:
    """Testo che il lettore vede (senza stili, tag e attributi)."""
    import html as H
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S)
    return H.unescape(re.sub(r"<[^>]+>", " ", h))


@pytest.mark.parametrize("margin", [0.2, 0.55])
def test_report_testi_senza_gergo_e_senza_negativi(sim, margin):
    d, est, fit = sim
    h = R.html_report(d, R.results(est, d, margin), fit, margin, cal={"creator_finti": 300, "fattore_usato": 1.3,
                                                                       "fattore": 1.3})
    t = _visible(h)
    assert not re.search(r"[-−]\s*\d", t), re.findall(r".{30}[-−]\s*\d.{10}", t)
    for parola in ("intervallo di confidenza", "p-value", "regressione", "coefficient", "significativ", "motore",
                   "deviazione"):
        assert parola not in t.lower(), parola
    assert not re.search(r"\bROI\b", t)
    assert "allargati" in t  # la taratura e' dichiarata


def test_report_nome_brand_e_autore(sim):
    d, est, fit = sim
    res = R.results(est, d, 0.55)
    h = R.html_report(d, res, fit, 0.55, brand="<b>Rossi & figli</b>", autore="Anna")
    assert "<b>Rossi" not in h and "&lt;b&gt;Rossi &amp; figli&lt;/b&gt;" in h
    assert "Preparato per" in h and "Preparato da" in h and "Anna" in h
    page_css = h[h.index("@page{"):h.index("</style>")]
    assert "<" not in page_css  # il nome nell'intestazione di pagina non chiude lo stile


def test_report_casi_limite(sim):
    d, est, fit = sim
    e2 = est.copy()
    e2.loc[0, ["low_90", "high_90"]] = np.nan
    e2.loc[1, "cost_eur"] = 0.0
    h = R.html_report(d, R.results(e2, d, 0.55), fit, 0.55)
    assert R.NOT_ENOUGH in h and "costo zero" in h
    # un solo creator
    res1 = R.results(est, d, 0.55).iloc[:1]
    h1 = _visible(R.html_report(d, res1, fit, 0.55))
    assert "1 di 1" in h1 and "di una collaborazione" in h1 and "uno creator" not in h1
    # nessun creator con un effetto chiaro
    e3 = est.assign(prob_effect_positive=0.5)
    h3 = _visible(R.html_report(d, R.results(e3, d, 0.55), fit, 0.55))
    assert "Nessuno dei" in h3 and "Per tutti e sei i creator" in h3


def test_ritorno_sotto_1_mai_arrotondato_a_1():
    from creatorlift.report_html import fmt_roi, roi_range
    assert fmt_roi(0.96) == "0,96" and fmt_roi(0.94) == "0,9" and fmt_roi(1.0) == "1,0" and fmt_roi(7.33) == "7,3"
    assert roi_range(-0.5, 0.96) == "tra 0 e 0,96"


def test_nomi_con_caratteri_speciali_nel_report(sim):
    d, est, fit = sim
    res = R.results(est, d, 0.55).assign(creator=lambda x: x.creator.where(x.index > 0, "<b>Niccolò & co</b>"))
    h = R.html_report(d, res.iloc[1:], fit, 0.55)
    t = R._table_html(R.display_table(res))
    assert "<b>Niccolò" not in t and "&lt;b&gt;Niccolò &amp; co&lt;/b&gt;" in t
    assert h


def test_totale_campagna_coerente(sim):
    from creatorlift.model import total_incremental
    d, est, fit = sim
    t = total_incremental(fit)
    assert t["low_90"] <= t["incremental_orders"] <= t["high_90"]
    # con effetti piccoli il totale e' quasi la somma delle stime per creator
    assert abs(t["incremental_orders"] - est["incremental_orders"].sum()) < 0.02 * abs(est["incremental_orders"].sum()) + 2


def test_grafico_svg_autonomo(sim):
    d, est, fit = sim
    svg = R.fig_svg(R.creator_figure(fit, d, est.creator.iloc[0])).decode()
    assert svg.lstrip().startswith("<?xml") and "<svg" in svg
    assert "<dc:date>" not in svg and "matplotlib.org" not in svg
    assert "<text" in svg  # testo vero, non tracciati
    assert "system-ui" in svg and "DejaVu" not in svg  # stesso carattere del report
