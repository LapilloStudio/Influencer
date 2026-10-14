"""Test della lettura dei contatori dei post (creatorlift.contatori), senza rete."""
import csv

from creatorlift import contatori as C

REC = {
    "url": "https://www.tiktok.com/@dani.elino/video/7696469749902970144?is_from_webapp=1&web_id=1",
    "post_id": "7696469749902970144", "account_id": "dani.elino", "create_time": "2026-10-14T10:33:30.000Z",
    "play_count": 298400, "digg_count": 21500, "comment_count": 111, "collect_count": 1041,
    "share_count": "1573", "num_share_count": 1573, "commerce_info": "Paid partnership",
    "comments": [{"comment": "ciao", "user_handle": "Mario Rossi", "user_id": "1"}],
    "video_url": "https://example.invalid/video.mp4", "profile_biography": "bio",
}


def test_solo_contatori_senza_dati_personali():
    r = C.leggi_record(REC, "2026-10-14T13:00:00+00:00")
    assert r["visualizzazioni"] == 298400 and r["like"] == 21500 and r["condivisioni"] == 1573
    assert r["collaborazione_a_pagamento"] is True
    assert "?" not in r["url"]
    assert set(r) == set(C.CAMPI)
    assert "Mario Rossi" not in str(r) and "ciao" not in str(r)


def test_condivisioni_come_testo_e_valori_mancanti():
    r = C.leggi_record({"post_id": "1", "share_count": "1.573", "play_count": None, "commerce_info": None}, "t")
    assert r["condivisioni"] == 1573 and r["visualizzazioni"] is None
    assert r["collaborazione_a_pagamento"] is False


def test_salva_aggiunge_righe(tmp_path):
    p = tmp_path / "l.csv"
    C.salva([C.leggi_record(REC, "t1")], p)
    C.salva([C.leggi_record(REC, "t2")], p)
    righe = list(csv.DictReader(p.open(encoding="utf-8")))
    assert [r["letto_alle"] for r in righe] == ["t1", "t2"]
