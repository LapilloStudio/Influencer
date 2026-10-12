# Creator Lift: prototipo del motore di stima

Prototipo che stima quante vendite in più ha portato davvero ogni creator, comprese quelle senza codice sconto, con un intervallo di incertezza. Funziona su dati simulati in cui l'effetto vero è noto, così si controlla se il motore lo ritrova.

## File

| File | Cosa fa |
| --- | --- |
| `simulate.py` | Crea un anno di ordini di un negozio con 6 creator. Ogni creator ha un effetto vero noto, uno ha effetto zero. Include saldi, stagionalità, giorno della settimana, rumore e codici sconto che "trapelano" su siti di coupon. |
| `estimate.py` | Il motore. Stima le vendite in più per creator, l'intervallo al 90%, la probabilità che l'effetto sia positivo, il ROI sul margine e un giudizio in parole. |
| `run_tests.py` | Ripete simulazione e stima su 60 negozi per 3 dimensioni (5, 20, 80 ordini al giorno) e misura quanto il motore ci azzecca. |
| `PROMPT_CLAUDE_CODE.md` | Il prompt da dare a Claude Code per trasformare il motore in un prototipo usabile. |

## Come si usa

```
pip install numpy pandas statsmodels
python simulate.py --orders-per-day 20 --seed 1 --out dati_simulati
python estimate.py dati_simulati
python run_tests.py 60
```

`dati_simulati/verita_nascosta.csv` contiene l'effetto vero. Il motore non lo legge, serve solo per il confronto.

## Come funziona il motore

1. Gli ordini di ogni giorno vengono spiegati con andamento di fondo, giorno della settimana, stagionalità annuale e giorni di promozione. Il metodo è una regressione di Poisson che tiene conto dei giorni più variabili del previsto.
2. Per ogni creator si aggiungono quattro "finestre" dopo ogni post: il giorno stesso, 1-2 giorni, 3-6 giorni e 7-13 giorni. Così ogni creator ha la sua forma di effetto, rapido o lento.
3. Le vendite in più di un creator sono la differenza tra gli ordini previsti con i suoi post e quelli previsti senza.
4. L'incertezza si calcola ripetendo il conto 2.000 volte con coefficienti estratti dalla loro distribuzione.

## Risultati dei test (60 negozi simulati per dimensione)

| Ordini al giorno | Fatturato annuo indicativo | L'effetto vero cade nell'intervallo al 90% | Creator forte (+135 ordini a 20/giorno) rilevato | Creator debole (+22-30 ordini a 20/giorno) rilevato | Creator senza effetto giudicato utile |
| --- | --- | --- | --- | --- | --- |
| 5 | circa 80.000 € | 88% | 58% delle volte | 13% | 8% |
| 20 | circa 330.000 € | 89% | 97% | 15-27% | 10% |
| 80 | circa 1,3 milioni € | 89% | 100% | 25-43% | 3% |

Cosa dicono:
- **L'incertezza è onesta.** L'intervallo al 90% contiene l'effetto vero circa il 90% delle volte, a tutte le dimensioni.
- **In media la stima è giusta**, senza errori sistematici verso l'alto o verso il basso.
- **Con il codice sconto si sbaglia in modo prevedibile.** Per i creator forti il codice conta circa metà delle vendite vere (giulia_style: 63 ordini con codice contro 135 veri). Per il creator senza effetto il codice ne conta 13 a 20 ordini al giorno, che però vengono dai coupon trapelati.
- **Sotto circa 20 ordini al giorno il segnale è troppo debole.** Il motore vede solo i creator forti, e nemmeno sempre. I creator deboli non si distinguono dal rumore a nessuna dimensione.

## Limiti di questo prototipo

- I dati sono simulati con le stesse ipotesi che il modello usa. Sui dati veri l'errore sarà più grande.
- Due creator che pubblicano negli stessi giorni non si separano bene.
- Non usa ancora segnali esterni come ricerche del nome del brand, traffico diretto o sondaggio post-acquisto, che possono rendere la stima più precisa.
- Il costo del creator è a forfait, senza prodotti regalati o spedizioni.
