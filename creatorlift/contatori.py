"""Lettura dei contatori pubblici dei post TikTok (visualizzazioni, like, ...).

Una lettura = una riga per post in un file CSV. Per avere l'andamento ora per
ora la lettura va fatta ogni ora (vedi "Come farlo girare" in
docs/contatori-social.md). Si salvano solo i contatori: i commenti e gli utenti
che il servizio restituisce vengono scartati.

La chiave del servizio (Bright Data) non si scrive nel codice ne' nei file:
sta nella variabile d'ambiente BRIGHTDATA_API_KEY.

    export BRIGHTDATA_API_KEY="..."
    python -m creatorlift.contatori post.txt --out letture.csv

`post.txt`: un indirizzo di video TikTok per riga.
Il servizio e' di un fornitore esterno che raccoglie dati pubblici: da usare
per prove sui pilota, non come parte garantita del prodotto.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.brightdata.com/datasets/v3"
DATASET_PREDEFINITO = "gd_lu702nij2f790tmv9h"  # TikTok - Posts - collect by URL
CAMPI = ["letto_alle", "post_id", "url", "account", "pubblicato_alle", "visualizzazioni", "like", "commenti",
         "condivisioni", "salvataggi", "collaborazione_a_pagamento"]


def pulisci_url(url: str) -> str:
    """Toglie quello che segue il punto interrogativo (che puo' dare errori)."""
    return url.strip().split("?")[0]


def _num(v):
    try:
        return int(float(str(v).replace(".", "").replace(",", "")) if isinstance(v, str) else v)
    except (TypeError, ValueError):
        return None


def leggi_record(rec: dict, letto_alle: str) -> dict:
    """Riga con solo i contatori (niente commenti, utenti, indirizzi dei video)."""
    condivisioni = rec.get("num_share_count")
    if condivisioni is None:
        condivisioni = rec.get("share_count")
    return {
        "letto_alle": letto_alle,
        "post_id": str(rec.get("post_id") or ""),
        "url": pulisci_url(rec.get("url") or ""),
        "account": rec.get("account_id") or "",
        "pubblicato_alle": rec.get("create_time") or "",
        "visualizzazioni": _num(rec.get("play_count")),
        "like": _num(rec.get("digg_count")),
        "commenti": _num(rec.get("comment_count")),
        "condivisioni": _num(condivisioni),
        "salvataggi": _num(rec.get("collect_count")),
        "collaborazione_a_pagamento": "paid partnership" in str(rec.get("commerce_info") or "").lower(),
    }


def _chiamata(metodo: str, url: str, chiave: str, corpo=None):
    dati = None if corpo is None else json.dumps(corpo).encode()
    req = urllib.request.Request(url, data=dati, method=metodo, headers={
        "Authorization": f"Bearer {chiave}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Il servizio ha risposto con errore {e.code}: {e.read().decode()[:300]}") from None


def scarica(urls: list[str], chiave: str, dataset: str, attesa_max: int = 600) -> list[dict]:
    """Avvia la lettura, aspetta che sia pronta e restituisce i record."""
    avvio = _chiamata("POST", f"{API}/trigger?dataset_id={dataset}&include_errors=true", chiave,
                      [{"url": pulisci_url(u)} for u in urls])
    snap = avvio["snapshot_id"]
    t0 = time.time()
    while time.time() - t0 < attesa_max:
        stato = _chiamata("GET", f"{API}/progress/{snap}", chiave)
        if stato.get("status") == "ready":
            return _chiamata("GET", f"{API}/snapshot/{snap}?format=json", chiave) or []
        if stato.get("status") == "failed":
            raise SystemExit(f"Lettura fallita (snapshot {snap}).")
        time.sleep(5)
    raise SystemExit(f"La lettura non e' finita entro {attesa_max} secondi (snapshot {snap}).")


def salva(righe: list[dict], percorso: Path):
    nuovo = not percorso.exists()
    with percorso.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPI)
        if nuovo:
            w.writeheader()
        w.writerows(righe)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("elenco", help="file di testo con un indirizzo di video TikTok per riga")
    ap.add_argument("--out", default="letture.csv")
    ap.add_argument("--dataset", default=os.environ.get("BRIGHTDATA_DATASET_ID", DATASET_PREDEFINITO))
    ap.add_argument("--da-file", help="prova senza il servizio: legge un JSON gia' scaricato")
    a = ap.parse_args(argv)
    urls = [r.strip() for r in Path(a.elenco).read_text(encoding="utf-8").splitlines()
            if r.strip() and not r.startswith("#")]
    if not urls and not a.da_file:
        sys.exit("L'elenco e' vuoto.")
    if a.da_file:
        record = json.loads(Path(a.da_file).read_text(encoding="utf-8"))
    else:
        chiave = os.environ.get("BRIGHTDATA_API_KEY")
        if not chiave:
            sys.exit("Manca la chiave: scrivi export BRIGHTDATA_API_KEY=... prima di avviare il programma.")
        record = scarica(urls, chiave, a.dataset)
    ora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    righe = [leggi_record(r, ora) for r in record if isinstance(r, dict) and r.get("post_id")]
    salva(righe, Path(a.out))
    print(f"{len(righe)} post letti su {len(urls) or len(record)}; scritto {a.out}")
    for r in righe:
        print(f"  {r['account']}: {r['visualizzazioni']} visualizzazioni, {r['like']} like")


if __name__ == "__main__":
    main()
