"""Pagina "Carica dati": file del negozio oppure dati simulati."""
import streamlit as st

from creatorlift.io_shopify import ErroreDati, from_simulation, load_shopify
from creatorlift.ui import POSTS_TEMPLATE, PROMO_TEMPLATE, clear_data, set_data, show_avvisi

st.title("Carica dati")
st.write("Creator Lift stima quante vendite in più ha portato ogni collaborazione con un creator, anche quelle "
         "fatte senza codice sconto. I file restano su questo computer: niente viene inviato altrove.")

fonte = st.radio("Da dove prendo i dati?", ["File del negozio (Shopify)", "Dati simulati"], horizontal=True,
                 key="fonte")

if fonte == "File del negozio (Shopify)":
    st.subheader("1. Ordini")
    st.caption("In Shopify: Ordini › Esporta › \"Tutti gli ordini\" in formato CSV. Carica il file così com'è, "
               "senza aprirlo prima con Excel. Se Shopify ti ha mandato più file, caricali tutti.")
    ordini = st.file_uploader("Export degli ordini (CSV)", type=["csv"], accept_multiple_files=True, key="ordini")

    st.subheader("2. Post dei creator")
    st.caption("Un post per riga, con le colonne creator, data_post, costo_eur e, se c'è, codice_sconto. "
               "Va bene anche salvato da Excel.")
    c1, c2 = st.columns([3, 1])
    with c1:
        post = st.file_uploader("Elenco dei post (CSV)", type=["csv"], key="post")
    with c2:
        st.download_button("Scarica un modello", POSTS_TEMPLATE.encode("utf-8-sig"), "post_creator_modello.csv",
                           mime="text/csv", on_click="ignore")

    st.subheader("3. Giorni di promozione (facoltativo)")
    st.caption("Saldi, Black Friday, sconti su tutto il sito: colonne data_inizio e data_fine (oppure una "
               "colonna data con un giorno per riga). Aiutano a non scambiare una promozione per l'effetto di "
               "un creator.")
    c1, c2 = st.columns([3, 1])
    with c1:
        promo = st.file_uploader("Giorni di promozione (CSV)", type=["csv"], key="promo")
    with c2:
        st.download_button("Scarica un modello", PROMO_TEMPLATE.encode("utf-8-sig"), "promozioni_modello.csv",
                           mime="text/csv", on_click="ignore", key="modello_promo")

    with st.expander("Ordini da contare"):
        st.caption("Annullati, rimborsati, stornati e scaduti non vengono mai contati.")
        zero = st.checkbox("Conta anche gli ordini a 0 € (omaggi, test con codici al 100%)", key="incl_zero")
        prova = st.checkbox("Conta anche gli ordini di prova (Bogus Gateway)", key="incl_prova")

    if st.button("Analizza", type="primary", disabled=not (ordini and post)):
        try:
            with st.spinner("Leggo i file…"):
                data = load_shopify([(f.name, f.getvalue()) for f in ordini], post.getvalue(),
                                    promo.getvalue() if promo else None, include_zero=zero, include_test=prova)
            barra = st.progress(0.0, text="Controllo l'affidabilità con creator inventati (meno di un minuto)…")
            set_data(data, progress=lambda x: barra.progress(x, text="Controllo l'affidabilità con creator "
                                                                     "inventati (meno di un minuto)…"))
        except ErroreDati as e:
            clear_data()
            st.error(str(e), icon="🚫")
        except Exception:  # noqa: BLE001 - mai un errore tecnico in inglese all'utente
            clear_data()
            st.error("Non sono riuscito a leggere i file. Controlla di aver caricato l'export degli ordini di Shopify "
                     "e il file dei post nel formato del modello, poi riprova.", icon="🚫")
        else:
            st.switch_page("views/risultati.py")
    elif not (ordini and post):
        st.caption("Servono almeno l'export degli ordini e l'elenco dei post.")
else:
    st.write("Un anno di ordini di un negozio inventato, con 6 creator di cui si conosce l'effetto vero (uno non "
             "ha nessun effetto). Serve per vedere come funziona e quanto la stima ci azzecca.")
    c1, c2 = st.columns(2)
    with c1:
        per_giorno = st.number_input("Ordini al giorno", min_value=2, max_value=500, value=20, step=1,
                                     key="sim_ordini")
    with c2:
        seme = st.number_input("Seed (cambia per ottenere un altro negozio)", min_value=0, max_value=100_000,
                               value=1, step=1, key="sim_seed")
    if st.button("Usa dati simulati", type="primary"):
        barra = st.progress(0.0, text="Creo i dati e controllo l'affidabilità (meno di un minuto)…")
        set_data(from_simulation(float(per_giorno), int(seme)),
                 progress=lambda x: barra.progress(x, text="Creo i dati e controllo l'affidabilità (circa un "
                                                          "minuto)…"))
        st.switch_page("views/risultati.py")

if "data" in st.session_state:
    d = st.session_state["data"]
    st.divider()
    st.caption(f"Dati già caricati: {d.n_days} giorni, {d.orders_per_day:.1f} ordini al giorno "
               f"({'simulati' if d.origine == 'simulati' else 'Shopify'}).")
    show_avvisi(d.avvisi, only_important=True)
    st.page_link("views/risultati.py", label="Vai ai risultati", icon="📊")
