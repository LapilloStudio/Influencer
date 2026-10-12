# Privacy: nessun dato esce dal computer

## Cosa garantisce l'app

- Nessun servizio esterno: calcoli, grafici e report sono fatti in locale.
- L'app risponde solo su `127.0.0.1`: non è raggiungibile da altri computer della rete del negozio.
- I file caricati restano in memoria nel processo dell'app (i file sopra 1 MB passano per un istante nella cartella temporanea del sistema e vengono cancellati subito).
- Il report è un unico file HTML con immagini incorporate: nessuna risorsa scaricata da Internet.

## Impostazioni (`.streamlit/config.toml`, accanto ad `app.py`)

| Opzione | Valore | Perché |
| --- | --- | --- |
| `browser.gatherUsageStats` | `false` | di default il browser invia statistiche d'uso a Streamlit |
| `server.showEmailPrompt` | `false` | al primo avvio Streamlit chiede un'email nel terminale e la invia |
| `server.address` | `127.0.0.1` | di default l'app è raggiungibile da tutta la rete |
| `server.allowedHosts` | `localhost`, `127.0.0.1` | difesa dal DNS rebinding |
| `server.headless` | `false` | apre il browser da solo |
| `server.maxUploadSize` | `100` (MB) | |
| `client.showErrorLinks` | `false` | niente link "chiedi a Google/ChatGPT" con il testo dell'errore |
| `client.showErrorDetails` | `none` | niente dettagli tecnici (che potrebbero contenere dati) |
| `client.toolbarMode` | `viewer` | |
| `client.allowedOrigins` | `[]` | nessun sito esterno può comandare l'app dentro un riquadro |
| `logger.hideWelcomeMessage` | `true` | |
| `global.developmentMode` | `false` | |
| `theme.base`, `theme.primaryColor` | `light`, `#2a78d6` | tema locale |

Il file viene letto anche se l'app si avvia da un'altra cartella.

## Controlli nel codice

- `creatorlift/privacy.py` → `problems()`: all'avvio `app.py` verifica statistiche d'uso, richiesta email, CORS, protezione XSRF, modalità sviluppo, indirizzo locale e tema non scaricato da Internet. Se qualcosa non va mostra un errore e non prosegue.
- `disable_ip_lookup()`: spegne le due funzioni con cui Streamlit può chiedere a un servizio esterno l'indirizzo IP pubblico del computer.
- Nessuna mappa, nessun grafico Plotly, nessun HTML libero: un test controlla che nel codice non compaiano `st.map`, `pydeck`, `plotly`, `unsafe_allow_html`, `st.html` o icone scaricate.
- I testi che vengono dai file del brand (nomi, codici) sono neutralizzati prima di passare a Markdown (`ui.md()`), perché un'immagine Markdown farebbe scaricare qualcosa da Internet.

## Come è stato verificato

`tests/test_e2e_browser.py` avvia l'app vera con `streamlit run` attraverso `tests/e2e/avvia_con_controllo_rete.py`, che registra ogni tentativo di connessione del processo Python verso indirizzi non locali. Poi usa l'app con Chromium: dati simulati, risultati, download del report. Il test fallisce se:
- il browser fa una richiesta a un host diverso dall'app (147 richieste osservate, tutte locali);
- Python tenta una connessione o una risoluzione DNS esterna;
- il report scaricato contiene `http://` o `https://`.

**Controprova**: con le statistiche d'uso riattivate (`STREAMLIT_BROWSER_GATHER_USAGE_STATS=true`) lo stesso controllo vede le richieste a `data.streamlit.io`. Il test quindi se ne accorge davvero.

## Limiti

- **Il file `.streamlit/config.toml` è la protezione vera.** Il controllo all'avvio ferma la pagina, ma se le statistiche vengono riattivate dall'esterno (variabile d'ambiente, configurazione dell'utente) il browser le invia comunque prima che l'app possa intervenire. Quel file non va modificato.
- La disattivazione della ricerca dell'IP pubblico avviene alla prima esecuzione della pagina: una connessione da un altro sito aperta prima di quel momento potrebbe ancora provocarla (non trasmette dati del negozio).
- Verificato su Linux con Chromium. Non ancora su Windows e macOS con altri browser.
- Le versioni sono fissate in `requirements.txt` (Streamlit 1.65.0): aggiornando Streamlit questi controlli vanno ripetuti, il test nel browser serve a questo.
