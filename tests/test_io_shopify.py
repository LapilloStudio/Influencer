"""Test della lettura dei file: export Shopify, post, promozioni."""
import numpy as np
import pandas as pd
import pytest

from creatorlift.io_shopify import (
    ErroreDati, build_daily, data_warnings, from_simulation, load_shopify, read_orders, read_posts, read_promo,
    split_codes,
)
from creatorlift.model import estimate
from creatorlift.simulate import simulate, to_shopify

HEADER = ("Name,Email,Financial Status,Paid at,Currency,Subtotal,Shipping,Taxes,Total,Discount Code,"
          "Discount Amount,Created at,Lineitem quantity,Lineitem name,Lineitem price,Cancelled at,"
          "Payment Method,Refunded Amount,Id,Source\n")


def csv_bytes(rows: str) -> bytes:
    return (HEADER + rows).encode("utf-8")


# Piccolo export scritto a mano: un caso per riga.
SMALL = csv_bytes(
    # ordine su due righe: i campi dell'ordine solo sulla prima
    "#1001,a@x.it,paid,,EUR,40.00,4.90,8.10,44.90,GIULIA10,4.00,2025-03-01 10:00:00 +0100,1,Crema,20.00,,Shopify Payments,0.00,1,web\n"
    "#1001,a@x.it,,,,,,,,,,2025-03-01 10:00:00 +0100,1,Siero,20.00,,,,,\n"
    # codice in minuscolo insieme a un altro codice
    "#1002,b@x.it,partially_refunded,,EUR,30.00,0.00,5.41,30.00,\"giulia10, SPEDIZIONEGRATIS\",3.00,2025-03-01 11:00:00 +0100,1,Crema,30.00,,PayPal,10.00,2,web\n"
    # rimborsato con codice: non conta
    "#1003,c@x.it,refunded,,EUR,30.00,0.00,5.41,30.00,GIULIA10,3.00,2025-03-01 12:00:00 +0100,1,Crema,30.00,,Shopify Payments,30.00,3,web\n"
    # annullato: lo stato resta pending, conta Cancelled at
    "#1004,d@x.it,pending,,EUR,30.00,0.00,5.41,30.00,,0.00,2025-03-01 13:00:00 +0100,1,Crema,30.00,2025-03-01 15:00:00 +0100,Cash on Delivery (COD),0.00,4,web\n"
    # contrassegno in attesa: conta
    "#1005,e@x.it,pending,,EUR,20.00,0.00,3.61,20.00,MARCO15,2.00,2025-03-02 09:00:00 +0100,1,Crema,20.00,,Cash on Delivery (COD),0.00,5,web\n"
    # omaggio a 0 euro e ordine di prova: esclusi di default
    "#1006,f@x.it,paid,,EUR,0.00,0.00,0.00,0.00,Omaggio influencer,20.00,2025-03-02 10:00:00 +0100,1,Crema,20.00,,manual,0.00,6,shopify_draft_order\n"
    "#1007,g@x.it,paid,,EUR,1.00,0.00,0.18,1.00,,0.00,2025-03-02 11:00:00 +0100,1,Prova,1.00,,(for testing) Bogus Gateway,0.00,7,web\n"
    # alle 23:30 UTC del 2 marzo in Italia e' gia' il 3 marzo
    "#1008,h@x.it,paid,,EUR,25.00,0.00,4.51,25.00,,0.00,2025-03-02 23:30:00 +0000,1,Crema,25.00,,Shopify Payments,0.00,8,web\n"
    # stornato e scaduto
    "#1009,i@x.it,voided,,EUR,25.00,0.00,4.51,25.00,,0.00,2025-03-03 10:00:00 +0100,1,Crema,25.00,,Shopify Payments,0.00,9,web\n"
    "#1010,j@x.it,expired,,EUR,25.00,0.00,4.51,25.00,,0.00,2025-03-03 10:30:00 +0100,1,Crema,25.00,,Shopify Payments,0.00,10,web\n"
)
POSTS = "creator,data_post,costo_eur,codice_sconto\ngiulia,2025-03-01,500,GIULIA10\nmarco,02/03/2025,\"1.200,50\",Marco15\nanna,03/03/2025,300,\n".encode()


def test_ordini_piccolo_export():
    orders, esclusi, avvisi = read_orders([("ordini.csv", SMALL)])
    assert sorted(orders["Name"]) == ["#1001", "#1002", "#1005", "#1008"]
    assert esclusi == {"annullati": 1, "rimborsati": 1, "stornati": 1, "scaduti": 1, "zero": 1, "prova": 1}
    o = orders.set_index("Name")
    assert o.loc["#1001", "total"] == pytest.approx(44.90)  # il totale non si somma sulle righe articolo
    assert o.loc["#1001", "net"] == pytest.approx(44.90 - 8.10)
    assert o.loc["#1002", "codes"] == ["giulia10", "spedizionegratis"]
    assert o.loc["#1008", "date"] == "2025-03-03"
    assert any("in attesa" in a.testo for a in avvisi)
    assert any("fuso orario" in a.testo for a in avvisi)


