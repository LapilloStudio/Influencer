# Creator Lift

Stima quante vendite in più ha portato davvero ogni collaborazione con un creator, comprese quelle fatte senza codice sconto, con un intervallo probabile e un giudizio in parole: "si ripaga quasi certamente", "probabilmente si ripaga", "porta vendite ma non si ripaga", "nessun effetto chiaro". Pensato per piccoli brand e-commerce italiani su Shopify. Funziona anche con dati simulati in cui l'effetto vero è noto, così si controlla se il motore lo ritrova.

Tutto gira sul tuo computer: nessun file e nessun dato viene inviato altrove (vedi [Privacy](#privacy)).

La documentazione completa è in [`docs/`](docs/README.md): guida all'uso, formato dei file, metodo e validazione, privacy, architettura e registro dei lavori.

## Avvio

Serve Python 3.12 o più recente.

```
pip install -r requirements.txt
streamlit run app.py
```

Si apre il browser su `http://127.0.0.1:8501` (se la porta è occupata Streamlit usa la successiva). Per chiudere l'app: `Ctrl+C` nel terminale.

## Le pagine

### Carica dati

Due possibilità.

**File del negozio (Shopify)**
1. **Ordini**: in Shopify, *Ordini › Esporta › "Tutti gli ordini"*, formato CSV. Va caricato il file così com'è, senza aprirlo prima con Excel. Se Shopify ha mandato più file, si caricano tutti insieme.
2. **Post dei creator**: un CSV compilato dal brand, un post per riga (c'è un modello da scaricare nella pagina):

   | creator | data_post | costo_eur | codice_sconto |
   | --- | --- | --- | --- |
   | giulia_style | 10/02/2025 | 600,00 | GIULIA10 |
   | marco_daily | 16/03/2025 | 400,00 | |

   `codice_sconto` è facoltativo; più codici nella stessa cella si separano con una virgola (o vanno a capo). Le date possono essere `2025-02-10` o `10/02/2025`, gli importi `600`, `600,00`, `1.200` o `1.200,50`; va bene anche il file salvato da Excel con il punto e virgola. Il costo è quello del singolo post: per un creator si sommano i costi di tutti i suoi post. Una cella del costo vuota vale 0 (con un avviso se il totale del creator resta 0).
3. **Giorni di promozione** (facoltativo): colonne `data_inizio` e `data_fine` (oppure una colonna `data` con un giorno per riga). Saldi e Black Friday aiutano il motore a non scambiare una promozione per l'effetto di un creator.

Sotto "Ordini da contare" si può decidere se contare anche gli ordini a 0 € e quelli di prova (di default no).

**Dati simulati**: un anno di un negozio inventato con 6 creator, di cui uno senza nessun effetto. Si scelgono gli ordini al giorno e il seed (un numero che cambia il negozio).

Dopo il caricamento la pagina mostra gli avvisi importanti, per esempio se lo storico è sotto i 180 giorni o se ci sono meno di 10 ordini al giorno in media: in quei casi la stima sarà molto incerta.

### Risultati

- **Margine lordo**: cursore, predefinito 55%. Cambia solo il ritorno sull'investimento, non le vendite in più.
- **In breve**: una frase per creator, per esempio *"I 3 post di giulia_style hanno portato tra 111 e 252 ordini in più. Con un costo di 600 €, quasi certamente si sono ripagati."*
- **Per creator**: tabella con post, ordini con codice, vendite in più stimate, intervallo probabile, costo, ROI sul margine e giudizio. Un ROI sotto zero non viene mai mostrato come numero: si legge "nessun effetto rilevato".
- **Si sono ripagati?**: per ogni creator un punto con la stima del ROI, una barra con l'intervallo probabile e la linea a ROI = 1 (sopra, il costo si è ripagato).
- **Giorno per giorno**: per il creator scelto, gli ordini reali attorno a ogni post, la previsione senza il creator con la fascia di variazione normale, e la previsione con il creator.
- **Confronto con la verità** (solo con i dati simulati): effetto vero accanto alla stima e al conteggio degli ordini con codice.
- **Dettagli sui dati**: ordini non contati e perché, codici sconto usati che non appartengono a nessun creator.
- **Report per il brand**: un documento HTML in italiano semplice, pronto da stampare in PDF (A4, numeri di pagina): sintesi con i numeri della campagna e cosa suggeriamo, ritorno per creator, una pagina per creator, dati e metodo. Si apre con qualsiasi browser anche senza connessione. Esempio in `demo/report_esempio.pdf`.

## Come vengono letti i file di Shopify

L'export degli ordini ha una riga per articolo: i dati dell'ordine (totale, stato, codice sconto) sono solo sulla prima riga. Creator Lift:
- conta un ordine per numero d'ordine (colonna `Name`) e lo assegna al giorno in ora italiana;
- **non conta** gli ordini annullati (colonna `Cancelled at`), rimborsati, stornati e scaduti; di default nemmeno quelli a 0 € (omaggi ai creator, test con codici al 100%: se restassero, gonfierebbero proprio i giorni dei post) e quelli di prova (`Bogus Gateway`);
- **conta** i pagati, i parzialmente rimborsati e quelli in attesa (contrassegno, bonifico);
- riconosce i codici sconto senza badare a maiuscole e spazi, anche quando un ordine ne usa più di uno;
- calcola lo scontrino medio per il ROI **al netto dell'IVA**: `(Total − Taxes) / ordini`;
- se lo stesso ordine compare in più export, usa quello dell'export più recente (rimborsi e annullamenti arrivano dopo); due negozi con gli stessi numeri d'ordine restano distinti;
- se si carica un file sbagliato (riaperto con Excel, storico transazioni invece degli ordini, colonne mancanti, righe con troppi valori) lo dice in italiano, indicando la riga, e spiega cosa caricare.

Nel file dei post:
- righe identiche vengono contate una volta, e più righe dello stesso creator nello stesso giorno diventano un solo post con i costi sommati (con un avviso);
- se un codice sconto non compare in nessun ordine, l'app lo segnala e suggerisce il codice più simile trovato negli ordini;
- **due o più creator che hanno pubblicato sempre negli stessi giorni vengono stimati insieme** (per esempio "giulia + sara", con i costi sommati): dai dati non si può capire quante vendite ha portato ciascuno, e stimarli separati darebbe numeri falsamente precisi.

Per provare questa parte senza un negozio vero:

```
python simulate.py --orders-per-day 20 --seed 1 --out dati_simulati --shopify
```

scrive in `dati_simulati/` anche `shopify_ordini.csv`, `post_brand.csv` e `promozioni.csv`, da caricare nella pagina "Carica dati". Contengono gli stessi ordini dei dati simulati più ordini da scartare (rimborsati, annullati, omaggi, prove): la stima che ne esce è identica a quella sui dati simulati.

## Privacy

Le impostazioni sono in `.streamlit/config.toml`, accanto ad `app.py`, e valgono da qualunque cartella si avvii l'app:
- nessuna statistica d'uso inviata a Streamlit, e nessuna richiesta dell'email al primo avvio;
- l'app risponde solo su `127.0.0.1`: non è raggiungibile dagli altri computer della rete del negozio;
- nessun link a servizi esterni nei messaggi d'errore, nessuna mappa, nessun font o script scaricato da Internet;
- i file caricati restano in memoria; il report è un file autonomo.

All'avvio `app.py` controlla che queste opzioni siano attive e, se qualcuno le ha cambiate (con un'altra configurazione o una variabile d'ambiente), mostra un errore e si ferma. Il file di configurazione resta però la protezione vera: con le statistiche riattivate dall'esterno il browser le invierebbe comunque, quindi quel file non va modificato.

Il test `tests/test_e2e_browser.py` avvia l'app vera, la usa con Chromium (dati simulati, risultati, download del report) e verifica che né il browser né Python facciano richieste fuori da questo computer. Come controprova, con le statistiche d'uso riattivate lo stesso controllo vede le richieste a `data.streamlit.io`.

## Struttura del progetto

| File | Cosa fa |
| --- | --- |
| `app.py` | Avvio dell'app Streamlit e controllo della privacy. |
| `views/carica.py`, `views/risultati.py` | Le due pagine. |
| `creatorlift/model.py` | Il motore di stima (vedi sotto). |
| `creatorlift/simulate.py` | Il simulatore di negozi con effetto vero noto, e l'esportazione nel formato di Shopify. |
| `creatorlift/io_shopify.py` | Lettura di ordini Shopify, post e promozioni; tabella giornaliera e avvisi. |
| `creatorlift/report.py` | Tabella, frasi e grafici. |
| `creatorlift/contatori.py` | Lettura facoltativa dei contatori dei post TikTok (vedi docs/contatori-social.md). |
| `creatorlift/report_html.py`, `report_style.py` | Report per il brand (HTML autonomo, stampabile A4). |
| `creatorlift/privacy.py`, `creatorlift/ui.py` | Controlli di privacy e funzioni comuni alle pagine. |
| `estimate.py`, `simulate.py` | I comandi del prototipo, che funzionano come prima. |
| `run_tests.py` | Ripete simulazione e stima su molti negozi per 3 dimensioni (5, 20, 80 ordini al giorno). |
| `tests/` | Test automatici (pytest). |

Comandi del prototipo, invariati:

```
python simulate.py --orders-per-day 20 --seed 1 --out dati_simulati
python estimate.py dati_simulati
python run_tests.py 60
```

## Test

```
python -m pytest                 # tutti i test, circa un minuto
python -m pytest -m "not slow"   # salta i due test di calibrazione su 30 negozi
```

Verificano tra l'altro:
- su 30 negozi simulati da 20 ordini al giorno, l'intervallo al 90% contiene l'effetto vero tra l'80% e il 97% delle volte (risultato: 91%), e il creator senza effetto è giudicato utile meno del 15% delle volte (risultato: 3%);
- il motore nel pacchetto dà esattamente i numeri del prototipo originale;
- dai file nel formato Shopify si ottiene esattamente la stessa stima dei dati simulati;
- tabella e frasi non mostrano mai numeri negativi;
- l'app si usa senza errori e non fa richieste esterne.

`tests/test_e2e_browser.py` serve `playwright` e un Chromium (variabile `CREATORLIFT_CHROMIUM` per indicarne il percorso); senza, viene saltato.

## Come funziona il motore

1. Gli ordini di ogni giorno vengono spiegati con andamento di fondo, giorno della settimana, stagionalità annuale e giorni di promozione. Il metodo è una regressione di Poisson che tiene conto dei giorni più variabili del previsto.
2. Per ogni creator si aggiungono quattro "finestre" dopo ogni post: il giorno stesso, 1-2 giorni, 3-6 giorni e 7-13 giorni. Così ogni creator ha la sua forma di effetto, rapido o lento.
3. Le vendite in più di un creator sono la differenza tra gli ordini previsti con i suoi post e quelli previsti senza.
4. L'incertezza si calcola ripetendo il conto 2.000 volte con coefficienti estratti dalla loro distribuzione.

Se non c'è nessun giorno di promozione, la colonna delle promozioni (che sarebbe tutta a zero) non entra nel modello: non cambia le stime e lo rende risolvibile.

Il giudizio: "nessun effetto chiaro" se la probabilità che l'effetto sia positivo è sotto il 95%; altrimenti "si ripaga quasi certamente" se anche l'estremo basso dell'intervallo del ROI è sopra 1, "probabilmente si ripaga" se lo è la stima, "porta vendite ma non si ripaga" negli altri casi.

## Risultati dei test (60 negozi simulati per dimensione)

| Ordini al giorno | Fatturato annuo indicativo | L'effetto vero cade nell'intervallo al 90% | Creator forte (+135 ordini a 20/giorno) rilevato | Creator debole (+22-30 ordini a 20/giorno) rilevato | Creator senza effetto giudicato utile |
| --- | --- | --- | --- | --- | --- |
| 5 | circa 80.000 € | 88% | 58% delle volte | 13% | 8% |
| 20 | circa 330.000 € | 89% | 97% | 15-27% | 10% |
| 80 | circa 1,3 milioni € | 89% | 100% | 25-43% | 3% |

Su 600 negozi da 20 ordini al giorno l'intervallo contiene l'effetto vero nel 90,0% dei casi e il creator senza effetto è giudicato utile nel 4,8% dei casi, in linea con il 5% atteso: il 10% della tabella, su 60 negozi, è dovuto al caso.

Cosa dicono:
- **L'incertezza è onesta.** L'intervallo al 90% contiene l'effetto vero circa il 90% delle volte, a tutte le dimensioni.
- **In media la stima è giusta**, senza errori sistematici verso l'alto o verso il basso.
- **Con il codice sconto si sbaglia in modo prevedibile.** Per i creator forti il codice conta circa metà delle vendite vere (giulia_style: 63 ordini con codice contro 135 veri). Per il creator senza effetto il codice ne conta 13 a 20 ordini al giorno, che però vengono dai coupon trapelati.
- **Sotto circa 20 ordini al giorno il segnale è troppo debole.** Il motore vede solo i creator forti, e nemmeno sempre. I creator deboli non si distinguono dal rumore a nessuna dimensione.

## Limiti

- I dati simulati seguono le stesse ipotesi del modello. Su un negozio vero (dati pubblici) gli intervalli sono risultati troppo stretti: circa il 10% di falsi positivi invece del 5% (vedi [docs/prova-post-finti.md](docs/prova-post-finti.md)); per questo l'app, al caricamento, tara gli intervalli con 300 creator inventati sul negozio stesso.
- Due creator che pubblicano a pochi giorni di distanza non si separano bene (l'app lo segnala); se pubblicano sempre negli stessi giorni vengono stimati insieme.
- Con meno di un anno di dati la stagionalità annuale si confonde con l'andamento di fondo e può assorbire parte dell'effetto dei creator.
- L'export di Shopify è una fotografia: rimborsi e annullamenti degli ultimi giorni possono ancora arrivare (l'app avvisa per i post delle ultime due settimane).
- Il ROI usa lo scontrino medio di tutto il negozio; gli ordini portati dai creator, spesso scontati, possono valere meno.
- Il costo del creator è a forfait, senza prodotti regalati o spedizioni.
- Non usa ancora segnali esterni come ricerche del nome del brand, traffico diretto o sondaggio post-acquisto, che possono rendere la stima più precisa.
