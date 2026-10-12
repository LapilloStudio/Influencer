"""Simula un anno di ordini di un negozio online con collaborazioni creator.

Ogni creator ha un effetto VERO noto (vendite in piu' dopo il post), cosi'
si puo' controllare se il motore di stima lo ritrova.

Uso:
    python -m creatorlift.simulate --orders-per-day 20 --seed 1 --out dati_simulati
    (oppure, come prima: python simulate.py ...)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Creator, date dei post (giorno dell'anno, 0 = 1 gennaio), effetto vero sul
# giorno del post (+40% = 0.40 ordini in piu' rispetto al normale), meta' vita
# dell'effetto in giorni, costo della collaborazione in euro.
CREATORS = [
    {"creator": "giulia_style", "posts": [40, 160, 290], "lift": 0.60, "half_life": 2.0, "cost": 600},
    {"creator": "marco_daily", "posts": [75, 215], "lift": 0.25, "half_life": 1.5, "cost": 400},
    {"creator": "sara_mom", "posts": [110, 250], "lift": 0.40, "half_life": 3.0, "cost": 500},
    {"creator": "luca_tech", "posts": [130, 305], "lift": 0.00, "half_life": 2.0, "cost": 450},
    {"creator": "elena_fit", "posts": [190], "lift": 0.90, "half_life": 1.0, "cost": 900},
    {"creator": "fede_vlog", "posts": [60, 230, 335], "lift": 0.10, "half_life": 2.0, "cost": 250},
]
PROMO_DAYS = list(range(3, 10)) + list(range(180, 187)) + list(range(326, 333))  # saldi e Black Friday
CODE_SHARE_OF_INCREMENTAL = 0.35   # quota degli ordini "portati" dal creator che usa il codice
CODE_LEAK_RATE = 0.01              # ordini normali che usano il codice trovato su siti di coupon
AOV_MEAN = 45.0                    # scontrino medio in euro
GROSS_MARGIN = 0.55                # margine lordo sul venduto


def decay_curve(days_since: np.ndarray, half_life: float) -> np.ndarray:
    out = np.where(days_since >= 0, 0.5 ** (days_since / half_life), 0.0)
    return out


def simulate(orders_per_day: float, seed: int, n_days: int = 365):
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")

    trend = 1 + 0.25 * t / n_days
    weekly = np.array([0.95, 0.92, 0.95, 1.0, 1.05, 1.12, 1.01])[dates.dayofweek]
    yearly = 1 + 0.15 * np.sin(2 * np.pi * (t - 80) / 365)
    promo = np.isin(t, PROMO_DAYS).astype(float)
    base = orders_per_day * trend * weekly * yearly * (1 + 0.5 * promo)
    base = base * np.exp(rng.normal(0, 0.08, n_days))  # rumore giornaliero non spiegato

    creator_multiplier = np.zeros(n_days)
    per_creator_expected = {}
    for c in CREATORS:
        curve = np.zeros(n_days)
        for p in c["posts"]:
            curve += decay_curve(t - p, c["half_life"])
        creator_multiplier += c["lift"] * curve
        per_creator_expected[c["creator"]] = base * c["lift"] * curve

    lam = base * (1 + creator_multiplier)
    orders = rng.poisson(lam)

    # Ordini con codice: una parte degli incrementali + un po' di "fuga" dei codici
    incremental_expected = lam - base
    share_incr = np.divide(incremental_expected, lam, out=np.zeros(n_days), where=lam > 0)
    incr_orders = rng.binomial(orders, np.clip(share_incr, 0, 1))
    organic_orders = orders - incr_orders
    code_orders_by_creator = {c["creator"]: np.zeros(n_days, dtype=int) for c in CREATORS}
    for day in range(n_days):
        if incr_orders[day] > 0 and incremental_expected[day] > 0:
            weights = np.array([per_creator_expected[c["creator"]][day] for c in CREATORS])
            weights = weights / weights.sum()
            split = rng.multinomial(incr_orders[day], weights)
            for c, k in zip(CREATORS, split):
                code_orders_by_creator[c["creator"]][day] += rng.binomial(k, CODE_SHARE_OF_INCREMENTAL)
        # codici trapelati: assegnati ai creator con post nell'anno, a caso
        leaks = rng.binomial(organic_orders[day], CODE_LEAK_RATE)
        if leaks:
            who = rng.integers(0, len(CREATORS), leaks)
            for i in who:
                code_orders_by_creator[CREATORS[i]["creator"]][day] += 1

    revenue = np.array([rng.gamma(4.0, AOV_MEAN / 4.0, n).sum() if n else 0.0 for n in orders])

    daily = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "orders": orders,
        "revenue_eur": revenue.round(2),
        "promo": promo.astype(int),
    })
    for c in CREATORS:
        daily[f"code_{c['creator']}"] = code_orders_by_creator[c["creator"]]

    posts = pd.DataFrame([
        {"creator": c["creator"], "date": dates[p].strftime("%Y-%m-%d"), "cost_eur": c["cost"] / len(c["posts"])}
        for c in CREATORS for p in c["posts"]
    ]).sort_values("date")

    truth = []
    for c in CREATORS:
        exp_incr = per_creator_expected[c["creator"]].sum()
        truth.append({
            "creator": c["creator"],
            "true_incremental_orders": round(float(exp_incr), 1),
            "orders_with_code": int(code_orders_by_creator[c["creator"]].sum()),
            "cost_eur": c["cost"],
        })
    return daily, posts, pd.DataFrame(truth)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders-per-day", type=float, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="dati_simulati")
    ap.add_argument("--shopify", action="store_true",
                    help="scrive anche i file nel formato di Shopify e del brand (ordini, post, promozioni)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    daily, posts, truth = simulate(a.orders_per_day, a.seed)
    daily.to_csv(out / "ordini_giornalieri.csv", index=False)
    posts.to_csv(out / "post_creator.csv", index=False)
    truth.to_csv(out / "verita_nascosta.csv", index=False)
    meta = {"orders_per_day": a.orders_per_day, "seed": a.seed, "aov_eur": AOV_MEAN, "gross_margin": GROSS_MARGIN}
    (out / "parametri.json").write_text(json.dumps(meta, indent=1))
    if a.shopify:
        orders_csv, posts_csv, promo_csv = to_shopify(daily, posts, a.seed)
        (out / "shopify_ordini.csv").write_text(orders_csv, encoding="utf-8")
        (out / "post_brand.csv").write_text(posts_csv, encoding="utf-8")
        (out / "promozioni.csv").write_text(promo_csv, encoding="utf-8")
    print(truth.to_string(index=False))


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Esportazione nel formato di Shopify, per provare la lettura dei file reali.
# Il simulatore qui sopra non cambia: questi file contengono esattamente gli
# stessi ordini giornalieri e gli stessi ordini con codice, piu' ordini che la
# lettura deve scartare (rimborsati, annullati, omaggi a 0 euro, prove).

CODES = {
    "giulia_style": "GIULIA10",
    "marco_daily": "MARCO15",
    "sara_mom": "SARAMAMMA",
    "luca_tech": "LUCATECH",
    "elena_fit": "ELENAFIT",
    "fede_vlog": "FEDE10",
}
SHOPIFY_COLUMNS = [
    "Name", "Email", "Financial Status", "Paid at", "Fulfillment Status", "Fulfilled at", "Accepts Marketing",
    "Currency", "Subtotal", "Shipping", "Taxes", "Total", "Discount Code", "Discount Amount", "Shipping Method",
    "Created at", "Lineitem quantity", "Lineitem name", "Lineitem price", "Lineitem compare at price",
    "Lineitem sku", "Lineitem requires shipping", "Lineitem taxable", "Lineitem fulfillment status",
    "Billing Name", "Billing City", "Billing Country", "Notes", "Cancelled at", "Payment Method",
    "Refunded Amount", "Vendor", "Id", "Tags", "Source", "Tax 1 Name", "Tax 1 Value", "Phone",
]
ORDER_LEVEL = {"Financial Status", "Paid at", "Fulfillment Status", "Fulfilled at", "Accepts Marketing", "Currency",
               "Subtotal", "Shipping", "Taxes", "Total", "Discount Code", "Discount Amount", "Shipping Method",
               "Billing Name", "Billing City", "Billing Country", "Notes", "Cancelled at", "Payment Method",
               "Refunded Amount", "Id", "Tags", "Source", "Tax 1 Name", "Tax 1 Value"}
PRODUCTS = [("Crema viso", 24.9), ("Siero notte", 32.0), ("Detergente", 14.5), ("Maschera argilla", 19.9),
            ("Kit viaggio", 39.0), ("Balsamo labbra", 7.5)]


def _stamp(ts) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S %z")


def to_shopify(daily: pd.DataFrame, posts: pd.DataFrame, seed: int = 0):
    """Restituisce (export ordini CSV, CSV dei post, CSV delle promozioni) come testo."""
    rng = np.random.default_rng(seed + 10_000)
    orders = []  # dict per ordine

    def new_order(day, total, codes, status="paid", payment="Shopify Payments", cancelled=False,
                  source="web", refunded=0.0):
        sec = int(rng.integers(7 * 3600, 23 * 3600))
        local = pd.Timestamp(day) + pd.Timedelta(seconds=sec)
        ts = local.tz_localize("Europe/Rome", nonexistent="shift_forward", ambiguous=True)
        orders.append({"ts": ts, "total": round(float(total), 2), "codes": codes, "status": status,
                       "payment": payment, "cancelled": cancelled, "source": source, "refunded": refunded})

    for row in daily.itertuples(index=False):
        n = int(row.orders)
        if n == 0:
            continue
        w = rng.gamma(4.0, 1.0, n)
        totals = np.maximum(np.round(row.revenue_eur * w / w.sum(), 2), 0.01)
        code_lists = [[] for _ in range(n)]
        i = 0
        for c, code in CODES.items():
            k = int(getattr(row, f"code_{c}", 0))
            for _ in range(k):
                shown = code.lower() if rng.random() < 0.15 else code  # chi lo scrive in minuscolo
                code_lists[i] = [shown] + (["SPEDIZIONEGRATIS"] if rng.random() < 0.05 else [])
                i += 1
        for j in range(i, n):
            if rng.random() < 0.05:
                code_lists[j] = ["BENVENUTO10"]
        perm = rng.permutation(n)
        for j in range(n):
            r = rng.random()
            status, payment, refunded = "paid", "Shopify Payments", 0.0
            if r < 0.05:
                status, payment = "pending", "Cash on Delivery (COD)"
            elif r < 0.10:
                status, refunded = "partially_refunded", round(totals[j] * 0.3, 2)
            elif r < 0.20:
                payment = "PayPal Express Checkout"
            new_order(row.date, totals[j], code_lists[perm[j]], status, payment, refunded=refunded)

    # ordini che la lettura deve scartare
    days = daily["date"].to_numpy()
    all_codes = list(CODES.values())
    for _ in range(int(len(days) * 0.6)):  # rimborsati, a volte con codice di un creator
        codes = [all_codes[rng.integers(len(all_codes))]] if rng.random() < 0.3 else []
        t = rng.gamma(4, 11.0)
        new_order(days[rng.integers(len(days))], t, codes, status="refunded", refunded=round(t, 2))
    for _ in range(int(len(days) * 0.3)):  # annullati
        st = ["voided", "refunded", "pending"][rng.integers(3)]
        new_order(days[rng.integers(len(days))], rng.gamma(4, 11.0), [], status=st, cancelled=True)
    for _ in range(5):  # scaduti
        new_order(days[rng.integers(len(days))], rng.gamma(4, 11.0), [], status="expired")
    for p in posts.itertuples(index=False):  # omaggi ai creator il giorno del post: Total 0
        for _ in range(3):
            new_order(p.date, 0.0, ["Omaggio influencer"], source="shopify_draft_order", payment="manual")
    for _ in range(4):  # prove
        new_order(days[rng.integers(len(days))], 1.0, [], payment="(for testing) Bogus Gateway")

    orders.sort(key=lambda o: o["ts"])
    rows = []
    for num, o in enumerate(orders, start=1001):
        total = o["total"]
        shipping = 4.90 if 0 < total < 50 else 0.0
        subtotal = round(max(total - shipping, 0.0), 2)
        taxes = round(total - total / 1.22, 2)
        n_items = int(rng.integers(1, 4))
        items = rng.choice(len(PRODUCTS), n_items, replace=False)
        email = f"cliente{rng.integers(1, 5000)}@example.com"
        cancelled_at = _stamp(o["ts"] + pd.Timedelta(hours=5)) if o["cancelled"] else ""
        for li, p in enumerate(items):
            name, price = PRODUCTS[p]
            r = {c: "" for c in SHOPIFY_COLUMNS}
            r.update({
                "Name": f"#{num}", "Email": email, "Created at": _stamp(o["ts"]),
                "Lineitem quantity": "1", "Lineitem name": name, "Lineitem price": f"{price:.2f}",
                "Lineitem compare at price": "", "Lineitem sku": f"SKU-{p:03d}",
                "Lineitem requires shipping": "true", "Lineitem taxable": "true",
                "Lineitem fulfillment status": "fulfilled", "Vendor": "Negozio Esempio",
            })
            if li == 0:
                r.update({
                    "Financial Status": o["status"], "Paid at": "" if o["status"] == "pending" else _stamp(o["ts"]),
                    "Fulfillment Status": "fulfilled", "Accepts Marketing": "no", "Currency": "EUR",
                    "Subtotal": f"{subtotal:.2f}", "Shipping": f"{shipping:.2f}", "Taxes": f"{taxes:.2f}",
                    "Total": f"{total:.2f}", "Discount Code": ", ".join(o["codes"]),
                    "Discount Amount": f"{round(total * 0.1, 2):.2f}" if o["codes"] else "0.00",
                    "Shipping Method": "Spedizione standard", "Billing Name": "Mario Rossi",
                    "Billing City": "Milano", "Billing Country": "IT", "Cancelled at": cancelled_at,
                    "Payment Method": o["payment"], "Refunded Amount": f"{o['refunded']:.2f}",
                    "Id": str(5_000_000_000 + num), "Source": o["source"], "Tax 1 Name": "IT IVA 22%",
                    "Tax 1 Value": f"{taxes:.2f}",
                })
            rows.append(r)
    out = pd.DataFrame(rows, columns=SHOPIFY_COLUMNS)
    # Shopify esporta dal piu' recente; le righe di un ordine restano vicine
    out["_n"] = out["Name"].str[1:].astype(int)
    out = out.sort_values("_n", ascending=False, kind="stable").drop(columns="_n")
    orders_csv = out.to_csv(index=False, lineterminator="\n")

    # post come li compilerebbe il brand in Excel (separatore ';', date e importi all'italiana)
    p = posts.copy()
    p["data_post"] = pd.to_datetime(p["date"]).dt.strftime("%d/%m/%Y")
    p["costo_eur"] = p["cost_eur"].map(lambda v: f"{v:.2f}".replace(".", ","))
    p["codice_sconto"] = p["creator"].map(CODES)
    posts_csv = p[["creator", "data_post", "costo_eur", "codice_sconto"]].to_csv(index=False, sep=";", lineterminator="\n")

    promo = daily.loc[daily["promo"] == 1, "date"].tolist()
    ranges, start, prev = [], None, None
    for d in promo:
        if start is None:
            start = prev = d
        elif (pd.Timestamp(d) - pd.Timestamp(prev)).days == 1:
            prev = d
        else:
            ranges.append((start, prev))
            start = prev = d
    if start is not None:
        ranges.append((start, prev))
    promo_csv = "data_inizio,data_fine,descrizione\n" + "".join(f"{a},{b},promozione\n" for a, b in ranges)
    return orders_csv, posts_csv, promo_csv
