# Formato dei file

Tutto il codice di lettura è in `creatorlift/io_shopify.py`.

## 1. Export ordini di Shopify

**Come ottenerlo**: Shopify › *Ordini* › *Esporta* › "Tutti gli ordini" (o un intervallo di date), formato CSV. Sopra i 50 ordini Shopify manda il file per email. Va caricato senza aprirlo prima con Excel.

**Cosa sappiamo del formato** (verificato su circa 20 export reali pubblici, non ancora su un negozio italiano reale):
- una riga per **articolo**: i dati dell'ordine (`Total`, `Taxes`, `Financial Status`, `Discount Code`, `Cancelled at`, ...) sono compilati solo sulla prima riga di ogni ordine; `Name` e `Created at` si ripetono su tutte;
- intestazioni sempre in inglese, anche con il pannello in italiano; l'insieme delle colonne cambia negli anni (66-81 colonne), quindi le colonne si cercano per nome;
- date nel formato `2025-03-01 10:22:13 +0100`, nel fuso orario del negozio;
- importi con il punto decimale e due decimali;
- più codici sconto nello stesso ordine sono separati da `, `;
- gli ordini annullati si riconoscono dalla colonna `Cancelled at`, non da `Financial Status`.

**Colonne obbligatorie**: `Name`, `Created at`, `Total`, `Discount Code`, `Financial Status`.
**Colonne usate se presenti**: `Taxes`, `Cancelled at`, `Payment Method`, `Currency`, `Source`.

### Regole di lettura

| Regola | Dettaglio |
| --- | --- |
| Un ordine | identificato da numero (`Name`) e momento di creazione; per ogni campo si prende il primo valore non vuoto tra le righe dell'ordine |
| Giorno | `Created at` convertito in ora italiana (Europe/Rome), poi la data |
| Mai contati | annullati (`Cancelled at` compilato), `refunded`, `voided`, `expired` |
| Non contati di default | ordini con `Total` = 0 (omaggi ai creator, test con codici al 100%: gonfierebbero proprio i giorni dei post) e ordini di prova (`Payment Method` con "Bogus Gateway" o "(for testing)"); si possono reinserire dall'interfaccia |
| Contati | `paid`, `partially_refunded`, `partially_paid`, `pending` (contrassegno, bonifico), `authorized`; stati sconosciuti vengono contati con un avviso |
| Codici sconto | divisi sulla virgola, confrontati senza maiuscole e spazi, corrispondenza esatta (mai "contiene": `SARA` e `SARA10` restano distinti) |
| Più file | concatenati; un ordine presente in più export prende i dati dell'**export più recente** (quello con l'ordine più recente), non dell'ultimo caricato; lo stesso numero in due negozi diversi (diverso momento di creazione) resta due ordini |
| Giorni senza ordini | aggiunti con zero ordini, dal primo all'ultimo giorno dell'export |
| Fatturato | `Total` (IVA e spedizione incluse) per giorno; `Total − Taxes` per lo scontrino medio del ROI |

### Errori riconosciuti (messaggio in italiano)

- file riaperto e salvato con Excel (separatore `;`, codifica diversa, date in altro formato);
- storico delle transazioni o elenco dei pagamenti al posto degli ordini;
- export di un'altra piattaforma (per esempio Squarespace, senza colonna `Name`);
- colonne obbligatorie mancanti;
- file vuoto, troncato o con righe dal numero di colonne sbagliato;
- nessun ordine rimasto dopo le esclusioni.

## 2. File dei post (compilato dal brand)

| Colonna | Obbligatoria | Esempi accettati |
| --- | --- | --- |
| `creator` | sì | `giulia_style`, `Giulia Rossi` |
| `data_post` | sì | `2025-02-10`, `10/02/2025`, `10/02/25`, `10-02-2025`, `10.02.2025` |
| `costo_eur` | sì | `600`, `600,00`, `600.50`, `1.200`, `1.200,50`, `1,200.50`, `€ 600`, `600 €`; vuoto = 0 |
| `codice_sconto` | no | `GIULIA10`; più codici separati da virgola, punto e virgola, `/`, `|` o a capo |

Esempio (come lo salva Excel in italiano):

```
creator;data_post;costo_eur;codice_sconto
giulia_style;10/02/2025;600,00;GIULIA10
sara_mom;20/04/2025;500,00;SARAMAMMA
marco_daily;16/03/2025;400,00;
```

- Separatore `,` o `;` (riconosciuto dalla prima riga); codifica UTF-8 o Windows (cp1252).
- Le intestazioni si confrontano senza maiuscole e con gli spazi trasformati in `_` (`Data post` va bene).
- Il **costo è del singolo post**: il costo di un creator è la somma dei suoi post. Un pacchetto pagato una volta si può scrivere sul primo post lasciando vuoti gli altri.
- Lo stesso nome scritto con maiuscole, spazi doppi o non separabili diversi diventa un solo creator.

### Pulizia e avvisi

| Situazione | Cosa fa l'app |
| --- | --- |
| Due righe identiche | contata una volta, avviso con i numeri di riga |
| Più righe dello stesso creator nello stesso giorno | un solo post con i costi sommati, avviso |
| Creator con **esattamente le stesse date** di post | stimati insieme come `A + B`, costi sommati, avviso (il modello non può separarli) |
| Creator che pubblicano a ≤ 3 giorni di distanza | un avviso unico con i gruppi: stime più incerte |
| Post negli ultimi 14 giorni dei dati | avviso: effetto non ancora tutto visibile, rimborsi possibili |
| Post fuori dal periodo degli ordini | scartato, avviso |
| Costo totale di un creator = 0 | avviso: il ROI non si calcola |
| Codice mai usato negli ordini contati | avviso, con il codice più simile trovato negli ordini |
| Codice assegnato a più creator | avviso: gli ordini contano per ciascuno |
| Creator senza codice | avviso informativo: la stima usa solo l'andamento delle vendite |

### Errori

Data non valida (anche anni come `3025`), importo non numerico o negativo, nome del creator mancante, colonne mancanti o ripetute, righe con più valori che colonne (tipico: `500,50` in un file separato da virgole). Il messaggio indica la riga come la vede Excel (riga 1 = intestazione), anche se ci sono righe vuote.

## 3. File delle promozioni (facoltativo)

Due forme:

```
data_inizio;data_fine;descrizione
04/01/2025;10/01/2025;saldi invernali
28/11/2025;01/12/2025;black friday
```

oppure una colonna `data` con un giorno per riga. Stessi formati di data del file dei post. Se manca, il modello non usa la variabile promozioni.

## 4. Dati simulati

`creatorlift/simulate.py` genera 365 giorni di un negozio con:
- andamento in crescita del 25%, giorno della settimana, stagionalità annuale, 3 periodi di promozione da 7 giorni (+50% ordini), rumore giornaliero;
- 6 creator con effetto vero noto (sul giorno del post da +0% a +90%, che decade con una metà vita da 1 a 3 giorni), costi da 250 a 900 €;
- ordini con codice: il 35% degli ordini portati dal creator usa il codice; l'1% degli ordini normali usa un codice trovato su siti di coupon.

`to_shopify()` scrive gli stessi dati nel formato di Shopify (una riga per articolo, fusi orari con ora legale, IVA 22% inclusa, contrassegni, rimborsi parziali, codici in minuscolo e combinati) e aggiunge ordini che la lettura deve scartare: rimborsati, annullati, scaduti, omaggi a 0 € nei giorni dei post, ordini di prova. Il file dei post è scritto come da Excel italiano (`;`, date `gg/mm/aaaa`, importi con la virgola).