def test_omaggi_e_prove_si_possono_reinserire():
    orders, esclusi, _ = read_orders([("ordini.csv", SMALL)], include_zero=True, include_test=True)
    assert {"#1006", "#1007"} <= set(orders["Name"])
    assert "zero" not in esclusi and "prova" not in esclusi


def test_tabella_giornaliera_e_codici():
    orders, _, _ = read_orders([("ordini.csv", SMALL)])
    posts = read_posts(POSTS)
    daily, p, codes, with_code, unassigned, avvisi = build_daily(orders, posts)
    assert list(daily["date"]) == ["2025-03-01", "2025-03-02", "2025-03-03"]
    assert list(daily["orders"]) == [2, 1, 1]
    assert list(daily["code_giulia"]) == [2, 0, 0]
    assert list(daily["code_marco"]) == [0, 1, 0]
    assert with_code == {"anna": None, "giulia": 2, "marco": 1}
    assert "code_anna" not in daily
    assert unassigned.to_dict("records") == [{"codice": "spedizionegratis", "ordini": 1}]
    assert list(p.columns) == ["creator", "date", "cost_eur"]
    assert p.set_index("creator").loc["marco", "cost_eur"] == pytest.approx(1200.50)
    testi = " ".join(a.testo for a in avvisi + data_warnings(daily))
    assert "Senza codice sconto: anna" in testi
    assert "solo 3 giorni" in testi and "ordini al giorno" in testi


def test_export_reale_simulato_da_la_stessa_stima():
    """Dati simulati -> file nel formato Shopify -> lettura -> stessi numeri."""
    daily, posts, _ = simulate(20, 1)
    orders_csv, posts_csv, promo_csv = to_shopify(daily, posts, seed=1)
    d = load_shopify([("ordini.csv", orders_csv.encode())], posts_csv.encode(), promo_csv.encode())
    assert (d.daily["orders"].to_numpy() == daily["orders"].to_numpy()).all()
    assert (d.daily["promo"].to_numpy() == daily["promo"].to_numpy()).all()
    for c in posts["creator"].unique():
        assert (d.daily[f"code_{c}"].to_numpy() == daily[f"code_{c}"].to_numpy()).all()
    np.testing.assert_allclose(d.daily["revenue_eur"], daily["revenue_eur"], atol=0.05)
    assert set(d.esclusi) == {"annullati", "rimborsati", "scaduti", "zero", "prova"}
    # scontrino netto IVA: circa il lordo / 1,22
    assert d.aov == pytest.approx(daily["revenue_eur"].sum() / daily["orders"].sum() / 1.22, rel=0.01)
    o1, _ = estimate(d.daily, d.posts, seed=1)
    o2, _ = estimate(daily, posts, seed=1)
    pd.testing.assert_frame_equal(o1, o2, check_exact=True)


def test_piu_file_con_ordini_ripetuti():
    a = csv_bytes("#1,a@x.it,paid,,EUR,10,0,1.8,10.00,,0,2025-03-01 10:00:00 +0100,1,X,10,,Shopify Payments,0,1,web\n"
                  "#2,a@x.it,paid,,EUR,10,0,1.8,10.00,,0,2025-03-02 10:00:00 +0100,1,X,10,,Shopify Payments,0,2,web\n")
    b = csv_bytes("#2,a@x.it,refunded,,EUR,10,0,1.8,10.00,,0,2025-03-02 10:00:00 +0100,1,X,10,,Shopify Payments,10,2,web\n"
                  "#3,a@x.it,paid,,EUR,10,0,1.8,10.00,,0,2025-03-03 10:00:00 +0100,1,X,10,,Shopify Payments,0,3,web\n")
    orders, esclusi, avvisi = read_orders([("vecchio.csv", a), ("nuovo.csv", b)])
    assert sorted(orders["Name"]) == ["#1", "#3"]  # per #2 vale il file piu' recente (rimborsato)
    assert esclusi == {"rimborsati": 1}
    assert any("piu' file" in x.testo for x in avvisi)


@pytest.mark.parametrize("content,expected", [
    ((HEADER.replace(",", ";") + "#1;a;paid;;EUR;10;0;1,8;10,00;;0;01/03/2025 10:00;1;X;10;;;0;1;web\n").encode("cp1252"),
     "Excel"),
    ((HEADER + "#1,a,paid,,EUR,10,0,1.8,10.00,,0,01/03/2025 10:00,1,X,10,,,0,1,web\n").encode(), "Excel"),
    (b"Order,Name,Kind,Gateway,Created At,Status,Amount,Currency\n#1,#1,sale,shopify_payments,x,success,10,EUR\n",
     "Esporta ordini"),
    (b"Name,Created at,Total\n#1,2025-03-01 10:00:00 +0100,10.00\n", "mancano le colonne: Discount Code, Financial Status"),
    (b"Order ID,Financial Status,Created at\n0001,PAID,2025-03-01 10:00:00 +0100\n", "non sembra un export di Shopify"),
    (b"", "vuoto"),
])
def test_errori_chiari_sui_file_sbagliati(content, expected):
    with pytest.raises(ErroreDati, match=expected):
        read_orders([("ordini.csv", content)])


