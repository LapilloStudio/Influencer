# Messaggi per i brand e le agenzie pilota

Obiettivo: trovare 3-5 brand (o 1-2 agenzie) che ci diano i dati in cambio di un'analisi gratuita, per verificare lo strumento su dati veri e capire se qualcuno lo pagherebbe.

**Chi cercare**: negozi Shopify italiani con almeno 15-20 ordini al giorno (indicativamente da 250-300 mila € di fatturato annuo in su), almeno 6-12 mesi di storico e diverse collaborazioni con creator, idealmente alcune senza codice sconto. Le agenzie di influencer marketing sono un ottimo canale: hanno più brand e devono dimostrare ai clienti che le campagne rendono.

**Cosa non promettere**: numeri esatti o che "tutti i creator risulteranno efficaci". Lo strumento dà una stima con un intervallo, e con pochi ordini il risultato più frequente può essere "nessun effetto chiaro".

## Messaggio a un brand (email)

> **Oggetto:** I vostri creator vendono davvero? Analisi gratuita
>
> Ciao [nome],
>
> sto sviluppando uno strumento che stima quante vendite in più ha portato ogni collaborazione con un creator, comprese quelle che non passano dal codice sconto (chi vede il post e compra senza codice). Il risultato è un report semplice: per ogni creator, quanti ordini in più ha portato, con un margine di incertezza, e se la collaborazione si è ripagata.
>
> Cerco pochi brand per provarlo su dati veri. In cambio vi preparo il report gratis.
>
> Servirebbero tre cose:
> 1. l'export degli ordini da Shopify (ultimi 6-12 mesi);
> 2. l'elenco dei post dei creator: chi, quando, quanto è costato, eventuale codice sconto;
> 3. se ci sono stati, i periodi di saldi o promozioni.
>
> I dati dei vostri clienti non servono: vi mando una pagina che toglie dal file nomi, email e indirizzi prima che me lo inviate, direttamente sul vostro computer. I dati restano riservati e li uso solo per questa analisi; se preferite, firmiamo un accordo di riservatezza.
>
> Vi va di sentirci 15 minuti?
>
> [firma]

## Messaggio breve (LinkedIn / Instagram / WhatsApp)

> Ciao [nome], sto provando uno strumento che stima quante vendite in più porta ogni creator, anche senza codice sconto, e se la collaborazione si è ripagata. Cerco qualche brand su Shopify per testarlo: in cambio dei dati (senza info sui clienti) vi faccio il report gratis. Ti interessa?

## Messaggio a un'agenzia

> **Oggetto:** Dimostrare ai vostri clienti quanto vendono i creator
>
> Ciao [nome],
>
> lavorate con brand che vi chiedono "quanto ha venduto davvero questa campagna?". Il codice sconto ne conta solo una parte: chi vede il post e compra senza codice non compare, e i codici finiti sui siti di coupon gonfiano i numeri dei creator sbagliati.
>
> Sto sviluppando uno strumento che stima le vendite in più di ogni creator a partire dagli ordini giornalieri del negozio, con un margine di incertezza e il ritorno sulla spesa. Cerco un'agenzia con cui provarlo su 2-3 brand clienti: le analisi sono gratuite, e i report potete usarli con i vostri clienti.
>
> Vi va di parlarne?
>
> [firma]

## Cosa chiedere (da mandare a chi accetta)

1. **Export ordini** da Shopify: *Ordini › Esporta › "Tutti gli ordini"* oppure un periodo di 6-12 mesi, formato CSV. Non aprirlo con Excel prima di inviarlo.
2. **Pulizia dei dati personali**: aprire con il browser la pagina `strumenti/pulisci_export_shopify.html`, scegliere il file, scaricare il file pulito e inviare quello. Funziona anche senza connessione e il file non esce dal computer.
3. **Elenco dei post**: usare il modello che si scarica dalla pagina "Carica dati" dell'app (colonne creator, data_post, costo_eur, codice_sconto). Un post per riga; il costo è quello del singolo post.
4. **Promozioni** (facoltativo): periodi di saldi, Black Friday, sconti su tutto il sito, con data di inizio e fine.
5. Informazioni utili da annotare: margine lordo medio (per il ritorno sulla spesa), eventuali eventi particolari (uscite in TV, problemi al sito, rotture di stock).

## Prima di consegnare il report

- Eseguire la prova dei post finti sui dati del brand (`creatorlift.placebo`, con i suoi post veri nel modello) e annotare il risultato: dice quanto fidarsi degli intervalli su quel negozio.
- Controllare gli avvisi dell'app (storico corto, pochi ordini, codici non trovati, creator con le stesse date).

## Dopo il report: le domande da fare

1. I risultati hanno senso per voi? C'è qualcosa che vi sorprende o che vi sembra sbagliato?
2. Cambiereste qualcosa nelle prossime collaborazioni sulla base di questo report?
3. Lo pagheresti? Quanto, per un report come questo?
4. Ogni quanto lo vorreste: dopo ogni campagna, ogni mese, una volta all'anno?
5. Chi lo leggerebbe: il titolare, chi fa marketing, l'agenzia?

Annotare le risposte: sono loro a dire se ha senso costruire il SaaS.

## Riservatezza

Anche senza i dati dei clienti, ordini e fatturato sono informazioni riservate del brand. Conviene un accordo di riservatezza semplice (scopo dell'uso, nessuna condivisione, cancellazione dei file a fine analisi). Per un testo adatto al proprio caso, meglio farlo vedere a un professionista.
