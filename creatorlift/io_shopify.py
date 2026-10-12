"""Lettura dei dati del negozio: export ordini di Shopify, post dei creator,
giorni di promozione. Produce la tabella giornaliera che usa il motore.

Formato dell'export ordini di Shopify (Ordini > Esporta > "Esporta ordini"),
verificato su export reali:
  - una riga per ARTICOLO: i campi dell'ordine (Total, Taxes, Financial Status,
    Discount Code, Cancelled at, ...) sono compilati solo sulla prima riga di
    ogni ordine; Name e Created at si ripetono su tutte;
  - intestazioni sempre in inglese, anche con il pannello in italiano;
  - date come "2025-03-01 10:22:13 +0100", nel fuso orario del negozio;
  - importi con il punto decimale, senza separatore delle migliaia;
  - gli annullati si riconoscono da "Cancelled at", non da Financial Status;
  - piu' codici sconto nello stesso ordine sono separati da ", ".

Regole applicate (decise con il titolare del progetto):
  - esclusi: annullati, rimborsati (refunded), stornati (voided), scaduti
    (expired); di default anche ordini a 0 euro (omaggi, test con codici al
    100%) e ordini di prova (pagati con "Bogus Gateway");
  - tenuti: pagati, parzialmente rimborsati, in attesa (contrassegno, bonifico);
  - scontrino medio per il ROI = (Total - Taxes) / ordini, cioe' al netto
    dell'IVA (vale sia con prezzi IVA inclusa sia esclusa).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/Rome"
MIN_DAYS = 180
MIN_ORDERS_PER_DAY = 10
EFFECT_DAYS = 14  # l'effetto di un post si misura per 14 giorni (finestre fino a 7-13)

ORDER_REQUIRED = ["Name", "Created at", "Total", "Discount Code", "Financial Status"]
EXCLUDED_STATUS = {"refunded": "rimborsati", "voided": "stornati", "expired": "scaduti"}
KEPT_STATUS = {"paid", "partially_refunded", "partially_paid", "pending", "authorized"}

EXCLUSION_LABELS = {
    "annullati": "annullati",
    "rimborsati": "rimborsati",
    "stornati": "stornati",
    "scaduti": "scaduti",
    "zero": "a 0 euro (omaggi, test con codici al 100%)",
    "prova": "di prova (Bogus Gateway)",
}


class ErroreDati(ValueError):
    """Errore nei file caricati, con un messaggio in italiano per l'utente."""


@dataclass
class Avviso:
    livello: str  # "importante" oppure "info"
    testo: str


@dataclass
class ShopData:
    """Tutto quello che serve al motore e all'interfaccia."""
    daily: pd.DataFrame          # date, orders, revenue_eur, promo, code_<creator>
    posts: pd.DataFrame          # creator, date, cost_eur
    aov: float                   # scontrino medio usato per il ROI
    aov_label: str               # come e' stato calcolato lo scontrino
    orders_with_code: dict       # creator -> ordini con il suo codice (None se non ha codice)
    codes: dict = field(default_factory=dict)        # creator -> lista dei codici
    avvisi: list = field(default_factory=list)       # lista di Avviso
    esclusi: dict = field(default_factory=dict)      # motivo -> numero di ordini tolti
    codici_non_assegnati: pd.DataFrame | None = None  # codici usati ma di nessun creator
    truth: pd.DataFrame | None = None                # solo per i dati simulati
    origine: str = "shopify"                         # "shopify" oppure "simulati"
    params: dict = field(default_factory=dict)

    @property
    def n_days(self) -> int:
        return len(self.daily)

    @property
    def orders_per_day(self) -> float:
        return float(self.daily["orders"].mean()) if len(self.daily) else 0.0


# ---------------------------------------------------------------- utilita'

def _to_bytes(src) -> bytes:
    if src is None:
        return b""
    if isinstance(src, bytes):
        return src
    if isinstance(src, (str, Path)):
        return Path(src).read_bytes()
    if hasattr(src, "getvalue"):
        return src.getvalue()
    return src.read()


