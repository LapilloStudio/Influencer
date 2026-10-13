"""Report per il brand: un documento HTML autonomo, da leggere a schermo o da
stampare in PDF (A4, con numeri di pagina).

Ordine: sintesi (numeri chiave, il punto, cosa suggeriamo), si sono ripagati
(grafico e tabella), come leggere le schede, una scheda per creator, dati e
metodo, confronto con la verita' (solo per i dati simulati).

Regole dei testi (come nell'app): niente gergo statistico, "intervallo
probabile", mai un numero negativo ("nessun effetto rilevato"), i giudizi con
simbolo + testo. Nessuna risorsa esterna: caratteri di sistema, grafici SVG
incorporati, nessuno script.
"""
from __future__ import annotations

import base64
import html
import math
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd

from creatorlift import report as R
from creatorlift.io_shopify import EXCLUSION_LABELS, ShopData
from creatorlift.model import Fit, total_incremental, verdict
from creatorlift.report_style import CSS, LOGO, SYMBOLS

CERTO = "si ripaga quasi certamente"
PROB = "probabilmente si ripaga"
ZERO = "porta vendite (costo zero)"
NORIP = "porta vendite ma non si ripaga"
NESSUNO = "nessun effetto chiaro"
INSUFF = R.NOT_ENOUGH

# giudizio -> (simbolo, etichetta)
VERDETTI = {
    CERTO: ("certo", "Si ripaga quasi certamente"),
    PROB: ("prob", "Probabilmente si ripaga"),
    ZERO: ("certo", "Porta vendite (costo zero)"),
    NORIP: ("noripaga", "Porta vendite ma non si ripaga"),
    NESSUNO: ("nessuno", "Nessun effetto chiaro"),
    INSUFF: ("insuff", "Dati insufficienti"),
}
SPIEGAZIONI = {
    CERTO: "Anche il valore più basso dell'intervallo probabile copre il costo del creator.",
    PROB: "Le vendite in più ci sono quasi certamente e la stima copre il costo, ma il valore più basso "
          "dell'intervallo probabile no: potrebbe anche non bastare.",
    ZERO: "Le vendite in più ci sono quasi certamente e la collaborazione non è costata nulla.",
    NORIP: "Le vendite in più ci sono quasi certamente, ma il margine che portano non copre il costo.",
    NESSUNO: "L'effetto, se c'è, è troppo piccolo per distinguerlo dalle normali oscillazioni delle vendite. "
             "<b>Non è una bocciatura:</b> con questi dati non si può dimostrare né un effetto né la sua assenza.",
    INSUFF: "Non è stato possibile fare una stima, per esempio perché dopo il post ci sono troppi pochi giorni "
            "o ordini.",
}
RIPAGATI = {CERTO, PROB, ZERO}
CHIARI = RIPAGATI | {NORIP}          # vendite in piu' quasi certe
NUMERI = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci"]
MESI_LUNGHI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
               "ottobre", "novembre", "dicembre"]

e = html.escape


# ---------------------------------------------------------------- numeri e parole

def num(n: int, femminile: bool = False) -> str:
    """Numero in lettere fino a dieci, poi in cifre, davanti a un nome:
    "un creator", "una collaborazione", "sei creator"."""
    if n == 1:
        return "una" if femminile else "un"
    return NUMERI[n] if 0 <= n <= 10 else R.fmt_int(n)


def tutti(n: int) -> str:
    """"tutti e sei i", "tutti i 12"."""
    return f"tutti e {NUMERI[n]} i" if 2 <= n <= 10 else f"tutti i {R.fmt_int(n)}"


def fmt_roi(x: float) -> str:
    """Ritorno con un decimale; un valore sotto 1 non diventa mai '1,0'
    (1 e' il pareggio)."""
    s = R.fmt_dec(x, 1)
    return R.fmt_dec(x, 2) if x < 1 and s == "1,0" else s


def roi_range(lo, hi) -> str:
    f = lambda v: "0" if v <= 0 else fmt_roi(v)  # noqa: E731
    return f"tra {f(lo)} e {f(hi)}"


def ord_range(lo, hi) -> str:
    return R._interval(lo, hi)


def elenco(items) -> str:
    items = list(items)
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


