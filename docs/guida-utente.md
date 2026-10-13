# Guida all'uso

## Installazione

Serve Python 3.12 o più recente (numpy e scipy non supportano versioni precedenti).

```
pip install -r requirements.txt
```

`requirements.txt` fissa le versioni con cui il progetto è stato provato (Streamlit 1.65.0, pandas 3.0.5, statsmodels 0.15.0, matplotlib 3.11.2 e altre). `playwright` serve solo per un test e si può saltare.

## Avvio

Dalla cartella del progetto:

```
streamlit run app.py
```

Il browser si apre da solo su `http://127.0.0.1:8501` (se la porta è occupata Streamlit usa la successiva). L'app non è raggiungibile da altri computer della rete. Per chiuderla: `Ctrl+C` nel terminale.

Se all'avvio compare un errore rosso che parla di impostazioni di sicurezza, qualcuno ha cambiato la configurazione di Streamlit (vedi [Privacy](privacy.md)): l'app si rifiuta di partire finché non è sistemata.

## Pagina "Carica dati"

Si sceglie da dove prendere i dati.

### File del negozio (Shopify)

1. **Ordini** (obbligatorio): da Shopify, *Ordini › Esporta › "Tutti gli ordini"*, formato CSV. Caricare il file così com'è, senza aprirlo con Excel. Si possono caricare più file insieme (per esempio export di periodi diversi).
2. **Post dei creator** (obbligatorio): CSV compilato dal brand. Il pulsante *Scarica un modello* dà un file d'esempio.
3. **Giorni di promozione** (facoltativo): saldi, Black Friday, sconti su tutto il sito. Anche qui c'è un modello.

Il formato preciso dei tre file è in [Formato dei file](formato-dati.md).

Nella sezione *Ordini da contare* si può decidere di contare anche gli ordini a 0 € e quelli di prova. Di default non si contano: annullati, rimborsati, stornati e scaduti non si contano mai.

Si preme **Analizza**. Se un file ha un problema compare un messaggio in italiano che dice quale file, quale riga e cosa fare. Se è tutto a posto si passa ai risultati.

### Dati simulati

Un anno di ordini di un negozio inventato con 6 creator dall'effetto noto (uno, `luca_tech`, non ha nessun effetto). Si sceglie:
- **Ordini al giorno**: la dimensione del negozio (20 è il valore di riferimento).
- **Seed**: un numero che genera un negozio diverso a parità di dimensione.

Serve per mostrare come funziona l'app e quanto la stima ci azzecca.

### Avvisi

