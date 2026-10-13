# Architettura e sviluppo

## Struttura

```
app.py                      avvio Streamlit, controllo privacy, navigazione
views/carica.py             pagina "Carica dati"
views/risultati.py          pagina "Risultati"
creatorlift/
  model.py                  motore di stima (metodo del prototipo)
  simulate.py               simulatore con effetto vero noto; export nel formato Shopify
  io_shopify.py             lettura ordini/post/promozioni, tabella giornaliera, avvisi
  report.py                 tabella, frasi, grafici (app e report)
  report_html.py            report per il brand (HTML autonomo, stampabile A4)
  report_style.py           stile del report (CSS, simboli dei giudizi)
  privacy.py                controlli di privacy
  ui.py                     stato della sessione e cache per le pagine
estimate.py, simulate.py    comandi del prototipo (richiamano il pacchetto)
run_tests.py                validazione su molti negozi simulati
.streamlit/config.toml      impostazioni di privacy
tests/                      test pytest
riferimento/                riepilogo dei test del prototipo originale
```

## Flusso dei dati

```
File Shopify ─┐
File post    ─┼─ io_shopify.load_shopify() ─┐
File promo   ─┘                             ├─ ShopData ─ report.analyze() ─ (stima, Fit) ─ report.results(margine) ─┬─ tabella, frasi
simulate.simulate() ─ io_shopify.from_simulation() ┘                                                              ├─ grafici
                                                                                                                  └─ report HTML
```

`ShopData` (in `io_shopify.py`) contiene tutto quello che serve dopo la lettura:
`daily` (date, orders, revenue_eur, promo, code_<creator>), `posts` (creator, date, cost_eur), `aov` e `aov_label`, `orders_with_code`, `codes`, `avvisi`, `esclusi`, `codici_non_assegnati`, `truth` (solo dati simulati), `origine`, `params`.

## Funzioni principali