def date_long(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {MESI_LUNGHI[d.month - 1]} {d.year}"


def date_list(days) -> str:
    days = [pd.Timestamp(d) for d in days]
    if len({d.year for d in days}) == 1:
        return elenco([f"{d.day} {R.MESI[d.month - 1]}" for d in days]) + f" {days[0].year}"
    return elenco([R.fmt_date(d) for d in days])


def css_str(s: str) -> str:
    """Testo dentro una stringa CSS (content: "..."), al sicuro anche da '</style>'."""
    return '"' + "".join(c if c.isalnum() or c in " .,:;·–-_()'&%/€+" else f"\\{ord(c):x} " for c in s) + '"'


def icon(g: str, cls: str = "vi") -> str:
    return f'<svg class="{cls}" viewBox="0 0 16 16" aria-hidden="true"><use href="#v-{VERDETTI[g][0]}"/></svg>'


def badge(g: str) -> str:
    return f'<span class="badge">{icon(g)}<span>{e(VERDETTI[g][1])}</span></span>'


def vt(g: str) -> str:
    return f'<span class="vt">{icon(g)}<span>{e(VERDETTI[g][1])}</span></span>'


def pct(v: float, vmax: float) -> str:
    return f"{max(0.0, min(1.0, v / vmax)) * 100:.2f}%"


def nice_max(v: float, steps=(0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000)):
    v = max(v, 1e-9)
    for s in steps:
        n = math.ceil(v * 1.04 / s)
        if n <= 6:
            return s, max(n, 2) * s
    s = 10 ** math.ceil(math.log10(v / 5))
    return s, math.ceil(v / s) * s


def tick_txt(t: float) -> str:
    return R.fmt_dec(t, 1) if t % 1 else R.fmt_int(t)


# ---------------------------------------------------------------- dati del report

def _creators(data: ShopData, res: pd.DataFrame, margin: float) -> list:
    unit = data.aov * margin  # euro di margine per ogni ordine in piu'
    out = []
    for r in res.itertuples(index=False):
        days = sorted(pd.to_datetime(data.posts.loc[data.posts.creator == r.creator, "date"]).unique())
        code = None if r.orders_with_code is None or pd.isna(r.orders_with_code) else int(r.orders_with_code)
        be = r.cost_eur / unit if r.cost_eur > 0 and unit > 0 else None
        out.append(SimpleNamespace(
            r=r, name=r.creator, g=r.giudizio, ok=bool(r.estimable), n_posts=int(r.n_posts), days=days,
            cost=float(r.cost_eur), code=code, est=float(r.incremental_orders), lo=float(r.low_90),
            hi=float(r.high_90), roi=float(r.roi), roi_lo=float(r.roi_low), roi_hi=float(r.roi_high),
            be=be, margin_eur=float(r.incremental_orders) * unit))
    return out


def _total(fit: Fit, cr: list, data: ShopData, margin: float) -> SimpleNamespace:
    ok = [c for c in cr if c.ok]
    spend_all = sum(c.cost for c in cr)
    spend = sum(c.cost for c in ok)
    t = SimpleNamespace(ok=False, est=np.nan, lo=np.nan, hi=np.nan, prob=0.0, roi=np.nan, roi_lo=np.nan,
                        roi_hi=np.nan, g=INSUFF, spend=spend, spend_all=spend_all,
                        left_out=[c.name for c in cr if not c.ok])
    if not ok:
        return t
    tot = total_incremental(fit, [c.name for c in ok])
    vals = [tot["incremental_orders"], tot["low_90"], tot["high_90"]]
    if not np.all(np.isfinite(vals)):
        return t
    t.ok = True
    t.est, t.lo, t.hi, t.prob = round(vals[0], 1), round(vals[1], 1), round(vals[2], 1), tot["prob_effect_positive"]
    unit = data.aov * margin
    if spend > 0:
        t.roi, t.roi_lo, t.roi_hi = (round(v * unit / spend, 2) for v in (t.est, t.lo, t.hi))
        t.g = verdict({"prob_effect_positive": t.prob, "roi": t.roi, "roi_low": t.roi_lo})
    else:
        t.g = ZERO if t.prob >= 0.95 else NESSUNO
    t.margin_eur = t.est * unit
    return t


def _context(data, res, fit, margin, now, cal, brand, autore) -> SimpleNamespace:
    cr = _creators(data, res, margin)
    first, last = data.daily["date"].iloc[0], data.daily["date"].iloc[-1]
    y0, y1 = pd.Timestamp(first).year, pd.Timestamp(last).year
    c = SimpleNamespace(
        data=data, fit=fit, margin=margin, now=now, cal=cal, cr=cr,
        brand=(brand or "").strip(), autore=(autore or "").strip(), demo=data.origine == "simulati",
        periodo=f"{R.fmt_date(first)} – {R.fmt_date(last)}", anni=str(y0) if y0 == y1 else f"{y0}–{y1}",
        n=len(cr), n_posts=sum(x.n_posts for x in cr), tot=_total(fit, cr, data, margin),
        unit=data.aov * margin)
    c.by = {g: [x for x in cr if x.g == g] for g in VERDETTI}
    c.paid = [x for x in cr if x.g in RIPAGATI]
    c.codes = sum(x.code for x in cr if x.code is not None)
    return c


# ---------------------------------------------------------------- testi

def frase_totale(c) -> str:
    t = c.tot
    if not t.ok:
        return "Per il totale della campagna i dati non bastano a fare una stima."
    chi = f"i post di {num(c.n)} creator" if c.n > 1 else "i post del creator"
    if t.prob >= 0.95:
        return (f"Nel periodo {chi} hanno portato circa {R.fmt_int(t.est)} ordini in più "
                f"({ord_range(t.lo, t.hi)}), contando anche chi ha comprato senza codice sconto.")
    return (f"Nel periodo, sommando {chi}, non si vede un aumento chiaro degli ordini: le vendite in più "
            f"stanno {ord_range(t.lo, t.hi)}, quindi potrebbero anche essere nessuna.")


def frase_spesa(c) -> str:
    t = c.tot
    if not t.ok or t.spend <= 0:
        return ""
    spesa = R.fmt_eur(t.spend)
    if t.est <= 0:
        return f"Con {spesa} spesi, non ci sono prove che la spesa sia rientrata."
    margine = R.fmt_eur(round(t.margin_eur, -1) if t.margin_eur >= 100 else t.margin_eur)
    base = (f"Con {spesa} spesi, il margine portato è di circa {margine}, cioè {fmt_roi(t.roi)} € per ogni "
            "euro speso")
    coda = {CERTO: ": la spesa è quasi certamente rientrata.",
            PROB: ": nel complesso la spesa probabilmente è rientrata, ma non è certo.",
            NORIP: ": le vendite in più ci sono, ma non bastano a ripagare la spesa.",
            NESSUNO: ", ma con questa incertezza non si può dire se la spesa sia rientrata."}
    return base + coda.get(t.g, ".")


def frasi_creator(c) -> list:
    out = []
    by = c.by
    paid = [x for x in c.cr if x.g in (CERTO, PROB)]
    if paid:
        best = max(paid, key=lambda x: x.roi)
        if len(paid) == 1:
            out.append(f"L'unica collaborazione che si è ripagata è quella con {best.name}, con circa "
                       f"{fmt_roi(best.roi)} € di margine per ogni euro speso.")
        else:
            out.append(f"Si sono ripagate le collaborazioni con {elenco([x.name for x in paid])}; la migliore è "
                       f"{best.name}, con circa {fmt_roi(best.roi)} € di margine per ogni euro speso.")
    elif c.n > 1:
        out.append("Nessuna collaborazione si è ripagata in modo dimostrabile.")
    if by[ZERO]:
        nn = [x.name for x in by[ZERO]]
        out.append(f"{elenco(nn)} {'ha' if len(nn) == 1 else 'hanno'} portato vendite in più senza costi.")
    if by[NORIP]:
        nn = [x.name for x in by[NORIP]]
        out.append(f"{elenco(nn)} {'ha' if len(nn) == 1 else 'hanno'} portato vendite in più, ma non abbastanza "
                   "da ripagare il costo.")
    if by[NESSUNO]:
        xs = by[NESSUNO]
        k = len(xs)
        if k == 1:
            chi = f"Per {xs[0].name}" if c.n > 1 else "Per il creator"
        elif k == c.n:
            chi = f"Per {tutti(k)} creator"
        elif k == c.n - len(c.paid):  # tutti gli altri sono senza un effetto chiaro
            chi = f"Per gli altri {num(k)} creator"
        else:
            chi = f"Per {elenco([x.name for x in xs])}"
        verbo = "abbia" if k == 1 else "abbiano"
        out.append(f"{chi} l'effetto è troppo piccolo per distinguerlo dalle normali oscillazioni delle vendite: "
                   f"non vuol dire che non {verbo} venduto nulla, ma che con questi dati non si può dimostrare.")
    if by[INSUFF]:
        out.append(f"Per {elenco([x.name for x in by[INSUFF]])} i dati non bastano per una stima.")
    return out


def suggerimenti(c) -> list:
    """Cosa fare, per gruppi di giudizio: (in grassetto, spiegazione)."""
    out = []
    by = c.by
    if by[CERTO]:
        xs = by[CERTO]
        if len(xs) == 1:
            x = xs[0]
            out.append((f"Rinnovare la collaborazione con {x.name}.",
                        f"Anche nell'ipotesi più prudente ogni euro speso è tornato come almeno "
                        f"{fmt_roi(x.roi_lo)} € di margine."))
        else:
            out.append((f"Rinnovare le collaborazioni con {elenco([x.name for x in xs])}.",
                        "Anche nell'ipotesi più prudente il margine che portano supera il costo."))
    if by[ZERO]:
        out.append((f"Continuare con {elenco([x.name for x in by[ZERO]])}.",
                    "Le vendite in più ci sono e la collaborazione non è costata nulla."))
    if by[PROB]:
        xs = by[PROB]
        if len(xs) == 1:
            x = xs[0]
            out.append((f"Fare un'altra prova con {x.name} prima di decidere.",
                        f"Il risultato è probabilmente positivo ma incerto ({roi_range(x.roi_lo, x.roi_hi)} € "
                        "di margine per euro speso): un nuovo post aiuterebbe a confermarlo."))
        else:
            out.append((f"Fare un'altra prova con {elenco([x.name for x in xs])} prima di decidere.",
                        "Il risultato è probabilmente positivo, ma ancora incerto: un nuovo post aiuterebbe a "
                        "confermarlo."))
    if by[NORIP]:
        xs = by[NORIP]
        if len(xs) == 1:
            x = xs[0]
            out.append((f"Rinegoziare il compenso di {x.name}.",
                        f"Le vendite in più ci sono, ma il margine non copre il costo: con questi risultati la "
                        f"collaborazione si ripaga con un compenso fino a circa {R.fmt_eur(_giu(x.margin_eur))}."))
        else:
            out.append((f"Rinegoziare i compensi di {elenco([x.name for x in xs])}.",
                        "Le vendite in più ci sono, ma il margine che portano non copre il costo."))
    if by[NESSUNO]:
        xs = by[NESSUNO]
        spesa = sum(x.cost for x in xs)
        quota = spesa / c.tot.spend_all * 100 if c.tot.spend_all > 0 else 0
        if len(xs) == c.n:
            testa = "Rivedere le collaborazioni prima di rinnovarle." if len(xs) > 1 else \
                "Rivedere la collaborazione prima di rinnovarla."
        elif len(xs) == 1:
            testa = f"Rivedere la collaborazione con {xs[0].name} prima di rinnovarla."
        elif len(xs) == c.n - len(c.paid):
            testa = f"Rivedere le collaborazioni con gli altri {num(len(xs))} creator prima di rinnovarle."
        else:
            testa = f"Rivedere le collaborazioni con {elenco([x.name for x in xs])} prima di rinnovarle."
        if len(xs) == 1:
            testo = f"È costata {R.fmt_eur(spesa)}"
        else:
            testo = f"Insieme sono costate {R.fmt_eur(spesa)}"
        if len(xs) < c.n and spesa > 0:
            testo += f", il {R.fmt_int(quota)}% della spesa,"
        testo += (" senza un effetto dimostrabile. Non vuol dire che siano soldi persi, ma che con questi dati "
                  "non si può dire se si siano ripagate." if len(xs) > 1 else
                  " senza un effetto dimostrabile. Non vuol dire che siano soldi persi, ma che con questi dati "
                  "non si può dire se si sia ripagata.")
        sotto = [x for x in xs if _sotto_pareggio(x)]
        if sotto:
            x = max(sotto, key=lambda y: y.cost)
            testo += (f" Per {x.name} anche il caso migliore resta sotto il pareggio ({R.fmt_int(max(x.hi, 0))} "
                      f"ordini in più contro i circa {R.fmt_int(x.be)} che servivano).")
        out.append((testa, testo))
    if by[INSUFF]:
        out.append((f"Rifare l'analisi più avanti per {elenco([x.name for x in by[INSUFF]])}.",
                    "Dopo il post non ci sono ancora abbastanza giorni o ordini per una stima."))
    return out


def _giu(v: float) -> float:
    """Arrotonda per difetto a 10 € (per un compenso 'fino a')."""
    return max(0.0, math.floor(v / 10) * 10) if v >= 10 else max(0.0, v)


def _sotto_pareggio(x) -> bool:
    """Anche il valore piu' alto dell'intervallo resta sotto il pareggio (e si
    vede anche nei numeri arrotondati)."""
    return x.ok and x.be is not None and x.hi < x.be and int(round(max(x.hi, 0))) < int(round(x.be))


def lettura(x) -> str:
    if not x.ok:
        return "Il grafico mostra gli ordini reali attorno al post, ma i dati non bastano per una stima."
    if x.g in CHIARI:
        return ("Dopo i post la linea arancione si stacca da quella blu: lo scarto tra le due sono le vendite in "
                "più portate dal creator.")
    return ("Le due linee restano vicine: l'effetto, se c'è, è troppo piccolo per distinguerlo dalle normali "
            "oscillazioni (la fascia azzurra).")


def nota_codice(x) -> str:
    if x.code is None:
        return ("Questo creator non aveva un codice sconto: la stima si basa solo sull'andamento degli ordini "
                "attorno ai post.")
    k = R.fmt_int(x.code)
    if not x.ok:
        return f"Il suo codice sconto compare in {k} ordini."
    if x.g in CHIARI and x.code < x.lo:
        return (f"Il codice sconto compare in {k} ordini, meno delle vendite in più stimate "
                f"({ord_range(x.lo, x.hi)}): molti clienti arrivati dai post hanno comprato senza codice. "
                f"Contando solo i codici, quelle vendite non sarebbero state attribuite a {x.name}.")
    if x.g in CHIARI and x.code > x.hi:
        return (f"Il codice sconto compare in {k} ordini, più delle vendite in più stimate: una parte di chi l'ha "
                "usato avrebbe comprato comunque, o l'ha trovato su un sito di coupon.")
    if x.g in CHIARI:
        return (f"Il codice sconto compare in {k} ordini, dentro l'intervallo delle vendite in più stimate "
                f"({ord_range(x.lo, x.hi)}). Non tutti sono vendite in più: alcuni clienti avrebbero comprato "
                "comunque.")
    return (f"Il codice sconto compare in {k} ordini, ma da solo non prova un effetto: una parte arriva da clienti "
            "che avrebbero comprato comunque o da siti di coupon.")


def consiglio(x) -> str:
    if x.g == CERTO:
        return (f"Rinnovare la collaborazione: anche nell'ipotesi più prudente ogni euro speso è tornato come "
                f"almeno {fmt_roi(x.roi_lo)} € di margine.")
    if x.g == PROB:
        return (f"Fare un'altra prova prima di decidere: il risultato è probabilmente positivo, ma l'intervallo è "
                f"ancora ampio ({roi_range(x.roi_lo, x.roi_hi)} € per euro speso).")
    if x.g == ZERO:
        return "Continuare: le vendite in più ci sono e la collaborazione non è costata nulla."
    if x.g == NORIP:
        return (f"Rinegoziare il compenso: con questi risultati la collaborazione si ripaga fino a circa "
                f"{R.fmt_eur(_giu(x.margin_eur))}.")
    if x.g == INSUFF:
        return "Rifare l'analisi quando dopo il post ci saranno più giorni di dati."
    if _sotto_pareggio(x):
        return (f"Rivedere il compenso prima di rinnovare: anche nel caso migliore ({R.fmt_int(max(x.hi, 0))} "
                f"ordini in più) le vendite restano sotto il pareggio (circa {R.fmt_int(x.be)}).")
    if x.n_posts == 1:
        return ("Con un solo post i dati sono pochi: prima di rinnovare, valutare una prova con più post o un "
                "compenso più basso.")
    return ("Prima di rinnovare, valutare un compenso più basso o una prova con più post, a qualche giorno di "
            "distanza da quelli degli altri creator.")


def titolo_ripagati(c) -> str:
    k, n = len(c.paid), c.n
    if n == 1:
        x = c.cr[0]
        return {CERTO: "La collaborazione si è quasi certamente ripagata",
                PROB: "La collaborazione probabilmente si è ripagata, ma non è certo",
                ZERO: "La collaborazione ha portato vendite in più senza costi",
                NORIP: "La collaborazione ha portato vendite in più, ma non si è ripagata",
                NESSUNO: "Con questi dati non si vede un effetto chiaro della collaborazione",
                INSUFF: "I dati non bastano per giudicare la collaborazione"}[x.g]
    if k == 0:
        testa = f"Nessuno dei {num(n)} creator si è ripagato in modo dimostrabile"
    elif k == n:
        return f"{tutti(n).capitalize()} creator si sono ripagati"
    else:
        testa = (f"{num(k).capitalize()} creator su {num(n)} si "
                 f"{'è ripagato' if k == 1 else 'sono ripagati'}")
    resto = n - k
    nn, nr = len(c.by[NESSUNO]), len(c.by[NORIP])
    if k and nn == resto:
        coda = (f"; per gli altri {num(resto)} i dati non mostrano un effetto chiaro" if resto > 1
                else f"; per {c.by[NESSUNO][0].name} i dati non mostrano un effetto chiaro")
    elif k and nr == resto:
        coda = (f"; gli altri {num(resto)} portano vendite, ma non abbastanza" if resto > 1
                else f"; {c.by[NORIP][0].name} porta vendite, ma non abbastanza")
    else:
        coda = ""
    return testa + coda


# ---------------------------------------------------------------- grafici in HTML

def roi_chart(c) -> str:
    """Ritorno sul margine per creator: stima (punto), intervallo probabile
    (barra), zona sotto il pareggio in grigio chiaro, linea del pareggio a 1."""
    rows = [x for x in c.cr]
    finite = [max(x.roi_hi, x.roi, 0) for x in rows if x.ok and np.isfinite(x.roi_hi)]
    step, vmax = nice_max(max(finite + [1.5]))
    ticks = [round(i * step, 2) for i in range(int(round(vmax / step)) + 1)]
    if 1 not in ticks:
        ticks = sorted(ticks + [1])
    grid = "".join(f'<i class="gl" style="left:{pct(t, vmax)}"></i>' for t in ticks if t not in (0, 1))
    base = f'<i class="zone" style="width:{pct(1, vmax)}"></i>{grid}<i class="be" style="left:{pct(1, vmax)}"></i>'
    out = []
    for x in rows:
        costo = f'<span> · {e(R.fmt_eur(x.cost))}</span>'
        name = f'<div class="rc-name"><b>{e(x.name)}{costo}</b>{vt(x.g)}</div>'
        if not x.ok:
            trk = f'<span class="trk-txt">{e(INSUFF)}</span>'
        elif not np.isfinite(x.roi):
            trk = '<span class="trk-txt">costo zero: il ritorno non si calcola</span>'
        else:
            cls = "pos" if x.g in RIPAGATI else "neu"
            lo, hi = max(x.roi_lo, 0), max(x.roi_hi, 0)
            trk = f'<i class="bar bar--{cls}" style="left:{pct(lo, vmax)};width:calc({pct(hi, vmax)} - {pct(lo, vmax)})"></i>'
            if x.roi > 0:
                trk += (f'<i class="dot dot--{cls}" style="left:{pct(x.roi, vmax)}"></i>'
                        f'<b class="dv" style="left:{pct(x.roi, vmax)}">{fmt_roi(x.roi)}</b>')
            else:
                trk += '<i class="dot dot--zero" style="left:0"></i>'
        out.append(f'{name}<div class="rc-trk">{base}{trk}</div>')
    tk = "".join(f'<span class="tk{" tk--be" if t == 1 else ""}{" tk--end" if t >= vmax else ""}" '
                 f'style="left:{pct(t, vmax)}">{tick_txt(t)}</span>' for t in ticks)
    head = (f'<div class="rc-sp"></div><div class="rc-head"><span class="be-lab" style="left:{pct(1, vmax)}">'
            f'1 = pareggio <span>· a destra si ripaga →</span></span><i class="be" style="left:{pct(1, vmax)}"></i></div>')
    return (f'<div class="rc" role="img" aria-label="Ritorno sul margine di ogni creator, con intervallo probabile '
            f'e linea del pareggio a 1">{head}{"".join(out)}'
            f'<div class="rc-sp"></div><div class="rc-ax">{tk}</div>'
            f'<div class="rc-sp"></div><div class="rc-axt">euro di margine tornati per ogni euro speso</div></div>')


def number_line(x) -> str:
    """Vendite in piu' (intervallo e stima), ordini con codice e pareggio sullo
    stesso asse, in ordini."""
    if not x.ok:
        return ""
    lo, hi = max(x.lo, 0.0), max(x.hi, 0.0)
    vals = [hi, max(x.est, 0)] + ([x.code] if x.code is not None else []) + ([x.be] if x.be else [])
    step, vmax = nice_max(max(vals + [5]))
    ticks = [i * step for i in range(int(round(vmax / step)) + 1)]
    grid = "".join(f'<i class="gl" style="left:{pct(t, vmax)}"></i>' for t in ticks if t)
    be = f'<i class="be" style="left:{pct(x.be, vmax)}"></i>' if x.be else ""
    cls = "pos" if x.g in RIPAGATI else "neu"
    if x.est > 0:
        dot = f'<i class="dot dot--{cls}" style="left:{pct(x.est, vmax)}"></i>'
        val = f'<b>{R.fmt_int(x.est)}</b>'
    else:
        dot = '<i class="dot dot--zero" style="left:0"></i>'
        val = f'<b class="nr">{R.NO_EFFECT}</b>'
    head = ""
    if x.be:
        side = " mv-be-lab--r" if x.be / vmax > 0.6 else ""
        head = (f'<div class="mv-row"><div class="mv-sp"></div><div class="mv-plot mv-plot--head">'
                f'<span class="mv-be-lab{side}" style="left:{pct(x.be, vmax)}">pareggio: circa '
                f'{R.fmt_int(x.be)} ordini</span></div></div>')
    rows = (f'<div class="mv-row"><div class="mv-lab">Vendite in più stimate{val}</div>'
            f'<div class="mv-plot">{grid}{be}<i class="bar bar--{cls}" style="left:{pct(lo, vmax)};'
            f'width:calc({pct(hi, vmax)} - {pct(lo, vmax)})"></i>{dot}</div></div>')
    if x.code is not None:
        rows += (f'<div class="mv-row"><div class="mv-lab">Ordini con il suo codice<b>{R.fmt_int(x.code)}</b></div>'
                 f'<div class="mv-plot">{grid}{be}<i class="cbar" style="width:{pct(x.code, vmax)}"></i>'
                 f'<span class="clab" style="left:{pct(x.code, vmax)}">{R.fmt_int(x.code)} con codice</span></div></div>')
    tk = "".join(f'<span class="tk{" tk--end" if t >= vmax else ""}" style="left:{pct(t, vmax)}">{R.fmt_int(t)}</span>'
                 for t in ticks)
    axis = f'<div class="mv-row"><div class="mv-sp"></div><div class="mv-plot mv-plot--axis">{tk}</div></div>'
    return (f'<figure class="mv" aria-label="Vendite in più, ordini con codice e pareggio di {e(x.name)}">'
            f'<h4 class="sub">Vendite in più, codice sconto e pareggio <span style="text-transform:none;'
            f'letter-spacing:0;font-weight:400">· in ordini</span></h4>{head}{rows}{axis}</figure>')


def schema() -> str:
    """Esempio disegnato a mano per spiegare i grafici giorno per giorno."""
    x0, dx = 40, 23.3

    def X(d):
        return x0 + (d + 7) * dx

    def yb(d):
        return 172 + 7 * math.sin(d * 0.9)

    def yo(d):
        return yb(d) - (0 if d < 0 else 82 * math.exp(-d / 2.6))

    days = list(range(-7, 21))
    noise = [9, -14, 6, -4, 15, -9, 3, -16, 5, 12, -7, 10, -12, 4, 14, -6, -15, 8, -3, 11, -10, 6, 13, -8, 2, -13, 9, -5]
    band = (" ".join(f"{X(d):.1f},{yb(d) - 38:.1f}" for d in days) + " "
            + " ".join(f"{X(d):.1f},{yb(d) + 38:.1f}" for d in reversed(days)))
    blue = " ".join(f"{X(d):.1f},{yb(d):.1f}" for d in days)
    orange = " ".join(f"{X(d):.1f},{yo(d):.1f}" for d in days)
    lift = [d for d in days if 0 <= d <= 12]
    area = (" ".join(f"{X(d):.1f},{yo(d):.1f}" for d in lift) + " "
            + " ".join(f"{X(d):.1f},{yb(d):.1f}" for d in reversed(lift)))
    dy = {d: yo(d) + noise[k] * 1.1 for k, d in enumerate(days)}
    dots = "".join(f'<circle cx="{X(d):.1f}" cy="{dy[d]:.1f}" r="3" fill="#52514e" stroke="#fcfcfb" stroke-width="1.2"/>'
                   for d in days)

    def call(tx, ty, px, py, a, b, lx, ly):
        return (f'<path d="M{px:.1f},{py:.1f} L{lx:.1f},{ly:.1f}" stroke="#898781" stroke-width="1" fill="none"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" fill="#0b0b0b" stroke="#fcfcfb" stroke-width="1"/>'
                f'<text x="{tx:.1f}" y="{ty}" class="s1">{a}<tspan x="{tx:.1f}" dy="16" class="s2">{b}</tspan></text>')

    ax = 268
    return f"""<svg class="schema" viewBox="0 0 700 296" role="img" aria-label="Come leggere i grafici giorno per giorno: esempio">
  <style>.schema text{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}}
  .schema .s1{{font-size:13px;fill:#0b0b0b;font-weight:600}} .schema .s2{{font-size:12px;fill:#52514e}}
  .schema .ax{{font-size:12px;fill:#52514e}}</style>
  <line x1="{x0 - 8}" x2="{X(20) + 8:.1f}" y1="{ax}" y2="{ax}" stroke="#c3c2b7" stroke-width="1"/>
  <polygon points="{band}" fill="#2a78d6" fill-opacity="0.12"/>
  <polygon points="{area}" fill="#eb6834" fill-opacity="0.16"/>
  <line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="22" y2="{ax}" stroke="#52514e" stroke-width="1.2"/>
  <polyline points="{blue}" fill="none" stroke="#2a78d6" stroke-width="2.4" stroke-linejoin="round"/>
  <polyline points="{orange}" fill="none" stroke="#eb6834" stroke-width="2.4" stroke-linejoin="round"/>
  {dots}
  <text x="{X(0):.1f}" y="{ax + 20}" class="ax" text-anchor="middle">giorno del post</text>
  <text x="{X(7):.1f}" y="{ax + 20}" class="ax" text-anchor="middle">+1 settimana</text>
  <text x="{X(14):.1f}" y="{ax + 20}" class="ax" text-anchor="middle">+2 settimane</text>
  {call(X(3) + 4, 44, X(1), yo(1), "Ordini attesi con il creator", "linea arancione", X(3) - 2, 46)}
  {call(X(5) + 4, 96, X(2.2), (yo(2.2) + yb(2.2)) / 2 + 4, "Vendite in più", "lo scarto tra la linea arancione e la blu", X(5) - 2, 98)}
  {call(X(13) + 4, 76, X(15), yb(15) - 38, "Oscillazioni normali", "fascia azzurra: 9 giorni su 10", X(15), 96)}
  {call(X(12) + 4, 238, X(17), yb(17), "Ordini attesi senza il creator", "linea blu", X(16), 226)}
  {call(X(-7), 50, X(-5), dy[-5], "Ordini reali", "un punto per ogni giorno", X(-5.6), 72)}
</svg>"""


# ---------------------------------------------------------------- sezioni

def _kicker(no: str, lab: str, count: str = "") -> str:
    cnt = f'<span class="count">{e(count)}</span>' if count else ""
    return f'<div class="kicker"><span class="no">{no}</span><span class="lab">{e(lab)}</span>{cnt}</div>'


def sec_sintesi(c) -> str:
    t = c.tot
    meta = []
    if c.brand:
        meta.append(("Preparato per", c.brand))
    meta.append(("Periodo analizzato", c.periodo))
    meta.append(("Data del report", date_long(c.now)))
    if c.autore:
        meta.append(("Preparato da", c.autore))
    if c.demo:
        meta.append(("Dati", "negozio simulato (dimostrativi)"))
    meta_html = "".join(f'<div><div class="m-l">{e(a)}</div><div class="m-v">{e(b)}</div></div>' for a, b in meta)
    right = (f'<div class="client">{e(c.brand)}</div>' if c.brand else
             ('<span class="demo-tag">Dati dimostrativi</span>' if c.demo else ""))

    # numeri chiave
    if not t.ok:
        k1 = f'<div class="kpi-v kpi-v--txt">{R.NOT_ENOUGH}</div><div class="kpi-s">&nbsp;</div>'
    elif t.est < 0:
        k1 = (f'<div class="kpi-v kpi-v--txt">{R.NO_EFFECT}</div>'
              f'<div class="kpi-s">intervallo probabile<br>{ord_range(t.lo, t.hi)}</div>')
    else:
        k1 = (f'<div class="kpi-v">{R.fmt_int(t.est)}</div>'
              f'<div class="kpi-s">intervallo probabile<br>{ord_range(t.lo, t.hi)}</div>')
    k2 = (f'<div class="kpi-v">{R.fmt_int(t.spend_all)}<span class="u">&nbsp;€</span></div>'
          f'<div class="kpi-s">{num(c.n)} creator, {R.fmt_int(c.n_posts)} post</div>')
    if not t.ok or t.spend <= 0:
        k3 = f'<div class="kpi-v kpi-v--txt">{"costo zero" if t.ok else R.NOT_ENOUGH}</div><div class="kpi-s">&nbsp;</div>'
    elif t.roi < 0:
        k3 = (f'<div class="kpi-v kpi-v--txt">{R.NO_EFFECT}</div>'
              f'<div class="kpi-s">{roi_range(t.roi_lo, t.roi_hi)}</div>')
    else:
        k3 = (f'<div class="kpi-v">{fmt_roi(t.roi)}<span class="u">&nbsp;€</span></div>'
              f'<div class="kpi-s">di margine per ogni euro speso<br>{roi_range(t.roi_lo, t.roi_hi)}</div>')
    icons = "".join(icon(x.g) for x in c.cr) if c.n <= 16 else ""
    nomi = elenco([x.name for x in c.paid]) if 0 < len(c.paid) <= 3 else (
        f"{len(c.by[CERTO])} quasi certamente, {len(c.by[PROB])} probabilmente" if c.paid else "nessuno in modo dimostrabile")
    k4 = (f'<div class="kpi-v">{len(c.paid)}<span class="su"> su {c.n}</span></div>'
          f'<div class="icons" aria-hidden="true">{icons}</div><div class="kpi-s">{e(nomi)}</div>')
    kpis = (f'<div class="kpis">'
            f'<div class="kpi"><div class="kpi-l">Ordini in più grazie ai creator</div>{k1}</div>'
            f'<div class="kpi"><div class="kpi-l">Spesa per i creator</div>{k2}</div>'
            f'<div class="kpi"><div class="kpi-l">Ritorno sul margine</div>{k3}</div>'
            f'<div class="kpi"><div class="kpi-l">Creator che si sono ripagati</div>{k4}</div></div>')

    p1 = " ".join(s for s in (frase_totale(c), frase_spesa(c)) if s)
    punto_html = f"<p>{e(p1)}</p><p>{e(' '.join(frasi_creator(c)))}</p>"
    recs = "".join(f"<li><b>{e(a)}</b>{e(b)}</li>" for a, b in suggerimenti(c))
    avvisi = [a for a in c.data.avvisi if a.livello == "importante"]
    warn = ("<div class='warn'><b>Da tenere presente</b><ul>" + "".join(f"<li>{e(a.testo)}</li>" for a in avvisi)
            + "</ul></div>") if avvisi else ""
    note = ([f"Il totale e il ritorno complessivo non comprendono {elenco(t.left_out)} (dati insufficienti)."]
            if t.left_out else [])
    return f"""<section class="sheet first" id="sintesi">
  <div class="topbar"><div class="mark">{LOGO}<span>Creator Lift</span></div>{right}</div>
  <div class="eyebrow">Analisi delle collaborazioni con i creator · {e(c.anni)}</div>
  <h1>Quanto hanno venduto davvero i vostri creator</h1>
  <p class="sub-title">Vendite in più, costo e ritorno sul margine di {num(c.n, True)} collaborazion{'i' if c.n != 1 else 'e'}, comprese le vendite arrivate senza codice sconto.</p>
  <div class="meta">{meta_html}</div>
  {kpis}
  <div class="block punto"><h4 class="sub">Il punto</h4><div>{punto_html}</div></div>
  <div class="block recs"><h4 class="sub">Cosa suggeriamo</h4><ol>{recs}</ol></div>
  {warn}
  {f'<p class="note">{e(" ".join(note))}</p>' if note else ""}
</section>"""


def table(c) -> str:
    rows = []
    for x in c.cr:
        code = R.fmt_int(x.code) if x.code is not None else "senza codice"
        if not x.ok:
            effect = f'<td class="merged" colspan="2" data-l="Vendite in più e ritorno"><span class="nr">{INSUFF}</span></td>'
        elif x.est < 0:
            ritorno = f" · ritorno {roi_range(x.roi_lo, x.roi_hi)}" if np.isfinite(x.roi) else ""
            effect = (f'<td class="merged" colspan="2" data-l="Vendite in più e ritorno"><span class="nr">'
                      f'{R.NO_EFFECT}</span><small>vendite {ord_range(x.lo, x.hi)}{ritorno}</small></td>')
        else:
            if np.isfinite(x.roi):
                roi = (f'{fmt_roi(x.roi)}<small>{roi_range(x.roi_lo, x.roi_hi)}</small>' if x.roi >= 0 else
                       f'<span class="nr">{R.NO_EFFECT}</span><small>{roi_range(x.roi_lo, x.roi_hi)}</small>')
            else:
                roi = '<span class="nr">costo zero</span>'
            effect = (f'<td class="num" data-l="Vendite in più">{R.fmt_int(x.est)}<small>{ord_range(x.lo, x.hi)}</small></td>'
                      f'<td class="num" data-l="Ritorno sul margine">{roi}</td>')
        rows.append(f'<tr><th scope="row" data-l="Creator">{e(x.name)}</th>'
                    f'<td class="num" data-l="Post">{x.n_posts}</td>'
                    f'<td class="num" data-l="Costo">{e(R.fmt_eur(x.cost))}</td>'
                    f'<td class="num" data-l="Ordini con codice">{code}</td>{effect}'
                    f'<td data-l="Giudizio">{vt(x.g)}</td></tr>')
    t = c.tot
    if t.ok:
        est = (R.fmt_int(t.est) if t.est >= 0 else f'<span class="nr">{R.NO_EFFECT}</span>')
        roi = ("" if t.spend <= 0 else
               (fmt_roi(t.roi) if t.roi >= 0 else f'<span class="nr">{R.NO_EFFECT}</span>')
               + f"<small>{roi_range(t.roi_lo, t.roi_hi)}</small>")
        tot_cells = (f'<td class="num" data-l="Vendite in più">{est}<small>{ord_range(t.lo, t.hi)}</small></td>'
                     f'<td class="num" data-l="Ritorno sul margine">{roi}</td>')
    else:
        tot_cells = f'<td class="merged" colspan="2" data-l="Vendite in più e ritorno">{INSUFF}</td>'
    foot = (f'<tr><th scope="row" data-l="Totale">Totale</th><td class="num" data-l="Post">{c.n_posts}</td>'
            f'<td class="num" data-l="Costo">{e(R.fmt_eur(t.spend_all))}</td>'
            f'<td class="num" data-l="Ordini con codice">{R.fmt_int(c.codes)}</td>{tot_cells}'
            f'<td class="empty" data-l=""></td></tr>')
    return (f'<table class="tbl"><thead><tr><th scope="col">Creator</th><th scope="col" class="num">Post</th>'
            f'<th scope="col" class="num">Costo</th><th scope="col" class="num">Ordini con codice</th>'
            f'<th scope="col" class="num">Vendite in più<span class="th-sub">stima e intervallo</span></th>'
            f'<th scope="col" class="num">Ritorno sul margine<span class="th-sub">€ per € speso</span></th>'
            f'<th scope="col">Giudizio</th></tr></thead><tbody>{"".join(rows)}</tbody><tfoot>{foot}</tfoot></table>')


def sec_ripagati(c) -> str:
    return f"""<section class="sheet" id="ripagati">
  {_kicker("01", "Si sono ripagati?")}
  <h2 class="action">{e(titolo_ripagati(c))}</h2>
  <div class="exhibit">
    <div class="ex-h"><div class="ex-t">Ritorno sul margine per creator</div>
      <div class="legend"><span><i class="sw sw-dot"></i>stima</span><span><i class="sw sw-bar"></i><i class="sw sw-bar2"></i>intervallo probabile</span>
      <span><i class="sw sw-ring"></i>nessun effetto rilevato</span><span><i class="sw sw-zone"></i>sotto il pareggio</span></div></div>
    {roi_chart(c)}
    <p class="fig-c">A destra della linea nera (1 € di margine per ogni euro speso) la collaborazione si è ripagata. Il cerchio vuoto sullo zero indica una stima sotto lo zero: nessun effetto rilevato, non una perdita.</p>
  </div>
  <div class="exhibit">
    <div class="ex-h"><div class="ex-t">Riepilogo per creator</div></div>
    {table(c)}
    <p class="fig-c">Ritorno = vendite in più × scontrino medio ({e(R.fmt_eur(c.data.aov))}) × margine lordo ({R.fmt_int(c.margin * 100)}%) ÷ costo. Gli estremi sotto lo zero sono mostrati come 0. L'intervallo del totale non è la somma di quelli dei singoli creator.</p>
  </div>
</section>"""


def sec_leggere(c) -> str:
    gloss = [
        ("Vendite in più", "Gli ordini che non ci sarebbero stati senza i post, con o senza codice sconto: ordini "
                           "reali meno ordini attesi senza il creator."),
        ("Intervallo probabile", "La fascia in cui si trova il valore vero 9 volte su 10. Se parte da 0, il "
                                 "creator potrebbe non aver portato nessuna vendita in più."),
        ("Ritorno sul margine", "Quanti euro di margine sono tornati per ogni euro pagato al creator. Sopra 1 la "
                                "collaborazione si è ripagata, sotto 1 no."),
        ("Pareggio", "Le vendite in più che servono perché il margine copra il costo: costo ÷ (scontrino medio × "
                     f"margine lordo), cioè circa un ordine in più ogni {R.fmt_int(c.unit)} € di costo."),
        ("Ordini con codice", "Gli ordini con il codice sconto del creator. Non coincidono con le vendite in più: "
                              "molti clienti comprano senza codice e alcuni codici girano sui siti di coupon."),
        ("Nessun effetto rilevato", "La stima è sotto lo zero: i post non hanno fatto salire gli ordini in modo "
                                    "visibile. Non indica una perdita."),
    ]
    gl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in gloss)
    presenti = [g for g in VERDETTI if g != ZERO or c.by[ZERO]]
    verd = "".join(f"<div>{badge(g)}</div><div>{SPIEGAZIONI[g]}</div>" for g in presenti)
    return f"""<section class="sheet" id="leggere">
  {_kicker("02", "Creator per creator")}
  <h2 class="action">Come leggere le schede dei creator</h2>
  <div class="exhibit">
    <div class="ex-h"><div class="ex-t">Il grafico giorno per giorno (esempio disegnato, non un creator reale)</div></div>
    <div class="fig-scroll">{schema()}</div>
    <p class="fig-c">Se dopo il post gli ordini reali e la linea arancione salgono sopra la fascia azzurra, il creator ha portato vendite in più. Se restano dentro la fascia, l'effetto non si distingue dalle normali oscillazioni del negozio.</p>
  </div>
  <div class="two"><h4 class="sub">Le parole del report</h4><dl class="gloss">{gl}</dl></div>
  <div class="two"><h4 class="sub">I giudizi</h4><div class="verd">{verd}</div>
  <p class="fig-c">Ogni giudizio ha il suo simbolo, così si legge anche stampato in bianco e nero.</p></div>
</section>"""


