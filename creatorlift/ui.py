"""Funzioni condivise dalle pagine Streamlit (stato della sessione, cache)."""
from __future__ import annotations

import hashlib
import re

import streamlit as st

from creatorlift import report as R
from creatorlift.io_shopify import ShopData
from creatorlift.placebo import calibrate

POSTS_TEMPLATE = (
    "creator;data_post;costo_eur;codice_sconto\n"
    "giulia_style;10/02/2025;600,00;GIULIA10\n"
    "sara_mom;20/04/2025;500,00;SARAMAMMA\n"
    "marco_daily;16/03/2025;400,00;\n"
)
PROMO_TEMPLATE = "data_inizio;data_fine;descrizione\n04/01/2025;10/01/2025;saldi invernali\n28/11/2025;01/12/2025;black friday\n"


def md(text: str) -> str:
    """Testo da mostrare con st.markdown: i nomi arrivano dai file del brand,
    quindi si neutralizzano i simboli che Markdown interpreterebbe (anche le
    immagini, che farebbero scaricare qualcosa da Internet)."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~])", r"\\\1", str(text))


def fingerprint(data: ShopData) -> str:
    h = hashlib.sha256()
    h.update(data.daily.to_csv(index=False).encode())
    h.update(data.posts.to_csv(index=False).encode())
    h.update(repr(round(data.aov, 6)).encode())
    return h.hexdigest()[:16]


def set_data(data: ShopData, progress=None):
    """Taratura con i post finti, poi il motore una volta; tutto nella sessione."""
    cal = calibrate(data.daily, data.posts, progress=progress)
    est, shape, fit = R.analyze(data, seed=0, widen=cal["fattore_usato"])
    st.session_state["data"] = data
    st.session_state["est"] = est
    st.session_state["fit"] = fit
    st.session_state["cal"] = cal
    st.session_state["data_id"] = fingerprint(data) + f"-{cal['fattore_usato']:.4f}"


def clear_data():
    for k in ("data", "est", "fit", "cal", "data_id"):
        st.session_state.pop(k, None)
    creator_png.clear()


@st.cache_data(max_entries=64, show_spinner=False)
def creator_png(data_id: str, creator: str, _fit, _data) -> bytes:
    return R.fig_png(R.creator_figure(_fit, _data, creator))


def show_avvisi(avvisi, only_important=False):
    for a in avvisi:
        if a.livello == "importante":
            st.warning(a.testo, icon="⚠️")
        elif not only_important:
            st.info(a.testo, icon="ℹ️")
