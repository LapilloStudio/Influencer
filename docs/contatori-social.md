# Contatori dei post (visualizzazioni, like)

Facoltativo: serve per rapporti come "vendite in più ogni 1.000 visualizzazioni". Il modello di stima non ne ha bisogno.

## Cosa fa
`creatorlift/contatori.py` legge i contatori pubblici di una lista di video TikTok tramite un servizio esterno (Bright Data) e aggiunge una riga per post a un file CSV: visualizzazioni, like, commenti, condivisioni, salvataggi, data di pubblicazione e se il post è marcato "collaborazione a pagamento". Commenti e nomi degli utenti restituiti dal servizio vengono scartati.

## Come usarlo
1. Crea un account Bright Data e una chiave API (non scriverla nei file né in chat; se la mostri per sbaglio, generane una nuova).
2. Scrivi gli indirizzi dei video in `post.txt`, uno per riga.
3. Da terminale:
   ```
   export BRIGHTDATA_API_KEY="la-tua-chiave"
   python -m creatorlift.contatori post.txt --out letture.csv
   ```
4. Per avere l'andamento ora per ora, ripeti ogni ora. Su Mac o Linux con `cron` (`crontab -e`): `0 * * * * cd /percorso/Influencer && BRIGHTDATA_API_KEY=... python -m creatorlift.contatori post.txt --out letture.csv`. Il computer deve essere acceso: per una lettura affidabile 24 ore su 24 serve un server.

## Costi e limiti
- Tariffa vista sul servizio: 1,50 $ ogni 1.000 record, cioè circa 0,0015 $ a lettura di un post. 10 post letti ogni ora per 14 giorni: circa 5 $.
- Lo script è stato provato solo sul file restituito dal servizio, non con chiamate reali (la rete di sviluppo le blocca). Se le chiamate falliscono, controlla l'identificativo del dataset (`--dataset`) e gli errori mostrati.
- Il fornitore raccoglie dati pubblici senza autorizzazione della piattaforma: usalo per prove sui pilota. Prima di metterlo in un prodotto a pagamento servono le garanzie scritte e un parere legale (origine dei dati, responsabilità, GDPR).

# Quali brand pagano creator (`creatorlift/brand_adv.py`)

Serve a trovare clienti possibili con dati veri: dai post #adv raccolti si contano, per ogni brand citato, i post a pagamento, i creator diversi e le settimane diverse. Un brand con più creator e più settimane paga collaborazioni in modo ricorrente.

1. Su Bright Data: TikTok - Posts › **Discover by keyword**, parola chiave `#adv` (poi anche `adv`, `#ad`, `#collaborazione`), con un limite di record (per esempio 300, circa 0,45 $). Scarica il JSON dalla scheda Snapshots.
2. `python -m creatorlift.brand_adv post_adv.json --out brand_adv.csv` (più file insieme: elencali tutti; `--regione ""` per non filtrare l'Italia).
3. Controlla a mano la lista: un hashtag non è sempre un brand.

Si salvano solo nomi di account pubblici e numeri, non testi né commenti.