def _chart_img(c, x) -> str:
    fig = R.creator_figure(c.fit, c.data, x.name)
    b64 = base64.b64encode(R.fig_svg(fig)).decode()
    alt = (f"Ordini di ogni giorno attorno ai post di {x.name}: ordini reali, ordini attesi senza il creator con la "
           "fascia delle normali oscillazioni e ordini attesi con il creator.")
    return f'<img alt="{e(alt)}" src="data:image/svg+xml;base64,{b64}">'


def sec_creator(c, i, x) -> str:
    post = "1 post" if x.n_posts == 1 else f"{x.n_posts} post"
    if not x.ok:
        v1 = f'<div class="st-v st-v--txt">{INSUFF}</div><div class="st-s">&nbsp;</div>'
        v2 = v1
    else:
        v1 = ((f'<div class="st-v">{R.fmt_int(x.est)}</div>' if x.est >= 0 else
               f'<div class="st-v st-v--txt">{R.NO_EFFECT}</div>')
              + f'<div class="st-s">intervallo probabile<br>{ord_range(x.lo, x.hi)}</div>')
        if not np.isfinite(x.roi):
            v2 = '<div class="st-v st-v--txt">costo zero</div><div class="st-s">&nbsp;</div>'
        elif x.roi >= 0:
            v2 = (f'<div class="st-v">{fmt_roi(x.roi)}<span class="u">&nbsp;€</span></div>'
                  f'<div class="st-s">di margine per € speso<br>{roi_range(x.roi_lo, x.roi_hi)}</div>')
        else:
            v2 = (f'<div class="st-v st-v--txt">{R.NO_EFFECT}</div>'
                  f'<div class="st-s">di margine per € speso<br>{roi_range(x.roi_lo, x.roi_hi)}</div>')
    pareggio = f" · pareggio a circa {R.fmt_int(x.be)} ordini" if x.be else ""
    v3 = f'<div class="st-v">{e(R.fmt_eur(x.cost))}</div><div class="st-s">{post}{pareggio}</div>'
    v4 = (f'<div class="st-v">{R.fmt_int(x.code)}</div><div class="st-s">con il suo codice sconto</div>'
          if x.code is not None else '<div class="st-v st-v--txt">senza codice</div><div class="st-s">&nbsp;</div>')
    titolo = "Ordini al giorno attorno al post" if x.n_posts == 1 else f"Ordini al giorno attorno ai {x.n_posts} post"
    return f"""<section class="sheet creator" id="c-{i}">
  {_kicker("02", "Creator per creator", f"{i} di {c.n}")}
  <div class="cr-head"><h2 class="cr-name">{e(x.name)}</h2>{badge(x.g)}</div>
  <div class="cr-meta">{post} · {e(date_list(x.days))} · costo {e(R.fmt_eur(x.cost))}</div>
  <p class="cr-lead">{e(R.sentence(x.r))}</p>
  <div class="stats">
    <div class="st"><div class="st-l">Vendite in più</div>{v1}</div>
    <div class="st"><div class="st-l">Ritorno sul margine</div>{v2}</div>
    <div class="st"><div class="st-l">Costo</div>{v3}</div>
    <div class="st"><div class="st-l">Ordini con codice</div>{v4}</div>
  </div>
  {number_line(x)}
  <figure class="fig">
    <figcaption class="fig-t">{e(titolo)}</figcaption>
    <div class="fig-scroll">{_chart_img(c, x)}</div>
    <p class="fig-src">Fonte: ordini giornalieri del negozio, {e(c.periodo)}.</p>
  </figure>
  <div class="cr-foot">
    <div><h4 class="sub">Cosa mostra il grafico</h4><p>{e(lettura(x))}</p></div>
    <div><h4 class="sub">Codice sconto e stima</h4><p>{e(nota_codice(x))}</p></div>
    <div><h4 class="sub">Cosa suggeriamo</h4><p>{e(consiglio(x))}</p></div>
  </div>
</section>"""


