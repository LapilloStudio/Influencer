# Metodo e validazione

Il metodo statistico è quello del prototipo originale e non è stato cambiato. Il codice è in `creatorlift/model.py`.

## Come si stima

1. **Ordini di ogni giorno** spiegati da: costante, andamento lineare nel tempo, giorno della settimana, stagionalità annuale (due coppie seno/coseno), giorni di promozione. Il modello è una regressione di Poisson con sovradispersione (quasi-Poisson: la varianza è stimata dai dati, `scale="X2"`).
2. **Effetto di ogni creator**: quattro finestre dopo ogni post (giorno 0, giorni 1-2, 3-6, 7-13), ciascuna con il suo coefficiente. Ogni creator ha così la sua forma di effetto, rapida o lenta.
3. **Vendite in più** di un creator = somma su tutti i giorni di (ordini previsti con i suoi post − ordini previsti con le sue finestre azzerate).
4. **Incertezza**: 2.000 estrazioni dei coefficienti dalla loro distribuzione (normale multivariata con la covarianza stimata); per ognuna si ricalcolano le vendite in più. L'intervallo probabile al 90% va dal 5° al 95° percentile.
5. **Probabilità di effetto positivo**: quota delle 2.000 estrazioni con vendite in più > 0.

Esiste anche una variante alternativa (`mode="halflife"`, decadimento con metà vita comune scelta tra 0,5 e 6 giorni) che l'app non usa.

## ROI e giudizio

- **Scontrino medio**: sui dati Shopify `(Total − Taxes) / ordini contati`, cioè netto IVA (vale con prezzi IVA inclusa ed esclusa; include la spedizione). Sui dati simulati: fatturato / ordini.
- **ROI sul margine** = vendite in più × scontrino medio × margine lordo / costo. Calcolato anche per gli estremi dell'intervallo. Il margine si cambia dall'app senza rifare la stima.
- **Giudizio** (`verdict`):
  - probabilità di effetto positivo < 95% → "nessun effetto chiaro";
  - altrimenti, ROI dell'estremo basso ≥ 1 → "si ripaga quasi certamente";
  - altrimenti, ROI stimato ≥ 1 → "probabilmente si ripaga";
  - altrimenti → "porta vendite ma non si ripaga".

Presentazione (`creatorlift/report.py`): numeri negativi mai mostrati (stima sotto zero → "nessun effetto rilevato", estremi dell'intervallo tagliati a 0), costo 0 → "costo zero", stima non calcolabile → "dati insufficienti".

## Grafico giorno per giorno

`daily_paths()` usa la stessa stima e le stesse estrazioni della tabella e restituisce per ogni giorno:
- ordini reali; previsione con tutti i post; previsione senza il creator;
- `without_lo/hi`: intervallo al 90% della previsione senza il creator (solo incertezza sui coefficienti);
- `normal_lo/hi`: intervallo al 90% degli ordini di un giorno qualsiasi senza il creator, cioè con anche la variabilità giornaliera (simulazione gamma-Poisson con varianza = scala × media, come nel modello quasi-Poisson). È la fascia mostrata nel grafico, perché è quella con cui ha senso confrontare un singolo giorno: con la prima, molti giorni normali sembrerebbero picchi.

Verificato che la somma giornaliera delle vendite in più coincide con la stima della tabella, e che sui giorni lontani dai post circa il 90% degli ordini reali cade nella fascia (un po' di più con pochi ordini al giorno, perché gli ordini sono numeri interi: circa 95% a 5 ordini al giorno).

## Risultati dei test sui negozi simulati

### `python run_tests.py 30` (30 negozi per dimensione)

| Ordini al giorno | Effetto vero nell'intervallo al 90% | Creator senza effetto giudicato utile |
| --- | --- | --- |
| 5 | 90,0% | 3,3% |
| 20 | 91,1% | 3,3% |
| 80 | 88,3% | 3,3% |

### `python run_tests.py 60` (60 negozi per dimensione, i numeri del README originale)

| Ordini al giorno | Nell'intervallo | Creator forte rilevato | Creator deboli rilevati | Senza effetto giudicato utile |
| --- | --- | --- | --- | --- |
| 5 | 88% | 58% | 13% | 8% |
| 20 | 89% | 97% | 15-27% | 10% |
| 80 | 89% | 100% | 25-43% | 3% |

Riprodotti esattamente, al decimale.

### Calibrazione su 600 negozi da 20 ordini al giorno

| Creator | Effetto vero nell'intervallo | Vero sotto l'intervallo | Vero sopra |
| --- | --- | --- | --- |
| elena_fit | 88,8% | 5,8% | 5,3% |
| fede_vlog | 90,3% | 4,2% | 5,5% |
| giulia_style | 91,3% | 4,5% | 4,2% |
| luca_tech (nessun effetto) | 89,7% | 4,7% | 5,7% |
| marco_daily | 89,0% | 5,7% | 5,3% |
| sara_mom | 90,7% | 3,2% | 6,2% |

- Copertura complessiva **90,0%**; creator senza effetto giudicato utile **4,8%** (29 su 600), contro il 5% atteso dalla soglia del 95% (test binomiale p = 0,93).
- Errore standardizzato della stima: media tra −0,15 e −0,03, deviazione standard tra 0,99 e 1,03. Nessuna distorsione apprezzabile.

**Conclusione**: sui dati simulati il motore è ben tarato. Il 10% di falsi positivi della tabella a 60 negozi è dovuto al caso (i seed 30-59 da soli danno il 17%).

### Soglie dei test automatici

Il test pytest usa i seed fissi 0-29 (copertura 91,1%, falsi positivi 3,3%), quindi è deterministico. Su 20 gruppi diversi da 30 negozi (seed 0-599) nessuno esce dall'intervallo di copertura 80-97% e uno supera il 15% di falsi positivi: con seed diversi il test potrebbe fallire per caso, non per un errore del motore.

## Cosa dicono i test

- L'intervallo al 90% contiene l'effetto vero circa il 90% delle volte, a tutte le dimensioni.
- In media la stima è giusta.
- Il solo codice sconto sbaglia in modo prevedibile: per i creator forti conta circa metà delle vendite vere; per il creator senza effetto ne conta comunque circa 13 (coupon trapelati).
- Sotto circa 20 ordini al giorno il segnale è debole: emergono solo i creator forti, e non sempre. I creator deboli non si distinguono dal rumore a nessuna dimensione.

## Limiti

- I dati simulati seguono le stesse ipotesi del modello: sui dati veri l'errore sarà più grande.
- Creator che pubblicano a pochi giorni di distanza si separano male; con date identiche vengono stimati insieme.
- Con meno di un anno di dati la stagionalità annuale si confonde con l'andamento di fondo e può assorbire parte dell'effetto.
- L'export Shopify è una fotografia: rimborsi e annullamenti recenti possono ancora arrivare.
- Il ROI usa lo scontrino medio dell'intero negozio; gli ordini portati dai creator, spesso scontati, possono valere meno.
- Il costo è a forfait, senza prodotti regalati o spedizioni.
- Non usa segnali esterni (ricerche del brand, traffico diretto, sondaggi post-acquisto).