### `creatorlift/model.py`
| Funzione | Cosa fa |
| --- | --- |
| `base_design(daily)` | matrice di base: costante, trend, giorno della settimana, stagionalità, promozioni (solo se c'è almeno un giorno di promozione) |
| `fit(daily, posts, half_life)` | aggiunge le colonne dei creator e stima il GLM quasi-Poisson |
| `fit_and_draw(daily, posts, seed, mode)` | stima + 2.000 estrazioni → oggetto `Fit` |
| `estimate(daily, posts, seed, aov, margin, mode, return_fit)` | tabella per creator: vendite in più, intervallo, probabilità, costo, ROI |
| `daily_paths(fit, creator)` | previsioni giorno per giorno per i grafici |
| `verdict(row)` | giudizio in parole |
| `Fit.creator_columns(creator)` | colonne del creator per nome esatto; errore se il creator non esiste |

### `creatorlift/io_shopify.py`
| Funzione | Cosa fa |
| --- | --- |
| `read_orders(files, include_zero, include_test)` | ordini contati, esclusi per motivo, avvisi |
| `read_posts(src)` / `read_promo(src)` | file compilati a mano |
| `build_daily(orders, posts, promo_days)` | tabella giornaliera, pulizia dei post, codici, avvisi |
| `data_warnings(daily)` | avvisi su storico (< 180 giorni) e volume (< 10 ordini al giorno) |
| `load_shopify(...)` / `from_simulation(...)` | punti di ingresso → `ShopData` |
| `ErroreDati` | errore con messaggio in italiano per l'utente |

### `creatorlift/report.py`
| Funzione | Cosa fa |
| --- | --- |
| `analyze(data)` | esegue il motore una volta |
| `results(est, data, margin)` | ROI col margine scelto, giudizi, ordine per rendimento |
| `display_table(res)`, `sentence(r)`, `code_note(r)`, `truth_table(res, truth)` | testi per l'utente |
| `creator_figure(fit, data, creator)`, `roi_figure(res)`, `fig_png(fig)`, `fig_svg(fig)` | grafici (oggetti `Figure` di matplotlib, senza pyplot: sicuri da più thread); SVG con il carattere di sistema per il report |
| `html_report(data, res, fit, margin, cal=, brand=, autore=)` | report per il brand (delega a `report_html.build`) |

### `creatorlift/report_html.py`
Costruisce il report da `ShopData`, `results()` e `Fit`. Il totale della campagna viene da `model.total_incremental(fit, creator)` (stesse estrazioni delle stime per creator; i creator con dati insufficienti restano fuori). Testi generati da regole sui giudizi (`frase_totale`, `frasi_creator`, `suggerimenti`, `consiglio`, `nota_codice`), mai numeri negativi, un ritorno sotto 1 mai arrotondato a "1,0" (`fmt_roi`). Grafico del ritorno, linea "vendite in più, codice sconto e pareggio" e confronto con la verità sono in HTML/CSS (nitidi in stampa); il grafico giorno per giorno è l'SVG di matplotlib incorporato. Stampa: `@page` A4 con intestazione e "Pagina X di Y" (Chrome, Edge; Safari e Firefox stampano senza intestazioni). Le regole per schermi stretti valgono solo a schermo (`@media screen`), mai in stampa.
| `fmt_int`, `fmt_dec`, `fmt_eur`, `fmt_date` | numeri e date all'italiana |

### Interfaccia
- `app.py`: `st.set_page_config`, controllo privacy, `st.navigation` con le due pagine in `views/` (non `pages/`).
- `ui.set_data()` esegue la stima una sola volta al caricamento e la tiene in `st.session_state` (`data`, `est`, `fit`, `data_id`); il margine si applica dopo, quindi muovere il cursore è immediato.
- `ui.creator_png()` mette in cache i grafici per creator (chiave: impronta dei dati + creator).
- Il report si genera al clic del pulsante di download, con nome del brand e autore scritti nella pagina.
- `scripts/report_esempio.py` rigenera `demo/report_esempio.html` e `.pdf` (PDF con Chromium in locale).

## Test

```
python -m pytest                    # tutti (circa un minuto)
python -m pytest -m "not slow"      # senza i due test di calibrazione
python run_tests.py 30              # validazione su 30 negozi per 3 dimensioni
```

| File | Cosa verifica |
| --- | --- |
| `tests/test_model.py` | calibrazione su 30 negozi (copertura 80-97%, falsi positivi < 15%); numeri identici al prototipo originale (`fixtures/golden_originale.csv`, generato con `git show 7086e5a:estimate.py`); coerenza e fasce di `daily_paths`; casi limite (giorno del post senza ordini, nomi simili, nessuna promozione); giudizi; comandi del prototipo |
| `tests/test_io_shopify.py` | lettura di un piccolo export scritto a mano; esclusioni; fusi orari; più file; errori chiari; formati italiani; dai file Shopify simulati la stessa identica stima dei dati simulati; casi trovati in revisione (importi `1.200`, codici scritti male, righe ripetute, creator con le stesse date, ...) |
| `tests/test_report.py` | ROI uguale al motore; ordine dei creator; nessun numero negativo mostrato (tabella, frasi e testo visibile del report); niente gergo nel report; frasi e accordi singolare/plurale; formati; grafici; report autonomo; nome del brand con caratteri speciali; casi limite (un creator, nessun effetto chiaro, dati insufficienti, costo zero); ritorno sotto 1 mai "1,0" |
| `tests/test_app.py` | le pagine con `streamlit.testing` (dati simulati, file Shopify, file sbagliati, errori imprevisti), configurazione di privacy, assenza di mappe e risorse esterne |
| `tests/test_e2e_browser.py` | l'app vera in Chromium senza richieste esterne (saltato se mancano playwright o Chromium; percorso di Chromium nella variabile `CREATORLIFT_CHROMIUM`) |

Stato attuale: 102 test passati.

## Come estendere

- **Nuova colonna dell'export Shopify**: aggiungerla all'elenco `cols` in `read_orders`; le colonne si cercano per nome.
- **Nuova regola di esclusione**: in `read_orders`, assegnare un motivo in `reason` e aggiungere l'etichetta in `EXCLUSION_LABELS`.
- **Nuovo avviso**: `Avviso("importante" | "info", testo)` in `build_daily` o `_post_warnings`; gli importanti compaiono in cima alle pagine e nel report.
- **Cambiare il metodo**: solo in `model.py`. Il test `test_uguale_al_prototipo` fallirà apposta: va rigenerato il file `fixtures/golden_originale.csv` e vanno rifatti `run_tests.py` e la calibrazione.
- **Aggiornare Streamlit**: rieseguire `tests/test_e2e_browser.py` e ricontrollare le opzioni in `privacy.md`.