def sec_metodo(c) -> str:
    d = c.data
    esclusi = "; ".join(f"{R.fmt_int(v)} {EXCLUSION_LABELS[k]}" for k, v in d.esclusi.items()) or "nessuno"
    cal = R.calibration_text(c.cal)
    cal = cal.split(": ", 1)[1] if ": " in cal else cal
    cal = (cal[:1].upper() + cal[1:]) if cal else "Non eseguito."
    origine = "negozio simulato (dati dimostrativi)" if c.demo else "export degli ordini di Shopify"
    avvisi = [a for a in d.avvisi if a.livello != "importante"]
    avvisi_html = ("<ul>" + "".join(f"<li>{e(a.testo)}</li>" for a in avvisi) + "</ul>") if avvisi else "nessuno"
    facts = [
        ("Periodo analizzato", f"{c.periodo} ({R.fmt_int(d.n_days)} giorni)"),
        ("Origine dei dati", origine),
        ("Ordini al giorno", f"{R.fmt_dec(d.orders_per_day, 1)} in media"),
        ("Scontrino medio", f"{R.fmt_eur(d.aov)} ({d.aov_label})"),
        ("Margine lordo", f"{R.fmt_int(c.margin * 100)}%"),
        ("Creator e post", f"{c.n} creator, {c.n_posts} post, {R.fmt_eur(c.tot.spend_all)} di spesa"),
        ("Ordini non contati", esclusi),
        ("Controllo di affidabilità", cal),
    ]
    facts_html = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in facts)
    facts_html += f"<dt>Altri avvisi sui dati</dt><dd>{avvisi_html}</dd>"
    prova = (f"Prima dei risultati il calcolo è stato messo alla prova su questo negozio con "
             f"{R.fmt_int(c.cal['creator_finti'])} creator inventati, che per costruzione non hanno effetto: "
             + ("gli intervalli sono stati allargati per tenerne conto." if c.cal["fattore_usato"] > 1 else
                "gli intervalli si sono dimostrati affidabili.")) if c.cal else (
        "Il metodo è stato provato su negozi simulati in cui l'effetto vero era noto.")
    return f"""<section class="sheet" id="metodo">
  {_kicker("03", "Dati e metodo")}
  <h2 class="action">La stima confronta gli ordini reali con quelli che ci sarebbero stati senza i post</h2>
  <dl class="facts">{facts_html}</dl>
  <div class="cols2">
    <div><h4 class="sub">Come funziona</h4><ol class="steps">
      <li>Partiamo dagli ordini di ogni giorno del periodo, per capire l'andamento normale del negozio: tendenza, giorno della settimana, stagione e giorni di promozione.</li>
      <li>Per ogni creator misuriamo quanto salgono gli ordini il giorno del post, nei 2 giorni dopo, nei giorni da 3 a 6 e da 7 a 13.</li>
      <li>Le vendite in più sono la differenza tra gli ordini previsti con i post e quelli previsti senza, con o senza codice sconto.</li>
      <li>L'intervallo probabile si ottiene ripetendo il calcolo 2.000 volte con piccole variazioni: più le vendite oscillano, più è ampio.</li>
      <li>Il ritorno sul margine moltiplica le vendite in più per lo scontrino medio e il margine lordo, e le divide per il costo.</li>
      <li>{e(prova)}</li>
    </ol></div>
    <div><h4 class="sub">Limiti da tenere presenti</h4><ul class="limits">
      <li>Misura le vendite nelle due settimane dopo ogni post, non gli effetti di lungo periodo (clienti che tornano dopo mesi, notorietà del marchio).</li>
      <li>Se due creator pubblicano lo stesso giorno, il loro effetto si può stimare solo insieme. Anche saldi e campagne non indicati come promozioni possono confondere la stima.</li>
      <li>Con pochi post o vendite molto variabili, gli effetti piccoli restano nascosti nelle oscillazioni: è il caso di «nessun effetto chiaro».</li>
      <li>Scontrino e margine sono valori medi del negozio: se i clienti dei creator comprano prodotti più cari o più scontati, il ritorno reale può essere diverso.</li>
    </ul></div>
  </div>
</section>"""


