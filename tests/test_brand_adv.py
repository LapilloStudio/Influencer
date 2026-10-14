"""Test della lista di brand che pagano creator (creatorlift.brand_adv)."""
from creatorlift import brand_adv as B


def _post(creator, testo, tags, paid=True, data="2026-10-01", pid=None, views=1000, tagged=None):
    return {"post_id": pid or f"{creator}-{data}-{testo[:5]}", "account_id": creator, "description": testo,
            "hashtags": tags, "commerce_info": "Paid partnership" if paid else None, "create_time": data,
            "play_count": views, "region": "IT", "tagged_user": tagged, "url": f"https://t/{creator}?x=1"}


def test_brand_ricorrente_prima():
    rec = [
        _post("anna", "#adv con @brandA bellissimo", ["adv", "fyp"]),
        _post("luca", "prova @brandA #ad", ["ad"], data="2026-10-09"),
        _post("anna", "#adv #brandb", ["adv", "brandb"], data="2026-10-02"),
        _post("sara", "video normale @brandC", ["fyp"], paid=False),
    ]
    r = B.analizza(rec)
    assert r[0]["brand"] == "branda" and r[0]["creator_diversi"] == 2 and r[0]["post_adv"] == 2
    assert {x["brand"] for x in r} == {"branda", "brandb"}  # brandC: post non a pagamento
    assert all("?" not in x["esempio"] for x in r)


def test_esclusi_generici_e_creator_stesso():
    r = B.analizza([_post("anna", "#adv @anna #fyp #perte #carfax", ["adv", "fyp", "perte", "carfax"])])
    assert [x["brand"] for x in r] == ["carfax"]


def test_formati_diversi_di_tag():
    rec = _post("anna", "nuovo video", ["adv"], tagged=[{"username": "BrandD"}, "@brande"])
    assert B.brand_citati(rec) == {"brandd", "brande"}
    assert B.a_pagamento({"hashtags": None, "description": "testo #sponsorizzato"})


def test_file_reale_carfax():
    import json
    rec = [{"post_id": "7696469749902970144", "account_id": "dani.elino", "region": "IT",
            "description": "#adv Affidatevi sempre a dei professionisti… ma un CARFAX fatelo comunque #carfax ",
            "hashtags": ["adv", "carfax"], "commerce_info": "Paid partnership", "play_count": 298400,
            "create_time": "2026-10-14T10:33:30.000Z", "tagged_user": None}]
    r = B.analizza(json.loads(json.dumps(rec)))
    assert r[0]["brand"] == "carfax" and r[0]["visualizzazioni"] == 298400
