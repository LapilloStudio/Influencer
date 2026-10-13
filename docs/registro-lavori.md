# Registro dei lavori

Cosa è stato fatto per trasformare il prototipo del motore in un'applicazione, in che ordine, con quali decisioni. Tutto è sul branch `claude/sweet-mccarthy-hgk2xy`.

## Punto di partenza

Quattro file: `simulate.py` (negozio simulato con effetto vero noto), `estimate.py` (motore), `run_tests.py` (validazione), `README.md`. Regola concordata: **il metodo statistico non si cambia senza chiedere**.

## Passi

| Passo | Commit | Cosa |
| --- | --- | --- |
| 0 | `7086e5a` | File originali nel repository, senza modifiche. `run_tests.py 60` riproduce il README al decimale. |
| 1 | `4c03121`, `b55ad14` | Motore nel pacchetto `creatorlift/`, comandi del prototipo invariati, test pytest. Revisione indipendente e correzioni. |
| 2 | `29ef33d` | Lettura dell'export Shopify, dei post e delle promozioni; generatore di export Shopify dai dati simulati. |
| 3 | `20081d9` | Tabella, frasi, grafici e report HTML in italiano. |
| 4 | `e2fabb1` | App Streamlit con le due pagine, impostazioni di privacy, test dell'interfaccia e nel browser. |
| 5 | `753eefe` | README con avvio e pagine. |
| — | `50d83d2` | Correzioni dalla revisione indipendente della lettura dei file. |

Dopo ogni passo sono stati eseguiti i test e `run_tests.py 30`, che ha sempre dato gli stessi numeri del prototipo.

## Decisioni prese con il titolare del progetto

- **Scontrino medio per il ROI = (Total − Taxes) / ordini**, cioè netto IVA. `Total` include IVA e spedizione e gonfierebbe il ROI; `Subtotal` nei negozi italiani include l'IVA.
- **Esclusi di default anche gli ordini a 0 € e quelli di prova**, oltre ad annullati, rimborsati, stornati e scaduti. Si possono reinserire dall'interfaccia, e l'app dice sempre quanti ne ha tolti.
- Report in HTML (stampabile in PDF), grafici in matplotlib (un solo codice per app e report, funziona senza rete).

## Verifiche fatte