def sec_verita(c, res) -> str:
    truth = c.data.truth.set_index("creator")["true_incremental_orders"]
    rows = [x for x in c.cr if x.name in truth.index]
    vals = [max(x.hi, 0) for x in rows if x.ok] + [float(truth[x.name]) for x in rows]
    step, vmax = nice_max(max(vals + [10]))
    ticks = [i * step for i in range(int(round(vmax / step)) + 1)]
    grid = "".join(f'<i class="gl" style="left:{pct(t, vmax)}"></i>' for t in ticks if t)
    chart, trs, dentro, nessuno_veri = [], [], 0, []
    for x in rows:
        vero = float(truth[x.name])
        inside = x.ok and x.lo <= vero <= x.hi
        dentro += inside
        if x.g == NESSUNO and vero > 0:
            nessuno_veri.append((x.name, vero))
        ic = "#i-si" if inside else "#i-no"
        esito = (f'<span class="vt"><svg class="vi" viewBox="0 0 16 16" aria-hidden="true"><use href="{ic}"/></svg>'
                 f'<span>{"nell’intervallo" if inside else "fuori dall’intervallo"}</span></span>')
        trk = grid
        if x.ok:
            trk += (f'<i class="bar bar--neu" style="left:{pct(max(x.lo, 0), vmax)};width:calc('
                    f'{pct(max(x.hi, 0), vmax)} - {pct(max(x.lo, 0), vmax)})"></i>')
            trk += (f'<i class="dot dot--neu" style="left:{pct(x.est, vmax)}"></i>' if x.est >= 0 else
                    '<i class="dot dot--zero" style="left:0"></i>')
        trk += f'<i class="truth" style="left:{pct(vero, vmax)}"></i>'
        chart.append(f'<div class="rc-name"><b>{e(x.name)}</b>{esito}</div><div class="rc-trk">{trk}</div>')
        stima = (R.fmt_int(x.est) if x.est >= 0 else f'<span class="nr">{R.NO_EFFECT}</span>') if x.ok else INSUFF
        code = R.fmt_int(x.code) if x.code is not None else "senza codice"
        trs.append(f'<tr><th scope="row" data-l="Creator">{e(x.name)}</th>'
                   f'<td class="num" data-l="Effetto vero">{R.fmt_int(vero)}</td>'
                   f'<td class="num" data-l="Stima">{stima}</td>'
                   f'<td class="num" data-l="Intervallo probabile">{ord_range(x.lo, x.hi) if x.ok else INSUFF}</td>'
                   f'<td data-l="Il vero è nell’intervallo?">{esito}</td>'
                   f'<td class="num" data-l="Ordini con codice">{code}</td></tr>')
    tk = "".join(f'<span class="tk{" tk--end" if t >= vmax else ""}" style="left:{pct(t, vmax)}">{R.fmt_int(t)}</span>'
                 for t in ticks)
    n = len(rows)
    volte = f"{num(dentro, True)} {'volta' if dentro == 1 else 'volte'} su {num(n, True)}"
    find = [(f"L'intervallo ci prende {volte}.",
             "Per costruzione l'intervallo probabile contiene il valore vero circa 9 volte su 10: su pochi creator "
             "può capitare di sbagliarne uno.")]
    con_codice = [x for x in rows if x.code is not None]
    sotto = [x for x in con_codice if float(truth[x.name]) - x.code > 5]
    sopra = [x for x in con_codice if x.code - float(truth[x.name]) > 5]
    parti = []
    if sotto:
        a = max(sotto, key=lambda x: float(truth[x.name]) - x.code)
        parti.append(f"per {a.name} i codici sono {R.fmt_int(a.code)}, ma le vendite in più vere erano "
                     f"{R.fmt_int(truth[a.name])}")
    if sopra:
        b = max(sopra, key=lambda x: x.code - float(truth[x.name]))
        parti.append(f"per {b.name} ci sono {R.fmt_int(b.code)} ordini con codice, ma l'effetto vero era di "
                     f"{R.fmt_int(truth[b.name])}")
    if parti:
        find.append(("I codici sconto da soli avrebbero sbagliato.", elenco(parti)[:1].upper() + elenco(parti)[1:] + "."))
    if nessuno_veri:
        nn = elenco([f"{a} ({R.fmt_int(v)} ordini)" for a, v in nessuno_veri])
        find.append(("«Nessun effetto chiaro» non vuol dire zero.",
                     f"Avevano un effetto vero anche {nn}: troppo piccolo per distinguerlo dalle oscillazioni "
                     "normali. È proprio il significato di questo giudizio."))
    find_html = "".join(f"<div><h4>{e(a)}</h4><p>{e(b)}</p></div>" for a, b in find)
    return f"""<section class="sheet" id="verita">
  {_kicker("A", "Appendice · solo dati dimostrativi")}
  <h2 class="action">Confronto con la verità: il valore vero cade nell'intervallo probabile {volte}</h2>
  <div class="demo-box"><span class="demo-tag">Solo demo</span><p>Questo negozio è simulato, quindi l'effetto vero di ogni creator è noto e si può controllare il calcolo. Nei report su dati reali questa pagina non c'è: l'effetto vero non si può conoscere.</p></div>
  <div class="exhibit">
    <div class="ex-h"><div class="ex-t">Effetto vero e intervallo probabile per creator</div>
      <div class="legend"><span><i class="sw sw-diamond"></i>effetto vero</span><span><i class="sw sw-dot2"></i>stima</span>
      <span><i class="sw sw-bar2"></i>intervallo probabile</span><span><i class="sw sw-ring"></i>nessun effetto rilevato</span></div></div>
    <div class="rc" role="img" aria-label="Effetto vero confrontato con stima e intervallo probabile">{"".join(chart)}
      <div class="rc-sp"></div><div class="rc-ax">{tk}</div><div class="rc-sp"></div><div class="rc-axt">ordini in più</div></div>
  </div>
  <div class="exhibit"><table class="tbl"><thead><tr><th scope="col">Creator</th>
    <th scope="col" class="num">Effetto vero<span class="th-sub">ordini in più</span></th><th scope="col" class="num">Stima</th>
    <th scope="col" class="num">Intervallo probabile</th><th scope="col">Il vero è nell'intervallo?</th>
    <th scope="col" class="num">Ordini con codice</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>
  <div class="find">{find_html}</div>
</section>"""