def _decode(raw: bytes, nome: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252")
        except UnicodeDecodeError:
            raise ErroreDati(f"Non riesco a leggere {nome}: non e' un file CSV di testo.")


def _read_table(raw: bytes, nome: str) -> pd.DataFrame:
    """CSV compilato a mano (post, promozioni): accetta ',' o ';' come separatore,
    come lo salva Excel in italiano."""
    text = _decode(raw, nome)
    if not text.strip():
        raise ErroreDati(f"Il file {nome} e' vuoto.")
    first = text.splitlines()[0]
    sep = ";" if first.count(";") > first.count(",") else ","
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.apply(lambda s: s.str.strip())
    return df[(df != "").any(axis=1)].reset_index(drop=True)


def _parse_date_it(values: pd.Series, nome: str, colonna: str) -> pd.Series:
    """Date scritte a mano: 2025-03-01, 01/03/2025, 01-03-2025, 01.03.2025."""
    out = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"):
        missing = out.isna()
        if not missing.any():
            break
        out[missing] = pd.to_datetime(values[missing], format=fmt, errors="coerce")
    bad = out.isna() & (values != "")
    if bad.any():
        i = int(np.flatnonzero(bad.to_numpy())[0])
        raise ErroreDati(
            f"Nel file {nome}, colonna '{colonna}', riga {i + 2}: la data '{values.iloc[i]}' non e' valida. "
            "Scrivi le date come 2025-03-01 oppure 01/03/2025."
        )
    if (values == "").any():
        i = int(np.flatnonzero((values == "").to_numpy())[0])
        raise ErroreDati(f"Nel file {nome}, colonna '{colonna}', riga {i + 2}: manca la data.")
    return out


def _parse_euro(values: pd.Series, nome: str, colonna: str) -> pd.Series:
    """Importi scritti a mano: 500, 500.50, 500,50, 1.200,50, 1200 EUR, € 500."""
    s = values.str.replace("€", "", regex=False).str.replace("EUR", "", case=False, regex=False)
    s = s.str.replace(" ", "", regex=False).str.replace(" ", "", regex=False)
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    out = pd.to_numeric(s.replace("", "0"), errors="coerce")
    if out.isna().any():
        i = int(np.flatnonzero(out.isna().to_numpy())[0])
        raise ErroreDati(f"Nel file {nome}, colonna '{colonna}', riga {i + 2}: l'importo '{values.iloc[i]}' non e' un numero.")
    if (out < 0).any():
        i = int(np.flatnonzero((out < 0).to_numpy())[0])
        raise ErroreDati(f"Nel file {nome}, colonna '{colonna}', riga {i + 2}: l'importo non puo' essere negativo.")
    return out.astype(float)


def split_codes(cell) -> list[str]:
    """'GIULIA10, Spedizione' -> ['giulia10', 'spedizione'] (confronto senza maiuscole)."""
    if cell is None or (isinstance(cell, float) and np.isnan(cell)) or cell is pd.NA:
        return []
    out = []
    for tok in str(cell).replace(";", ",").split(","):
        tok = tok.strip().casefold()
        if tok and tok not in out:
            out.append(tok)
    return out


# ---------------------------------------------------------------- ordini

def _read_shopify_file(raw: bytes, nome: str) -> pd.DataFrame:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErroreDati(
            f"Il file {nome} sembra aperto e salvato di nuovo con Excel, che ne cambia il formato. "
            "Carica il file originale scaricato da Shopify, senza aprirlo prima."
        )
    if not text.strip():
        raise ErroreDati(f"Il file {nome} e' vuoto.")
    first = text.splitlines()[0]
    if first.count(";") > first.count(","):
        raise ErroreDati(
            f"Il file {nome} usa il punto e virgola come separatore: probabilmente e' stato aperto e salvato "
            "con Excel. Carica il file originale scaricato da Shopify, senza aprirlo prima."
        )
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    cols = set(df.columns)
    if {"Kind", "Gateway"} <= cols and "Lineitem quantity" not in cols:
        raise ErroreDati(
            f"{nome} e' lo storico delle transazioni, non l'elenco degli ordini. In Shopify vai su "
            "Ordini > Esporta e scegli \"Esporta ordini\"."
        )
    if "Payout ID" in cols:
        raise ErroreDati(f"{nome} e' l'elenco dei pagamenti ricevuti, non degli ordini. "
                         "In Shopify vai su Ordini > Esporta e scegli \"Esporta ordini\".")
    if "Name" not in cols and "Order ID" in cols:
        raise ErroreDati(f"{nome} non sembra un export di Shopify (manca la colonna 'Name').")
    missing = [c for c in ORDER_REQUIRED if c not in cols]
    if missing:
        raise ErroreDati(
            f"Nel file {nome} mancano le colonne: {', '.join(missing)}. Serve l'export degli ordini di "
            "Shopify (Ordini > Esporta > \"Esporta ordini\"), in formato CSV."
        )
    return df


def read_orders(files, include_zero: bool = False, include_test: bool = False):
    """Legge uno o piu' export ordini. Restituisce (ordini tenuti, esclusi, avvisi).

    `files`: lista di (nome, contenuto) oppure di contenuti (bytes, percorso,
    file caricato). Se lo stesso ordine compare in piu' file vale l'ultimo file.
    """
    if not isinstance(files, (list, tuple)):
        files = [files]
    frames, avvisi = [], []
    seen = set()
    duplicates = 0
    for k, item in enumerate(reversed(list(files))):  # l'ultimo file caricato ha la precedenza
        nome, src = item if isinstance(item, tuple) else (getattr(item, "name", f"file {len(files) - k}"), item)
        df = _read_shopify_file(_to_bytes(src), nome)
        names = set(df["Name"].unique()) - {""}
        dup = names & seen
        if dup:
            duplicates += len(dup)
            df = df[~df["Name"].isin(dup)]
        seen |= names
        frames.append(df)
    if duplicates:
        avvisi.append(Avviso("info", f"{duplicates} ordini comparivano in piu' file: contati una volta sola."))
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["Name"] != ""]
    if raw.empty:
        raise ErroreDati("Il file degli ordini non contiene nessun ordine.")

    # un ordine per riga: per ogni colonna il primo valore non vuoto
    cols = [c for c in ["Name", "Created at", "Total", "Taxes", "Discount Code", "Financial Status",
                        "Cancelled at", "Payment Method", "Currency", "Source"] if c in raw.columns]
    orders = raw[cols].replace("", pd.NA).groupby("Name", sort=False).first().reset_index()

    created = pd.to_datetime(orders["Created at"], format="%Y-%m-%d %H:%M:%S %z", utc=True, errors="coerce")
    bad = created.isna()
    if bad.any():
        esempio = orders.loc[bad, "Created at"].iloc[0]
        raise ErroreDati(
            f"{int(bad.sum())} ordini hanno una data in un formato inatteso (esempio: '{esempio}'). "
            "Probabilmente il file e' stato aperto e salvato con Excel: carica il file originale di Shopify."
        )
    offsets = set(orders["Created at"].str[-5:])
    if not offsets <= {"+0100", "+0200"}:
        avvisi.append(Avviso("info", "Le date dell'export non sono nel fuso orario italiano: le ho convertite "
                                     "all'ora italiana per assegnare ogni ordine al giorno giusto."))
    orders["date"] = created.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")

    def money(col):
        if col not in orders:
            return pd.Series(0.0, index=orders.index)
        v = pd.to_numeric(orders[col].fillna("0"), errors="coerce")
        if v.isna().any():
            raise ErroreDati(f"La colonna '{col}' contiene valori che non sono importi: carica il file "
                             "originale di Shopify, senza aprirlo con Excel.")
        return v.astype(float)

    orders["total"] = money("Total")
    orders["taxes"] = money("Taxes")
    if "Taxes" not in orders:
        avvisi.append(Avviso("importante", "Nell'export manca la colonna 'Taxes': lo scontrino medio per il "
                                           "calcolo del ritorno include l'IVA, quindi il ritorno e' sovrastimato."))
    status = orders["Financial Status"].fillna("").str.strip().str.lower()
    orders["status"] = status
    cancelled = orders["Cancelled at"].notna() if "Cancelled at" in orders else pd.Series(False, index=orders.index)
    pay = orders["Payment Method"].fillna("").str.lower() if "Payment Method" in orders else pd.Series("", index=orders.index)
    is_test = pay.str.contains("bogus gateway", regex=False) | pay.str.contains("(for testing)", regex=False)

    reason = pd.Series("", index=orders.index, dtype=object)
    reason[cancelled] = "annullati"
    for st, lab in EXCLUDED_STATUS.items():
        reason[(reason == "") & (status == st)] = lab
    if not include_test:
        reason[(reason == "") & is_test] = "prova"
    if not include_zero:
        reason[(reason == "") & (orders["total"] <= 0)] = "zero"
    esclusi = {k: int((reason == k).sum()) for k in EXCLUSION_LABELS if (reason == k).any()}

    unknown = sorted(set(status[(reason == "")]) - KEPT_STATUS - {""})
    if unknown:
        avvisi.append(Avviso("info", f"Stati di pagamento non riconosciuti, ordini tenuti: {', '.join(unknown)}."))
    kept = orders[reason == ""].copy()
    if kept.empty:
        raise ErroreDati("Dopo aver tolto annullati, rimborsati e ordini a 0 euro non resta nessun ordine.")
    pending = int((kept["status"] == "pending").sum())
    if pending:
        avvisi.append(Avviso("info", f"{pending} ordini sono ancora in attesa di pagamento (contrassegno, "
                                     "bonifico): li ho contati come vendite."))
    if "Currency" in kept and kept["Currency"].nunique() > 1:
        valute = ", ".join(sorted(kept["Currency"].dropna().unique()))
        avvisi.append(Avviso("importante", f"Gli ordini sono in valute diverse ({valute}): gli importi sono sommati "
                                           "senza conversione, quindi lo scontrino medio e' approssimativo."))
    kept["codes"] = kept["Discount Code"].map(split_codes)
    kept["net"] = kept["total"] - kept["taxes"]
    return kept[["Name", "date", "total", "taxes", "net", "status", "codes"]].reset_index(drop=True), esclusi, avvisi


