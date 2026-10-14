"""Quali brand pagano creator: lista ricavata dai post #adv raccolti con Bright Data.

Da un file JSON di post (per esempio TikTok "Discover by keyword" con #adv) si
tengono le collaborazioni a pagamento e si contano, per ogni brand citato
(@menzioni, utenti taggati, hashtag), quanti post e quanti creator diversi.
Un brand che compare con piu' creator e in piu' settimane e' un candidato
cliente: paga collaborazioni in modo ricorrente.

    python -m creatorlift.brand_adv post_adv.json --out brand_adv.csv

Si salvano solo nomi di account pubblici e numeri; testi e commenti no.
I nomi trovati sono da controllare a mano: un hashtag non e' sempre un brand.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

# hashtag che segnalano la collaborazione ma non sono un brand
SEGNALI_ADV = {"adv", "ad", "ads", "advertising", "sponsored", "sponsorizzato", "sponsorizzata", "pubblicita",
               "pubblicità", "collab", "collaborazione", "partnership", "paidpartnership", "gifted", "suppliedby",
               "prodottofornitoda"}
# hashtag troppo generici per essere un brand
GENERICI = SEGNALI_ADV | {
    "fyp", "foryou", "foryoupage", "perte", "neiperte", "viral", "virale", "tiktok", "tiktokitalia", "italia",
    "italy", "trend", "trending", "perteeee", "xyzbca", "fypage", "explore", "reels", "instagram", "comedy",
    "funny", "divertente", "ricette", "ricetta", "food", "makeup", "skincare", "beauty", "moda", "fashion",
    "outfit", "ootd", "fitness", "gym", "sport", "travel", "viaggi", "love", "amore", "famiglia", "mamma",
    "unboxing", "review", "recensione", "haul", "tutorial", "consigli", "lifestyle", "vlog", "grwm", "asmr",
    "natale", "estate", "inverno", "autunno", "primavera", "blackfriday", "sconti", "codicesconto", "offerta",
}
MENZIONE = re.compile(r"@([A-Za-z0-9_.]{2,30})")


def _lista(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            x = json.loads(v)
            return x if isinstance(x, list) else [v]
        except ValueError:
            return [s for s in re.split(r"[,\s]+", v) if s]
    return [v]


def _nome(v) -> str:
    """Nome di un account da stringa o dizionario (formati diversi tra i servizi)."""
    if isinstance(v, dict):
        for k in ("username", "user_name", "unique_id", "handle", "account_id", "nickname", "name"):
            if v.get(k):
                v = v[k]
                break
        else:
            return ""
    return str(v).strip().lstrip("@#").lower()


def hashtag(rec: dict) -> list[str]:
    tags = [_nome(h) for h in _lista(rec.get("hashtags"))]
    testo = rec.get("description") or rec.get("caption") or ""
    tags += [t.lower() for t in re.findall(r"#([\wàèéìòù]+)", testo)]
    return sorted(set(t for t in tags if t))


def a_pagamento(rec: dict) -> bool:
    """Collaborazione dichiarata: etichetta della piattaforma o hashtag #adv e simili."""
    etichetta = str(rec.get("commerce_info") or rec.get("paid_partnership") or rec.get("is_paid_partnership")
                    or "").lower()
    if "paid partnership" in etichetta or etichetta == "true":
        return True
    return bool(SEGNALI_ADV & set(hashtag(rec)))


def brand_citati(rec: dict) -> set[str]:
    """Account e hashtag che possono essere il brand (escluso il creator stesso)."""
    creator = _nome(rec.get("account_id") or rec.get("profile_username") or rec.get("user_posted") or "")
    testo = rec.get("description") or rec.get("caption") or ""
    nomi = {m.lower().rstrip(".") for m in MENZIONE.findall(testo)}
    for k in ("tagged_user", "tagged_users", "mentions", "coauthor_producers"):
        nomi |= {_nome(x) for x in _lista(rec.get(k))}
    nomi |= {t for t in hashtag(rec) if t not in GENERICI and len(t) > 2}
    return {n for n in nomi if n and n != creator}


def analizza(record: list[dict], solo_regione: str | None = None) -> list[dict]:
    per_brand = defaultdict(lambda: {"post": set(), "creator": set(), "visualizzazioni": 0, "settimane": set(),
                                     "ultimo": "", "esempio": ""})
    for rec in record:
        if not isinstance(rec, dict) or not a_pagamento(rec):
            continue
        if solo_regione and str(rec.get("region") or "").upper() not in ("", solo_regione.upper()):
            continue
        creator = _nome(rec.get("account_id") or rec.get("profile_username") or "")
        data = str(rec.get("create_time") or rec.get("date_posted") or "")[:10]
        pid = str(rec.get("post_id") or rec.get("url") or id(rec))
        for b in brand_citati(rec):
            x = per_brand[b]
            x["post"].add(pid)
            if creator:
                x["creator"].add(creator)
            x["visualizzazioni"] += int(rec.get("play_count") or rec.get("views") or 0)
            if data:
                x["settimane"].add(data[:8] + str(int(data[8:10]) // 7) if len(data) == 10 else data)
                if data > x["ultimo"]:
                    x["ultimo"], x["esempio"] = data, str(rec.get("url") or "").split("?")[0]
    righe = [{"brand": b, "post_adv": len(x["post"]), "creator_diversi": len(x["creator"]),
              "settimane_diverse": len(x["settimane"]), "visualizzazioni": x["visualizzazioni"],
              "ultimo_post": x["ultimo"], "creator": ", ".join(sorted(x["creator"])), "esempio": x["esempio"]}
             for b, x in per_brand.items()]
    # prima chi lavora con piu' creator: e' il segnale di spesa ricorrente
    return sorted(righe, key=lambda r: (-r["creator_diversi"], -r["post_adv"], -r["visualizzazioni"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("json", nargs="+", help="uno o piu' file JSON di post scaricati da Bright Data")
    ap.add_argument("--out", default="brand_adv.csv")
    ap.add_argument("--regione", default="IT", help="tiene solo i post di questa regione (vuoto = tutti)")
    a = ap.parse_args(argv)
    record = []
    for f in a.json:
        dati = json.loads(Path(f).read_text(encoding="utf-8"))
        record += dati if isinstance(dati, list) else [dati]
    righe = analizza(record, a.regione or None)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["brand", "post_adv", "creator_diversi", "settimane_diverse",
                                          "visualizzazioni", "ultimo_post", "creator", "esempio"])
        w.writeheader()
        w.writerows(righe)
    pagati = sum(1 for r in record if isinstance(r, dict) and a_pagamento(r))
    print(f"{len(record)} post letti, {pagati} collaborazioni a pagamento, {len(righe)} possibili brand -> {a.out}")
    for r in righe[:15]:
        print(f"  {r['brand']}: {r['post_adv']} post, {r['creator_diversi']} creator")


if __name__ == "__main__":
    main()