def test_post_errori():
    with pytest.raises(ErroreDati, match="mancano le colonne: costo_eur"):
        read_posts(b"creator,data_post\ngiulia,2025-03-01\n")
    with pytest.raises(ErroreDati, match="riga 3: la data '31/02/2025' non e' valida"):
        read_posts(b"creator,data_post,costo_eur\ngiulia,2025-03-01,10\nmarco,31/02/2025,10\n")
    with pytest.raises(ErroreDati, match="non e' un numero"):
        read_posts(b"creator,data_post,costo_eur\ngiulia,2025-03-01,cinquecento\n")


def test_post_formati_italiani_e_maiuscole():
    p = read_posts("creator;data_post;costo_eur;codice_sconto\nGiulia;01/03/2025;€ 500,00;GIULIA10\n"
                   "giulia;15.03.2025;250;giulia10\n\n".encode("cp1252"))
    assert list(p["creator"]) == ["Giulia", "Giulia"]
    assert list(p["date"]) == ["2025-03-01", "2025-03-15"]
    assert list(p["cost_eur"]) == [500.0, 250.0]
    assert list(p["codes"]) == [["giulia10"], ["giulia10"]]


def test_promozioni():
    assert read_promo(b"data_inizio,data_fine\n2025-01-04,2025-01-06\n") == {"2025-01-04", "2025-01-05", "2025-01-06"}
    assert read_promo(b"data\n29/11/2025\n2025-12-01\n") == {"2025-11-29", "2025-12-01"}
    with pytest.raises(ErroreDati, match="fine viene prima"):
        read_promo(b"data_inizio,data_fine\n2025-01-06,2025-01-04\n")
    with pytest.raises(ErroreDati, match="serve la colonna 'data'"):
        read_promo(b"giorno\n2025-01-06\n")


def test_post_fuori_periodo_e_buchi():
    rows = "".join(
        f"#{i},a@x.it,paid,,EUR,10,0,1.8,10.00,,0,{d} 10:00:00 +0100,1,X,10,,Shopify Payments,0,{i},web\n"
        for i, d in enumerate(["2025-03-01", "2025-03-02", "2025-03-12", "2025-03-13"], start=1)
    )
    orders, _, _ = read_orders([("o.csv", csv_bytes(rows))])
    posts = read_posts(b"creator,data_post,costo_eur\ngiulia,2025-03-02,10\nmarco,2025-05-01,10\n")
    daily, p, *_ , avvisi = build_daily(orders, posts)
    assert len(daily) == 13 and daily["orders"].sum() == 4
    assert list(p["creator"]) == ["giulia"]
    testi = " ".join(a.testo for a in avvisi)
    assert "fuori dal periodo" in testi and "marco (2025-05-01)" in testi
    assert "9 giorni di fila senza nessun ordine" in testi
    with pytest.raises(ErroreDati, match="Nessun post"):
        build_daily(orders, read_posts(b"creator,data_post,costo_eur\nmarco,2025-05-01,10\n"))


def test_codice_condiviso_e_post_vicini():
    orders, _, _ = read_orders([("ordini.csv", SMALL)])
    posts = read_posts(b"creator,data_post,costo_eur,codice_sconto\ngiulia,2025-03-01,10,GIULIA10\n"
                       b"sara,2025-03-02,10,giulia10\n")
    _, _, _, with_code, _, avvisi = build_daily(orders, posts)
    assert with_code == {"giulia": 2, "sara": 2}
    testi = " ".join(a.testo for a in avvisi)
    assert "assegnato a piu' creator" in testi
    assert "giulia e sara hanno pubblicato a pochi giorni di distanza" in testi


def test_avvisi_storico_e_volume():
    long_busy = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=200).strftime("%Y-%m-%d"), "orders": 12})
    assert data_warnings(long_busy) == []
    texts = [a.testo for a in data_warnings(long_busy.assign(orders=9))]
    assert len(texts) == 1 and "9.0 ordini al giorno" in texts[0]
    texts = [a.testo for a in data_warnings(long_busy.head(179))]
    assert len(texts) == 1 and "179 giorni" in texts[0]


def test_dati_simulati():
    d = from_simulation(20, 1)
    assert d.origine == "simulati" and d.truth is not None and d.n_days == 365
    assert d.orders_with_code["giulia_style"] == int(d.daily["code_giulia_style"].sum())
    assert d.avvisi == []
    assert from_simulation(5, 1).avvisi[0].livello == "importante"


def test_split_codes():
    assert split_codes(" A10 , b20,a10 ") == ["a10", "b20"]
    assert split_codes(pd.NA) == [] and split_codes(None) == [] and split_codes("") == []