# ---------------------------------------------------------------- post e promozioni

def read_posts(src, nome: str = "dei post") -> pd.DataFrame:
    """Colonne: creator, data_post, costo_eur, codice_sconto (facoltativa).
    Restituisce creator, date (AAAA-MM-GG), cost_eur, codes (lista)."""
    df = _read_table(_to_bytes(src), nome)
    missing = [c for c in ("creator", "data_post", "costo_eur") if c not in df.columns]
    if missing:
        raise ErroreDati(f"Nel file {nome} mancano le colonne: {', '.join(missing)}. "
                         "Servono creator, data_post, costo_eur e, se c'e', codice_sconto.")
    if df.empty:
        raise ErroreDati(f"Il file {nome} non contiene nessun post.")
    if (df["creator"] == "").any():
        i = int(np.flatnonzero((df["creator"] == "").to_numpy())[0])
        raise ErroreDati(f"Nel file {nome}, riga {i + 2}: manca il nome del creator.")
    # stesso creator scritto con maiuscole diverse: un solo creator
    canon = {}
    for c in df["creator"]:
        canon.setdefault(c.casefold(), c)
    df["creator"] = df["creator"].map(lambda c: canon[c.casefold()])
    out = pd.DataFrame({
        "creator": df["creator"],
        "date": _parse_date_it(df["data_post"], nome, "data_post").dt.strftime("%Y-%m-%d"),
        "cost_eur": _parse_euro(df["costo_eur"], nome, "costo_eur"),
        "codes": df["codice_sconto"].map(split_codes) if "codice_sconto" in df else [[] for _ in range(len(df))],
    })
    return out.sort_values(["date", "creator"]).reset_index(drop=True)


