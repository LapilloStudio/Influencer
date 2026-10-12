"""Test dell'interfaccia Streamlit senza browser (streamlit.testing)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from creatorlift.simulate import simulate, to_shopify

APP = str(Path(__file__).resolve().parents[1] / "app.py")
TIMEOUT = 120


@pytest.fixture(autouse=True)
def _clear_cache():
    import streamlit as st
    st.cache_data.clear()
    yield


def _testi(at):
    parti = [m.value for m in at.markdown] + [m.value for m in at.caption] + [m.value for m in at.info]
    parti += [m.value for m in at.warning] + [m.value for m in at.error]
    return "\n".join(map(str, parti))


def test_pagina_iniziale():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not at.exception
    assert at.title[0].value == "Carica dati"
    assert any(b.label == "Analizza" and b.disabled for b in at.button)


def test_risultati_senza_dati():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at.switch_page("views/risultati.py").run()
    assert not at.exception
    assert "Non ci sono ancora dati" in at.info[0].value


def test_dati_simulati_e_risultati():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at.radio(key="fonte").set_value("Dati simulati").run()
    at.number_input(key="sim_ordini").set_value(20)
    at.number_input(key="sim_seed").set_value(1)
    next(b for b in at.button if b.label == "Usa dati simulati").click().run()
    assert not at.exception
    assert at.title[0].value == "Risultati"
    tabella = at.dataframe[0].value
    assert len(tabella) == 6 and "ROI sul margine" in tabella.columns
    testo = _testi(at)
    assert "I 3 post di giulia\\_style hanno portato tra" in testo
    assert "Confronto con la verità" in [s.value for s in at.subheader]
    roi_55 = tabella.set_index("Creator").loc["giulia_style", "ROI sul margine"]

    # AppTest non ricorda il cambio di pagina fatto dallo script: lo si ripete
    at.switch_page("views/risultati.py")
    at.slider(key="margine").set_value(30).run()
    assert not at.exception
    roi_30 = at.dataframe[0].value.set_index("Creator").loc["giulia_style", "ROI sul margine"]
    assert roi_30 != roi_55
    at.selectbox(key="creator_grafico").set_value("sara_mom").run()
    assert not at.exception


def test_file_shopify():
    daily, posts, _ = simulate(20, 2)
    ordini, post, promo = to_shopify(daily, posts, seed=2)
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at.file_uploader(key="ordini").set_value([("ordini.csv", ordini.encode(), "text/csv")])
    at.file_uploader(key="post").set_value(("post.csv", post.encode(), "text/csv"))
    at.file_uploader(key="promo").set_value(("promo.csv", promo.encode(), "text/csv")).run()
    next(b for b in at.button if b.label == "Analizza").click().run()
    assert not at.exception
    assert at.title[0].value == "Risultati"
    assert len(at.dataframe[0].value) == 6
    assert "Confronto con la verità" not in [s.value for s in at.subheader]


def test_file_sbagliato_errore_chiaro():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at.file_uploader(key="ordini").set_value([("ordini.csv", b"Name;Total\n#1;10,00\n", "text/csv")])
    at.file_uploader(key="post").set_value(("post.csv", b"creator,data_post,costo_eur\nx,2025-01-01,10\n",
                                            "text/csv")).run()
    next(b for b in at.button if b.label == "Analizza").click().run()
    assert not at.exception
    assert at.title[0].value == "Carica dati"
    assert "Excel" in at.error[0].value


def test_privacy_controllata(monkeypatch):
    from creatorlift.privacy import problems
    ok = {"browser.gatherUsageStats": False, "server.showEmailPrompt": False, "server.enableCORS": True,
          "server.enableXsrfProtection": True, "global.developmentMode": False, "server.address": "127.0.0.1",
          "theme.base": "light"}
    assert problems(ok.get) == []
    assert len(problems({**ok, "browser.gatherUsageStats": True, "server.address": None}.get)) == 2


def test_config_toml_privacy():
    import tomllib
    cfg = tomllib.loads((Path(APP).parent / ".streamlit" / "config.toml").read_text())
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["server"]["address"] == "127.0.0.1"
    assert cfg["server"]["showEmailPrompt"] is False
    assert cfg["client"]["showErrorLinks"] is False


def test_nessuna_mappa_o_risorsa_esterna_nel_codice():
    radice = Path(APP).parent
    sorgenti = [radice / "app.py", *radice.glob("views/*.py"), *radice.glob("creatorlift/*.py")]
    for f in sorgenti:
        t = f.read_text()
        for vietato in ("st.map(", "pydeck", "plotly", "unsafe_allow_html", "st.html(", "page_icon=\":material"):
            assert vietato not in t, (f.name, vietato)