# ---------------------------------------------------------------- documento

def _page_css(c) -> str:
    font = "500 7.5pt/1 system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    left_top = "Creator Lift" + (f" · {c.brand}" if c.brand else "")
    left_bottom = "Dati dimostrativi" if c.demo else ("Riservato · " + c.brand if c.brand else "Riservato")
    return f"""
@page{{size:A4; margin:20mm 18mm 18mm 18mm; background:#fcfcfb;
  @top-left{{content:{css_str(left_top)}; font:{font}; color:#52514e; vertical-align:bottom; padding-bottom:5mm}}
  @top-right{{content:{css_str("Collaborazioni con i creator · " + c.periodo)}; font:{font}; color:#52514e; vertical-align:bottom; padding-bottom:5mm}}
  @bottom-left{{content:{css_str(left_bottom)}; font:{font}; color:#52514e; vertical-align:top; padding-top:5mm}}
  @bottom-right{{content:"Pagina " counter(page) " di " counter(pages); font:{font}; color:#52514e; vertical-align:top; padding-top:5mm}}
}}
@page :first{{@top-left{{content:none}} @top-right{{content:none}}}}
"""


def build(data: ShopData, res: pd.DataFrame, fit: Fit, margin: float, now: datetime | None = None,
          cal: dict | None = None, brand: str | None = None, autore: str | None = None) -> str:
    c = _context(data, res, fit, margin, now or datetime.now(), cal, brand, autore)
    parts = [sec_sintesi(c), sec_ripagati(c), sec_leggere(c)]
    parts += [sec_creator(c, i + 1, x) for i, x in enumerate(c.cr)]
    parts.append(sec_metodo(c))
    if data.truth is not None:
        parts.append(sec_verita(c, res))
    title = "Creator Lift · " + (f"{c.brand} · " if c.brand else "") + f"risultati {c.anni}"
    return (f"<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{e(title)}</title><style>{CSS}{_page_css(c)}</style></head><body>{SYMBOLS}"
            + "\n".join(parts) + "</body></html>")
