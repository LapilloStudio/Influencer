"""Pagina "Risultati": tabella, giudizi, grafici e report da scaricare."""
from datetime import datetime

import streamlit as st

from creatorlift import report as R
from creatorlift.io_shopify import EXCLUSION_LABELS
from creatorlift.ui import creator_png, md, show_avvisi

st.title("Risultati")

if "data" not in st.session_state:
    st.info("Non ci sono ancora dati: carica i file del negozio o usa i dati simulati.")
    st.page_link("views/carica.py", label="Carica dati", icon="📂")
    st.stop()

data, est, fit, data_id = (st.session_state[k] for k in ("data", "est", "fit", "data_id"))
first, last = data.daily["date"].iloc[0], data.daily["date"].iloc[-1]
origine = "dati simulati" if data.origine == "simulati" else "export Shopify"
st.caption(f"{R.fmt_date(first)} – {R.fmt_date(last)} · {data.n_days} giorni · "
           f"{R.fmt_dec(data.orders_per_day, 1)} ordini al giorno · {origine}")
show_avvisi(data.avvisi, only_important=True)

margine = st.slider("Margine lordo sul venduto", min_value=5, max_value=95, value=55, step=1, format="%d%%",
                    key="margine",
                    help="La parte del prezzo che resta dopo il costo della merce. Serve solo per il ritorno "
                         "sull'investimento: le vendite in più non cambiano.") / 100
res = R.results(est, data, margine)

st.subheader("In breve")
for r in res.itertuples(index=False):
    nota = R.code_note(r)
    st.markdown("- " + md(R.sentence(r) + (" " + nota if nota else "")))

st.subheader("Per creator")
st.dataframe(R.display_table(res), hide_index=True, width="stretch")
st.caption(f"Vendite in più: ordini che non ci sarebbero stati senza i post, con o senza codice. Intervallo "
           f"probabile: contiene il valore vero 9 volte su 10; se parte da 0 il creator potrebbe non aver portato "
           f"nulla. ROI sul margine: euro di margine tornati per ogni euro speso (sopra 1 si è ripagato), con "
           f"{data.aov_label} di {R.fmt_eur(data.aov)}.")

st.subheader("Si sono ripagati?")
st.image(R.fig_png(R.roi_figure(res)), width="stretch")
st.caption("Il punto è la stima, la barra l'intervallo probabile. A destra della linea verticale il costo si è "
           "ripagato. Un cerchio vuoto sullo zero vuol dire nessun effetto rilevato.")

st.subheader("Giorno per giorno, attorno a ogni post")
creator = st.selectbox("Creator", list(res["creator"]), key="creator_grafico")
st.markdown(md(R.sentence(res[res.creator == creator].iloc[0])))
with st.spinner("Disegno il grafico…"):
    st.image(creator_png(data_id, creator, fit, data), width="stretch")
st.caption("Punti: ordini reali. Linea blu: ordini attesi senza il creator, con la fascia della variazione normale "
           "da un giorno all'altro. Linea arancione: previsione che tiene conto del creator. La distanza tra le due "
           "linee sono le vendite in più.")

if data.truth is not None:
    st.subheader("Confronto con la verità")
    tt = R.truth_table(res, data.truth)
    dentro = int((tt["Il vero è nell'intervallo?"] == "sì").sum())
    st.write(f"Nei dati simulati l'effetto vero è noto. L'intervallo probabile lo contiene per {dentro} creator su "
             f"{len(tt)} (in media dovrebbe succedere 9 volte su 10). Contare solo gli ordini con codice, invece, "
             f"di solito sottostima i creator che funzionano e attribuisce vendite anche a chi non ne porta.")
    st.dataframe(tt, hide_index=True, width="stretch")

if data.esclusi or (data.codici_non_assegnati is not None and len(data.codici_non_assegnati)):
    with st.expander("Dettagli sui dati"):
        if data.esclusi:
            st.write("Ordini non contati:")
            st.dataframe([{"Motivo": EXCLUSION_LABELS[k], "Ordini": v} for k, v in data.esclusi.items()],
                         hide_index=True)
        if data.codici_non_assegnati is not None and len(data.codici_non_assegnati):
            st.write("Codici sconto usati che non appartengono a nessun creator dell'elenco:")
            st.dataframe(data.codici_non_assegnati.head(30).rename(columns={"codice": "Codice", "ordini": "Ordini"}),
                         hide_index=True)
        show_avvisi([a for a in data.avvisi if a.livello != "importante"])

st.divider()
st.subheader("Report per il brand")


def _report(data=data, res=res, fit=fit, margine=margine) -> bytes:
    return R.html_report(data, res, fit, margine).encode("utf-8")


st.download_button("Scarica il report (HTML, si stampa anche in PDF)", data=_report,
                   file_name=f"creator_lift_report_{datetime.now():%Y%m%d_%H%M}.html", mime="text/html",
                   on_click="ignore", type="primary", icon="📄")
st.caption("Il report si apre con qualsiasi browser, anche senza connessione. Per un PDF: apri il file e scegli "
           "Stampa › Salva come PDF.")