Dopo il caricamento compaiono gli avvisi importanti, per esempio:
- meno di 180 giorni di storico o meno di 10 ordini al giorno in media: **la stima sarà molto incerta**;
- post fuori dal periodo degli ordini (non considerati);
- giorni di fila senza ordini (export forse incompleto);
- un codice sconto del file dei post che nessun ordine ha usato (forse scritto male: l'app suggerisce il codice più simile);
- creator con costo 0;
- creator che hanno pubblicato sempre negli stessi giorni (vengono stimati insieme).

## Pagina "Risultati"

### Margine lordo
Cursore, predefinito 55%: la parte del prezzo che resta dopo il costo della merce. Cambia solo il ritorno sull'investimento, non le vendite in più.

### In breve
Una frase per creator, ordinate da chi rende di più. Esempi:
- *"I 3 post di giulia_style hanno portato tra 111 e 252 ordini in più. Con un costo di 600 €, quasi certamente si sono ripagati."*
- *"Per i 2 post di luca_tech non si vede un effetto chiaro: le vendite in più stanno tra 0 e 58 ordini, quindi potrebbero anche essere nessuna."*

### Tabella per creator

| Colonna | Significato |
| --- | --- |
| Post | numero di post del creator |
| Ordini con codice | ordini (contati) che hanno usato il suo codice; "senza codice" se non ne ha |
| Vendite in più stimate | ordini che non ci sarebbero stati senza i suoi post, con o senza codice; "nessun effetto rilevato" se la stima è sotto zero |
| Intervallo probabile | contiene il valore vero 9 volte su 10; se parte da 0 il creator potrebbe non aver portato nulla |
| Costo | somma dei costi dei suoi post |
| ROI sul margine | euro di margine tornati per ogni euro speso: sopra 1 la collaborazione si è ripagata; mai un numero negativo |
| Giudizio | vedi sotto |

I quattro giudizi:
- **si ripaga quasi certamente**: anche nell'ipotesi più prudente il ROI è sopra 1;
- **probabilmente si ripaga**: la stima del ROI è sopra 1, ma l'intervallo scende sotto;
- **porta vendite ma non si ripaga**: l'effetto c'è, ma il ROI stimato è sotto 1;
- **nessun effetto chiaro**: non si può dire con sicurezza che abbia portato vendite.

Casi particolari: "dati insufficienti" (l'effetto non si può stimare, per esempio troppi pochi ordini attorno al post), "costo zero" e "porta vendite (costo zero)" quando il costo è 0.

### Si sono ripagati?
Per ogni creator un punto (stima del ROI) e una barra (intervallo probabile), con una linea verticale a ROI = 1. Un cerchio vuoto sullo zero vuol dire nessun effetto rilevato.

### Giorno per giorno, attorno a ogni post
Si sceglie un creator. Per ogni suo post, dalla settimana prima a tre settimane dopo:
- **punti**: ordini reali;
- **linea blu**: ordini attesi senza il creator;
- **fascia azzurra**: variazione normale da un giorno all'altro (9 giorni normali su 10 cadono lì);
- **linea arancione**: previsione che tiene conto del creator. La distanza tra arancione e blu sono le vendite in più.

### Confronto con la verità (solo dati simulati)
Effetto vero accanto alla stima, all'intervallo e agli ordini con codice, e quante volte il vero cade nell'intervallo.

### Dettagli sui dati
Quanti ordini non sono stati contati e perché, e i codici sconto usati che non appartengono a nessun creator dell'elenco (utile per scoprire codici dimenticati).

### Report per il brand
Prima di scaricarlo si possono scrivere il **nome del brand** e **chi l'ha preparato** (facoltativi: se restano vuoti, quei campi non compaiono). *Scarica il report* produce un file HTML che si apre con qualsiasi browser anche senza connessione; per un PDF: aprirlo e scegliere *Stampa › Salva come PDF* (A4). Ogni sezione inizia su una pagina nuova, con i numeri di pagina.

Cosa contiene (con 6 creator sono 10 pagine, 11 con i dati simulati):
1. **Sintesi**: quattro numeri chiave (ordini in più di tutta la campagna con il loro intervallo, spesa, margine tornato per ogni euro speso, quanti creator si sono ripagati), *Il punto* in poche frasi e *Cosa suggeriamo* (rinnovare, fare un'altra prova, rinegoziare, rivedere), dedotto dai giudizi.
2. **Si sono ripagati?**: grafico del ritorno per creator con la linea del pareggio e la tabella riassuntiva con il totale.
3. **Come leggere le schede**: un grafico d'esempio spiegato, le parole del report e i giudizi.
4. **Una pagina per creator**: frase, numeri, *pareggio* in ordini (quante vendite in più servivano per ripagare il costo), confronto tra vendite in più, ordini con codice e pareggio, grafico giorno per giorno, cosa mostra il grafico, cosa dice il codice sconto e cosa suggeriamo.
5. **Dati e metodo**: numeri di base, ordini non contati, controllo di affidabilità, come funziona, limiti.
6. Solo con i dati simulati: **confronto con la verità**.

Un esempio già pronto è in `demo/report_esempio.html` e `.pdf` (si rigenera con `python scripts/report_esempio.py`).

## Provare con file in formato Shopify senza un negozio vero

```
python simulate.py --orders-per-day 20 --seed 1 --out dati_simulati --shopify
```

Crea in `dati_simulati/` i file `shopify_ordini.csv`, `post_brand.csv` e `promozioni.csv` da caricare nella pagina "Carica dati". Contengono anche ordini da scartare (rimborsati, annullati, omaggi a 0 €, prove), come un export vero.

## Domande frequenti

**Perché le vendite in più non coincidono con gli ordini con codice?**
Il codice conta solo chi lo usa: molti comprano dopo aver visto il post senza codice, e altri usano codici trovati su siti di coupon senza aver visto il post. Sui dati simulati il codice conta circa metà delle vendite vere dei creator forti e attribuisce vendite anche al creator che non ne porta.

**Perché l'intervallo è così largo?**
Con pochi ordini al giorno il rumore normale delle vendite è grande rispetto all'effetto di un post. Sotto circa 20 ordini al giorno solo i creator con un effetto forte emergono.

**Perché due creator compaiono come "A + B"?**
Hanno pubblicato sempre negli stessi giorni: dai dati non si può capire quanto ha portato ciascuno.

**I miei dati vanno da qualche parte?**
No: vedi [Privacy](privacy.md).
