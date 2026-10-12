"""Creator Lift: avvio dell'applicazione.

    streamlit run app.py

Gira solo su questo computer: le impostazioni di privacy sono in
.streamlit/config.toml e vengono controllate qui a ogni avvio.
"""
import streamlit as st

from creatorlift.privacy import disable_ip_lookup, problems

st.set_page_config(page_title="Creator Lift", page_icon="📈", layout="wide")

disable_ip_lookup()
errori = problems(st.get_option)
if errori:
    st.error("Per sicurezza l'app non parte: alcune impostazioni potrebbero far uscire dati da questo computer. "
             "Avviala dalla cartella del progetto con `streamlit run app.py`, senza cambiare la configurazione.\n\n"
             + "\n".join(f"- {e}" for e in errori))
    st.stop()

pagine = st.navigation([
    st.Page("views/carica.py", title="Carica dati", icon="📂", default=True),
    st.Page("views/risultati.py", title="Risultati", icon="📊"),
])
pagine.run()
