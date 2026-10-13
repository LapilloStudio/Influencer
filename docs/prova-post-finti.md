# Prova dei post finti su dati reali

## Perché

I test sui negozi simulati dicono che il motore è ben tarato, ma il simulatore segue le stesse ipotesi del modello. Per capire come si comporta su un negozio vero serve una prova in cui l'effetto vero è noto anche con dati reali: si inventano creator con date di post a caso. Quei post non sono mai esistiti, quindi l'effetto vero è zero.

Se il motore è tarato:
- un creator finto risulta con un effetto "chiaro" (probabilità ≥ 95%) circa il **5%** delle volte;
- l'intervallo probabile al 90% contiene lo zero circa il **90%** delle volte.

## Dati

"Online Retail" (archivio UCI, licenza CC BY 4.0): tutti gli ordini di un negozio online britannico dal 1° dicembre 2010 al 9 dicembre 2011, 541.909 righe. Annullati e resi tolti, un ordine per numero di fattura.

Il negozio è chiuso il sabato e nei festivi inglesi. Il modello non può stimare un giorno della settimana sempre a zero (il coefficiente non è stimabile e gli intervalli esplodono), quindi si usano solo i 305 giorni di apertura: **65 ordini al giorno** in media. Per simulare negozi più piccoli con lo stesso andamento vero si tiene a caso una parte degli ordini (20 e 10 al giorno).

Per ogni dimensione: 100 prove × 6 creator finti con 1-3 post ciascuno = 600 creator finti. Nessun giorno di promozione indicato (come un brand che non carica il file).

Comandi (il file si scarica dal link in `scripts/prova_dati_pubblici.py`):

```
python scripts/prova_dati_pubblici.py online-retail-dataset.csv --prove 100
```

## Risultati con il motore attuale

| Negozio | Effetto "chiaro" su creator finti | Zero nell'intervallo |
| --- | --- | --- |
| vero, 65 ordini/giorno | **10,2%** (± 2,4) | **71,7%** |
| 20 ordini/giorno | 7,5% (± 2,1) | 81,0% |
| 10 ordini/giorno | 7,7% (± 2,1) | 81,8% |
| atteso | 5% | 90% |

**Sui dati veri gli intervalli sono troppo stretti**: il motore è più sicuro di quanto dovrebbe. Su un negozio come questo, circa un creator inutile su dieci verrebbe giudicato efficace.

## Causa

Gli scarti del modello sul negozio vero sono correlati da un giorno all'altro; sui dati simulati no:

| | Correlazione degli scarti a 1, 2, 3 giorni | Sovradispersione |
| --- | --- | --- |
| negozio vero | 0,26 · 0,18 · 0,11 | 3,2 |
| simulato, 20/giorno | −0,04 · 0,03 · 0,04 | 1,5 |

Le finestre del modello sommano giorni consecutivi (1-2, 3-6, 7-13). Il calcolo attuale dell'incertezza tratta i giorni come indipendenti, quindi su dati con giorni "buoni" e "cattivi" a gruppi la sottostima. Il simulatore non genera questa correlazione: per questo tutti i test erano buoni.

## Correzioni provate

### Newey-West (incertezza robusta alla correlazione): non funziona

`scripts/esperimento_newey_west.py`. Stesse stime, intervalli calcolati con Newey-West a 7 o 14 giorni.

| | Effetto "chiaro" (vero 65/g) | Zero nell'intervallo (vero 65/g) | Copertura sui simulati |
| --- | --- | --- | --- |
| attuale | 10,0% | 72,2% | 90,2% |
| Newey-West 7 giorni | 15,3% | 63,2% | 75,7% |
| Newey-West 14 giorni | 15,8% | 61,5% | 71,5% |

Gli intervalli diventano **più stretti**: con circa 300 giorni e circa 40 coefficienti, molti dei quali riguardano pochi giorni, questa formula sottostima l'incertezza. Scartata.

### Taratura con i post finti sul negozio stesso: funziona

Si fa la prova dei post finti sui dati del negozio (con i suoi post veri nel modello) e si misura di quanto l'errore è più grande di quanto il motore dichiara (deviazione standard dell'errore standardizzato, `inflation_factor`). Poi si allargano gli intervalli di quel fattore.

| Negozio | Fattore misurato | Dopo la taratura (verificata su prove diverse da quelle usate per misurare): effetto "chiaro" | zero nell'intervallo |
| --- | --- | --- | --- |
| vero, 65/g | 1,62 | 1,8% | 90,7% |
| 20/g | 1,34 | 4,0% | 89,5% |
| 10/g | 1,28-1,34 | 2,5% | 93,2% |

Sui negozi simulati (post veri nel modello) il fattore misurato è tra 0,76 e 1,01, con falsi positivi tra 1,5% e 7,1%: il motore è già tarato. La stima del fattore su un singolo negozio oscilla, quindi andrebbe usata solo per **allargare** (fattore minimo 1), mai per restringere: sui dati simulati non cambierebbe quasi nulla.

## Decisione: taratura adottata

Su decisione del titolare del progetto la taratura è stata aggiunta (solo per allargare). Come funziona nell'app:
- al caricamento dei dati si fa la prova con 50 × 6 = 300 creator finti, con i post veri nel modello (circa 15 secondi);
- il fattore misurato, se maggiore di 1, allarga l'incertezza dei coefficienti (`estimate(..., widen=k)`): intervalli, probabilità, giudizi e fasce dei grafici cambiano insieme; le stime puntuali no;
- l'app e il report dicono con una frase se e di quanto gli intervalli sono stati allargati.

Verifica sul negozio reale (`scripts/verifica_taratura.py`): fattore misurato come fa l'app, poi nuova prova con creator finti diversi.

| Negozio | Fattore | Effetto "chiaro": prima → dopo (atteso 5%) | Zero nell'intervallo: prima → dopo (atteso 90%) |
| --- | --- | --- | --- |
| vero, 65/g | 1,51 | 12,8% → 5,5% | 72,0% → 88,3% |
| 20/g | 1,25 | 9,8% → 6,2% | 79,3% → 88,5% |
| 10/g | 1,18 | 9,9% → 6,7% | 81,5% → 88,4% |

Sui dati simulati il fattore resta intorno a 1 (per esempio 0,82 → usato 1,00; 1,03), quindi i risultati praticamente non cambiano. `run_tests.py` e i test di calibrazione misurano il motore senza taratura e restano identici.

## Cosa cambia con la taratura

- **Stime puntuali**: identiche.
- **Intervalli**: più larghi sui dati veri (su questo negozio di circa il 60% a 65 ordini al giorno, del 30% a 10-20).
- **Giudizi**: meno creator con "effetto chiaro" e "si ripaga quasi certamente". Su questo negozio i falsi positivi scenderebbero dal 10% a circa il 2-4%. I creator deboli, già difficili da vedere, lo diventerebbero ancora di più.
- **Test sui simulati**: praticamente invariati (fattore ≤ 1 → nessun allargamento).
- **Tempo**: circa 300 creator finti in più per negozio, circa 15 secondi al caricamento dei dati.

## Limiti di questa prova

- Un solo negozio, britannico, del 2010-2011, che vende soprattutto ad altre aziende; chiuso il sabato (giorni tolti, quindi il tempo del modello è un po' compresso).
- I negozi più piccoli sono ottenuti togliendo ordini a caso, non sono negozi veri.
- Va ripetuta sui dati dei brand pilota: lo strumento è `creatorlift.placebo` e funziona allo stesso modo.