def read_promo(src, nome: str = "delle promozioni") -> set[str]:
    """Colonne: data (un giorno per riga) oppure data_inizio e data_fine."""
    df = _read_table(_to_bytes(src), nome)
    days = set()
    if {"data_inizio", "data_fine"} <= set(df.columns):
        a = _parse_date_it(df["data_inizio"], nome, "data_inizio")
        b = _parse_date_it(df["data_fine"], nome, "data_fine")
        for i, (x, y) in enumerate(zip(a, b)):
            if y < x:
                raise ErroreDati(f"Nel file {nome}, riga {i + 2}: la data di fine viene prima di quella di inizio.")
            days |= set(pd.date_range(x, y, freq="D").strftime("%Y-%m-%d"))
    elif "data" in df.columns:
        days |= set(_parse_date_it(df["data"], nome, "data").dt.strftime("%Y-%m-%d"))
    else:
        raise ErroreDati(f"Nel file {nome} serve la colonna 'data' (un giorno per riga) oppure le colonne "
                         "'data_inizio' e 'data_fine'.")
    return days


# ---------------------------------------------------------------- tabella giornaliera

def data_warnings(daily: pd.DataFrame) -> list[Avviso]:
    out = []
    n = len(daily)
    per_day = float(daily["orders"].mean()) if n else 0.0
    if n < MIN_DAYS:
        out.append(Avviso("importante", f"Ci sono solo {n} giorni di storico (ne servono almeno {MIN_DAYS}): "
                                        "la stima sara' molto incerta."))
    if per_day < MIN_ORDERS_PER_DAY:
        out.append(Avviso("importante", f"In media ci sono {per_day:.1f} ordini al giorno (ne servono almeno "
                                        f"{MIN_ORDERS_PER_DAY}): la stima sara' molto incerta e solo i creator con "
                                        "un effetto molto forte potranno emergere."))
    return out