- **Calibrazione su 600 negozi** (20 ordini al giorno): copertura 90,0%, falsi positivi 4,8%. Ha smentito un'osservazione fatta all'inizio ("falsi positivi al doppio del nominale", basata sul 10% del README): era rumore dovuto ai soli 60 negozi.
- **Formato reale dell'export Shopify**: studiato su circa 20 export pubblici da agenti indipendenti, con un secondo agente che cercava di smentire ogni affermazione. Ne sono venute le regole: una riga per articolo, annullati da `Cancelled at`, fusi orari, codici multipli, file salvati da Excel.
- **Privacy di Streamlit**: lette nel codice di Streamlit 1.65 tutte le richieste di rete possibili (statistiche, email al primo avvio, ricerca dell'IP pubblico, icone, mappe), poi verificato con l'app vera in Chromium e con una controprova.
- **Dai file Shopify alla stima**: i dati simulati scritti nel formato di Shopify, con ordini da scartare, danno esattamente la stessa stima dei dati simulati.

## Revisioni indipendenti

Due revisioni con agenti separati: uno cercava problemi, un altro provava a smentirli riproducendoli.

**Passo 1** (motore nel pacchetto), problemi confermati e corretti:
- i grafici degli altri creator andavano in errore se il giorno di un post aveva zero ordini;
- creator con nomi simili (`giulia` e `giulia_`) venivano confusi (difetto già presente nel prototipo);
- un nome di creator sbagliato dava un grafico "senza effetto" invece di un errore;
- test della fascia di incertezza troppo deboli.

**Passo 2** (lettura dei file), 17 problemi confermati su 21, tra cui:
- **costi come `1.200` letti come 1,2 €** (ROI gonfiato fino a mille volte, senza avvisi);
- **creator con le stesse date di post**: effetto diviso a metà con intervalli falsamente stretti;
- con più export vinceva l'ultimo caricato invece del più recente, e due negozi con gli stessi numeri d'ordine si confondevano;
- codici scritti male, costi vuoti e righe ripetute senza avvisi;
- errori di pandas in inglese, numeri di riga sbagliati con righe vuote;
- decine di avvisi quasi uguali con molti creator.

## Cambiamenti che toccano la stima

Nessuno cambia il metodo; sui dati simulati i numeri restano identici al prototipo.

1. **Colonne del creator per nome esatto** invece che per prefisso (correzione di un difetto del prototipo con nomi simili).
2. **Colonna delle promozioni** inclusa solo se c'è almeno un giorno di promozione: tutta a zero rendeva il modello singolare. Stime puntuali identiche; gli intervalli cambiano di qualche ordine solo per il diverso uso dei numeri casuali.
3. **Creator con esattamente le stesse date di post stimati insieme** (`A + B`, costi sommati), perché il modello non può separarli.
4. **Taratura con i post finti** al caricamento dei dati: intervalli allargati del fattore misurato sul negozio (≥ 1).
5. **Grafico giorno per giorno**: la fascia mostrata è la variazione normale di un giorno, non solo l'incertezza dei coefficienti, perché è quella con cui si confrontano i singoli giorni.

## Fase 1 di validazione

- **Prova dei post finti su ordini reali pubblici** (`creatorlift/placebo.py`, `scripts/prova_dati_pubblici.py`): sul negozio vero il motore dà il 10% di falsi positivi invece del 5% e l'intervallo contiene lo zero solo nel 72% dei casi invece del 90%. Causa: scarti correlati da un giorno all'altro, assenti nei dati simulati. Newey-West peggiora; una taratura con i post finti sul negozio stesso funziona. Su decisione del titolare la taratura (solo per allargare) è stata **aggiunta all'app**: sul negozio reale riporta i falsi positivi dal 10-13% al 5,5-6,7% (vedi [Prova dei post finti](prova-post-finti.md)).
- **Pagina per togliere i dati personali** dall'export Shopify (`strumenti/pulisci_export_shopify.html`): si apre con un doppio clic, lavora senza connessione; verificata in Chromium (l'app legge dal file pulito gli stessi ordini dell'originale).
- **Messaggi per brand e agenzie pilota** ([Messaggi per i pilota](messaggi-pilota.md)).

## Report per il brand rifatto

Il primo report era una pagina web semplice: titoli, elenco di frasi, tabella e immagini. Tre proposte di grafica diverse (stile consulenza, editoriale, prodotto) sono state valutate da tre revisori distinti (titolare di un negozio, grafico, controllo dei numeri). Base scelta: stile consulenza, con le parti migliori delle altre due.
- Prima pagina con la risposta: numeri chiave della campagna (con intervallo), *Il punto*, *Cosa suggeriamo*.
- **Pareggio in ordini** per ogni creator e linea che confronta vendite in più, ordini con codice e pareggio.
- Grafico del ritorno con zona sotto il pareggio e giudizi sotto il nome; tabella con una sola cella "nessun effetto rilevato" per riga.
- Grafici giorno per giorno in SVG con il carattere del documento; legenda nella casella vuota con 3 post.
- A4 con intestazioni e numeri di pagina; a schermo stretto tabelle a schede e grafici scorrevoli.
- Nome del brand e autore facoltativi dall'app (mai segnaposto tra parentesi).
- Correzioni chieste dai revisori: un ritorno sotto 1 non viene mai scritto "1,0" (0,96 resta 0,96); tra i creator senza effetto chiaro prima chi è costato di più (prima l'ordine dipendeva da stime indistinguibili da zero); frasi sul codice sconto che non presentano gli ordini con codice come parte delle vendite in più.

Il metodo di stima non cambia. Unica aggiunta al motore: `total_incremental` accetta l'elenco dei creator da sommare.

## Cose da fare

- Provare l'app con **un export reale di un negozio italiano** (IVA inclusa, ordini con più codici, un annullato, un rimborso parziale) e aggiungerlo ai test.
- Provare l'app su Windows e macOS, controllando le richieste di rete dagli strumenti del browser.
- Valutare segnali esterni (ricerche del brand, traffico diretto, sondaggio post-acquisto) per stime più precise.
- Valutare uno scontrino medio specifico per gli ordini dei creator (spesso scontati).