def _post_warnings(posts: pd.DataFrame, last_day: str) -> list[Avviso]:
    out = []
    end = pd.Timestamp(last_day)
    recent = posts[pd.to_datetime(posts["date"]) > end - pd.Timedelta(days=EFFECT_DAYS - 1)]
    for c in sorted(recent["creator"].unique()):
        out.append(Avviso("info", f"Un post di {c} e' degli ultimi {EFFECT_DAYS} giorni: il suo effetto non e' ancora "
                                  "tutto visibile e rimborsi o annullamenti di questi giorni possono ancora arrivare."))
    p = posts.assign(t=pd.to_datetime(posts["date"])).sort_values("t")
    pairs = set()
    for i, a in p.iterrows():
        for j, b in p.iterrows():
            if a.creator < b.creator and abs((a.t - b.t).days) <= 3:
                pairs.add((a.creator, b.creator))
    for a, b in sorted(pairs):
        out.append(Avviso("info", f"{a} e {b} hanno pubblicato a pochi giorni di distanza: le vendite in piu' di quei "
                                  "giorni sono difficili da dividere tra i due, e le loro stime saranno piu' incerte."))
    return out


def build_daily(orders: pd.DataFrame, posts: pd.DataFrame, promo_days=frozenset()):
    """Aggrega gli ordini per giorno, dal primo all'ultimo giorno dell'export
    (i giorni senza ordini valgono zero) e conta gli ordini con il codice di
    ciascun creator."""
    avvisi = []
    first, last = orders["date"].min(), orders["date"].max()
    dates = pd.date_range(first, last, freq="D").strftime("%Y-%m-%d")
    g = orders.groupby("date")
    daily = pd.DataFrame({"date": dates})
    daily["orders"] = daily["date"].map(g.size()).fillna(0).astype(int)
    daily["revenue_eur"] = daily["date"].map(g["total"].sum()).fillna(0.0).round(2)
    daily["revenue_net_eur"] = daily["date"].map(g["net"].sum()).fillna(0.0).round(2)
    daily["promo"] = daily["date"].isin(set(promo_days)).astype(int)

    # buchi lunghi senza ordini: probabile export incompleto
    zero = (daily["orders"] == 0).to_numpy()
    run, longest = 0, 0
    for z in zero:
        run = run + 1 if z else 0
        longest = max(longest, run)
    if longest >= 7:
        avvisi.append(Avviso("importante", f"Ci sono {longest} giorni di fila senza nessun ordine: controlla che "
                                           "l'export contenga tutti gli ordini del periodo."))

    outside = posts[(posts["date"] < first) | (posts["date"] > last)]
    if len(outside):
        quali = ", ".join(f"{r.creator} ({r.date})" for r in outside.itertuples())
        avvisi.append(Avviso("importante", f"Questi post sono fuori dal periodo degli ordini ({first} - {last}) e non "
                                           f"sono stati considerati: {quali}."))
    posts = posts.drop(outside.index).reset_index(drop=True)
    if posts.empty:
        raise ErroreDati(f"Nessun post cade nel periodo degli ordini ({first} - {last}).")

    creators = sorted(posts["creator"].unique())
    codes = {c: sorted({k for ks in posts.loc[posts.creator == c, "codes"] for k in ks}) for c in creators}
    owners = {}
    for c, ks in codes.items():
        for k in ks:
            owners.setdefault(k, []).append(c)
    for k, cs in owners.items():
        if len(cs) > 1:
            avvisi.append(Avviso("importante", f"Il codice '{k}' e' assegnato a piu' creator ({', '.join(cs)}): "
                                               "gli ordini con quel codice sono contati per ciascuno."))
    with_code = {}
    for c in creators:
        if not codes[c]:
            with_code[c] = None
            continue
        mine = set(codes[c])
        hit = orders["codes"].map(lambda ks: bool(mine.intersection(ks)))
        daily[f"code_{c}"] = daily["date"].map(orders[hit].groupby("date").size()).fillna(0).astype(int)
        with_code[c] = int(daily[f"code_{c}"].sum())
    no_code = [c for c in creators if with_code[c] is None]
    if no_code:
        avvisi.append(Avviso("info", f"Senza codice sconto: {', '.join(no_code)}. Per loro la stima si basa solo "
                                     "sull'andamento delle vendite."))

    assigned = set(owners)
    counts = pd.Series([k for ks in orders["codes"] for k in ks if k not in assigned], dtype=object).value_counts()
    unassigned = counts.rename_axis("codice").reset_index(name="ordini")

    avvisi += _post_warnings(posts, last)
    return daily, posts[["creator", "date", "cost_eur"]], codes, with_code, unassigned, avvisi


# ---------------------------------------------------------------- punti di ingresso

def load_shopify(order_files, posts_file, promo_file=None, include_zero=False, include_test=False) -> ShopData:
    orders, esclusi, avvisi = read_orders(order_files, include_zero=include_zero, include_test=include_test)
    posts = read_posts(posts_file)
    promo = read_promo(promo_file) if promo_file is not None else set()
    daily, posts, codes, with_code, unassigned, avvisi2 = build_daily(orders, posts, promo)
    net = daily["revenue_net_eur"].sum()
    aov = float(net / daily["orders"].sum())
    data = ShopData(
        daily=daily, posts=posts, aov=aov, aov_label="scontrino medio al netto dell'IVA (Total - Taxes)",
        orders_with_code=with_code, codes=codes, esclusi=esclusi, codici_non_assegnati=unassigned,
        origine="shopify",
    )
    data.avvisi = data_warnings(daily) + avvisi + avvisi2
    if promo_file is None:
        data.avvisi.append(Avviso("info", "Nessun file delle promozioni: se ci sono stati saldi o sconti generali, "
                                          "caricarli rende la stima piu' precisa."))
    return data


def from_simulation(orders_per_day: float = 20, seed: int = 1) -> ShopData:
    from creatorlift.simulate import simulate

    daily, posts, truth = simulate(orders_per_day, seed)
    with_code = {c: int(daily[f"code_{c}"].sum()) for c in sorted(posts["creator"].unique())}
    data = ShopData(
        daily=daily, posts=posts.reset_index(drop=True), aov=float(daily["revenue_eur"].sum() / daily["orders"].sum()),
        aov_label="scontrino medio dei dati simulati", orders_with_code=with_code, truth=truth, origine="simulati",
        params={"orders_per_day": orders_per_day, "seed": seed},
    )
    data.avvisi = data_warnings(daily)
    return data
