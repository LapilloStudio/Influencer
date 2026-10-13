"""Risultati in parole semplici: tabella, frasi, grafici e report HTML.

Niente gergo statistico nei testi per l'utente: "intervallo probabile" e non
"intervallo di confidenza", "ritorno sul margine" spiegato in euro. Un ROI
negativo non viene mai mostrato come numero: si scrive "nessun effetto
rilevato". I grafici sono immagini PNG (matplotlib) incorporate nel report,
che quindi si apre anche senza connessione.
"""
from __future__ import annotations

import base64
import html
import io
from datetime import datetime

import matplotlib.ticker
import numpy as np
import pandas as pd
from matplotlib.figure import Figure  # niente pyplot: i grafici si possono creare da piu' thread

from creatorlift.io_shopify import EXCLUSION_LABELS, ShopData
from creatorlift.model import Fit, daily_paths, estimate, verdict

DEFAULT_MARGIN = 0.55
NO_EFFECT = "nessun effetto rilevato"
NOT_ENOUGH = "dati insufficienti"

# colori (palette validata per daltonismo, 2 serie): blu = senza il creator,
# arancio = con il creator; testi e assi in grigi neutri
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

# accordo singolare/plurale: "il post ... si è ripagato", "i post ... si sono ripagati"
VERB = {
    False: {"rip": "si è ripagato", "rip_cong": "si sia ripagato"},
    True: {"rip": "si sono ripagati", "rip_cong": "si siano ripagati"},
}


# ---------------------------------------------------------------- numeri all'italiana

def fmt_int(x) -> str:
    return f"{int(round(float(x))):,}".replace(",", ".")


def fmt_dec(x, digits=1) -> str:
    s = f"{float(x):,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_eur(x) -> str:
    x = float(x)
    return f"{fmt_int(x)}\u00a0€" if abs(x - round(x)) < 0.005 else f"{fmt_dec(x, 2)}\u00a0€"


def fmt_date(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


# ---------------------------------------------------------------- calcolo

def analyze(data: ShopData, seed: int = 0, widen: float = 1.0):
    """Esegue il motore una volta; il margine si applica dopo (`results`).
    `widen`: fattore di taratura (creatorlift.placebo.calibrate)."""
    est, shape, fit = estimate(data.daily, data.posts, seed=seed, aov=data.aov, margin=DEFAULT_MARGIN,
                               return_fit=True, widen=widen)
    return est, shape, fit


def calibration_text(cal: dict | None) -> str:
    """Una frase sulla taratura, per l'app e il report."""
    if not cal:
        return ""
    n = fmt_int(cal["creator_finti"])
    if cal["fattore_usato"] > 1.0:
        return (f"Controllo di affidabilità: con {n} creator inventati, su questo negozio il calcolo era troppo "
                f"sicuro di sé, quindi gli intervalli sono stati allargati di {fmt_dec(cal['fattore_usato'], 2)} "
                "volte. I giudizi sono di conseguenza più prudenti.")
    return (f"Controllo di affidabilità: con {n} creator inventati, su questo negozio gli intervalli si sono "
            "dimostrati affidabili e non sono stati modificati.")


def results(est: pd.DataFrame, data: ShopData, margin: float) -> pd.DataFrame:
    """Numeri per creator con il margine scelto. Stessa formula del motore:
    ROI = vendite in piu' x scontrino medio x margine / costo."""
    r = est[["creator", "incremental_orders", "low_90", "high_90", "prob_effect_positive", "cost_eur"]].copy()
    cost = r["cost_eur"].replace(0, np.nan)
    for src, dst in (("incremental_orders", "roi"), ("low_90", "roi_low"), ("high_90", "roi_high")):
        r[dst] = (r[src] * data.aov * margin / cost).round(2)
    r["giudizio"] = r.apply(verdict, axis=1)
    r.loc[r["cost_eur"] == 0, "giudizio"] = r.loc[r["cost_eur"] == 0, "prob_effect_positive"].map(
        lambda p: "porta vendite (costo zero)" if p >= 0.95 else "nessun effetto chiaro")
    r["estimable"] = np.isfinite(r[["incremental_orders", "low_90", "high_90"]]).all(axis=1)
    r.loc[~r["estimable"], "giudizio"] = NOT_ENOUGH
    r["orders_with_code"] = r["creator"].map(data.orders_with_code)
    r["n_posts"] = r["creator"].map(data.posts.groupby("creator").size())
    r["margin_eur"] = r["incremental_orders"] * data.aov * margin
    # prima chi rende di piu'
    rank = {g: i for i, g in enumerate(["si ripaga quasi certamente", "probabilmente si ripaga",
                                        "porta vendite (costo zero)", "porta vendite ma non si ripaga",
                                        "nessun effetto chiaro", NOT_ENOUGH])}
    r["_rank"] = r["giudizio"].map(rank)
    r = r.sort_values(["_rank", "roi"], ascending=[True, False], na_position="last").drop(columns="_rank")
    return r.reset_index(drop=True)


def _interval(lo, hi, unit="") -> str:
    lo, hi = max(float(lo), 0.0), max(float(hi), 0.0)
    return f"tra {fmt_int(lo)} e {fmt_int(hi)}{unit}"


def _roi_text(x) -> str:
    return NO_EFFECT if not np.isfinite(x) or x < 0 else fmt_dec(x, 1)


def display_table(res: pd.DataFrame) -> pd.DataFrame:
    """Tabella per l'utente, gia' formattata come testo."""
    rows = []
    for r in res.itertuples(index=False):
        ok = r.estimable
        code = "senza codice" if r.orders_with_code is None or pd.isna(r.orders_with_code) else fmt_int(r.orders_with_code)
        if not ok:
            extra, interval, roi = NOT_ENOUGH, NOT_ENOUGH, NOT_ENOUGH
        else:
            extra = NO_EFFECT if r.incremental_orders < 0 else fmt_int(r.incremental_orders)
            interval = _interval(r.low_90, r.high_90)
            if not np.isfinite(r.roi):
                roi = "costo zero"
            else:
                roi = _roi_text(r.roi)
        rows.append({
            "Creator": r.creator,
            "Post": int(r.n_posts),
            "Ordini con codice": code,
            "Vendite in più stimate": extra,
            "Intervallo probabile": interval,
            "Costo": fmt_eur(r.cost_eur),
            "ROI sul margine": roi,
            "Giudizio": r.giudizio,
        })
    return pd.DataFrame(rows)


def sentence(r) -> str:
    """Una frase per creator, per il titolare del brand."""
    plural = r.n_posts > 1
    chi = f"I {r.n_posts} post di {r.creator}" if plural else f"Il post di {r.creator}"
    v = VERB[plural]
    costo = fmt_eur(r.cost_eur)
    if not r.estimable:
        return (f"Per {r.creator} i dati non bastano a stimare l'effetto: nei giorni dopo il post ci sono troppo pochi "
                "ordini.")
    lo, hi = max(r.low_90, 0), max(r.high_90, 0)
    if r.giudizio == "nessun effetto chiaro":
        if hi <= 0:
            return f"{chi} non ha portato vendite in più che si possano vedere nei dati. Il costo è stato di {costo}."
        return (f"Per {chi[0].lower() + chi[1:]} non si vede un effetto chiaro: le vendite in più stanno tra "
                f"{fmt_int(lo)} e {fmt_int(hi)} ordini, quindi potrebbero anche essere nessuna. "
                f"Con un costo di {costo}, non ci sono prove che {v['rip_cong']}.")
    base = f"{chi} {'hanno' if plural else 'ha'} portato tra {fmt_int(lo)} e {fmt_int(hi)} ordini in più"
    if r.giudizio == "porta vendite (costo zero)":
        return base + "."
    if r.giudizio == "porta vendite ma non si ripaga":
        return f"{base}, ma con un costo di {costo} probabilmente non {v['rip']}."
    if r.giudizio == "probabilmente si ripaga":
        return f"{base}. Con un costo di {costo}, probabilmente {v['rip']}, ma non è sicuro."
    return f"{base}. Con un costo di {costo}, quasi certamente {v['rip']}."


def code_note(r) -> str:
    if r.orders_with_code is None or pd.isna(r.orders_with_code) or not r.estimable:
        return ""
    n = int(r.orders_with_code)
    return f"Gli ordini con il suo codice sconto sono {fmt_int(n)}."


def truth_table(res: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    m = res.merge(truth[["creator", "true_incremental_orders"]], on="creator")
    rows = []
    for r in m.itertuples(index=False):
        inside = r.low_90 <= r.true_incremental_orders <= r.high_90
        rows.append({
            "Creator": r.creator,
            "Effetto vero (ordini in più)": fmt_int(r.true_incremental_orders),
            "Stima": (NO_EFFECT if r.incremental_orders < 0 else fmt_int(r.incremental_orders))
            if r.estimable else NOT_ENOUGH,
            "Intervallo probabile": _interval(r.low_90, r.high_90) if r.estimable else NOT_ENOUGH,
            "Il vero è nell'intervallo?": "sì" if inside else "no",
            "Ordini con codice": "senza codice" if pd.isna(r.orders_with_code) else fmt_int(r.orders_with_code),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- grafici

def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def creator_figure(fit: Fit, data: ShopData, creator: str, before: int = 7, after: int = 20):
    """Ordini reali giorno per giorno attorno a ogni post, previsione senza il
    creator con la fascia di variazione normale, previsione con il creator."""
    p = daily_paths(fit, creator)
    dates = pd.to_datetime(p["date"])
    post_days = sorted(pd.to_datetime(data.posts.loc[data.posts.creator == creator, "date"]).unique())
    n = len(post_days)
    cols = min(n, 2)
    rows = int(np.ceil(n / cols))
    fig = Figure(figsize=(8.5, 3.0 * rows + 0.7))
    axes = fig.subplots(rows, cols, squeeze=False, sharey=True)
    windows = [(dates >= d0 - pd.Timedelta(days=before)) & (dates <= d0 + pd.Timedelta(days=after)) for d0 in post_days]
    ymax = max(float(np.nanmax(p.loc[w.to_numpy(), ["orders", "with_creator", "without_creator", "normal_hi"]]
                               .to_numpy(dtype=float))) for w in windows)
    fig.patch.set_facecolor(SURFACE)
    for k, ax in enumerate(axes.flat):
        if k >= n:
            ax.set_visible(False)
            continue
        d0 = post_days[k]
        q = p[windows[k].to_numpy()]
        x = (pd.to_datetime(q["date"]) - d0).dt.days.to_numpy()
        _style(ax)
        ax.fill_between(x, q["normal_lo"], q["normal_hi"], color=BLUE, alpha=0.12, linewidth=0,
                        label="variazione normale senza il creator (9 giorni su 10)")
        ax.plot(x, q["without_creator"], color=BLUE, linewidth=2, solid_capstyle="round",
                label="previsione senza il creator")
        ax.plot(x, q["with_creator"], color=ORANGE, linewidth=2, solid_capstyle="round",
                label="previsione con il creator")
        ax.plot(x, q["orders"], linestyle="none", marker="o", markersize=4.5, color=INK2,
                markeredgecolor=SURFACE, markeredgewidth=1, label="ordini reali")
        ax.axvline(0, color=MUTED, linewidth=1)
        ax.set_title(f"Post del {fmt_date(d0)}", fontsize=10, color=INK, loc="left")
        ticks = [t for t in (-7, 0, 7, 14) if x.min() <= t <= x.max()]
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{t:+d} gg" if t else "giorno 0" for t in ticks])
        ax.set_ylim(0, ymax * 1.06)
        if k % cols == 0:
            ax.set_ylabel("ordini al giorno", color=INK2, fontsize=9)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    order = [3, 2, 1, 0]
    fig.legend([handles[i] for i in order], [labels[i] for i in order], loc="upper left", ncol=2, frameon=False,
               fontsize=9, labelcolor=INK2, bbox_to_anchor=(0.01, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.65 / fig.get_figheight()))
    return fig


def roi_figure(res: pd.DataFrame):
    """Per ogni creator: stima del ROI (punto) e intervallo probabile al 90%
    (barra), con la linea a ROI = 1 oltre la quale il costo si ripaga.
    I valori sotto zero sono disegnati a zero: un ROI negativo non ha senso
    per chi legge e significa 'nessun effetto rilevato'."""
    r = res[np.isfinite(res["roi"].astype(float)) | ~res["estimable"]].copy()
    r["_sort"] = r["roi"].fillna(-np.inf)
    r = r.sort_values("_sort", ascending=True).reset_index(drop=True)
    fig = Figure(figsize=(8.5, 0.55 * len(r) + 1.3))
    ax = fig.subplots()
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    hi_all = r.loc[r["estimable"], "roi_high"].clip(lower=0)
    xmax = max(1.5, float(hi_all.max()) * 1.08 if len(hi_all) else 1.5)
    for i, row in r.iterrows():
        if not row["estimable"]:
            ax.text(0.02 * xmax, i, NOT_ENOUGH, va="center", color=MUTED, fontsize=9)
            continue
        lo, hi, pt = max(row["roi_low"], 0), max(row["roi_high"], 0), row["roi"]
        ax.plot([lo, hi], [i, i], color=BLUE, linewidth=6, alpha=0.35, solid_capstyle="round")
        if pt >= 0:
            ax.plot(pt, i, "o", color=BLUE, markersize=9, markeredgecolor=SURFACE, markeredgewidth=2, clip_on=False,
                    zorder=3)
        else:
            ax.plot(0, i, "o", markerfacecolor=SURFACE, markeredgecolor=BLUE, markersize=8, markeredgewidth=1.5,
                    clip_on=False, zorder=3)
        ax.text(xmax * 1.01, i, row["giudizio"], va="center", color=INK2, fontsize=9, clip_on=False)
    ax.axvline(1, color=INK2, linewidth=1)
    ax.text(1, len(r) - 0.35, " ROI = 1: il costo si ripaga", color=INK2, fontsize=9, va="bottom")
    ax.tick_params(axis="y", pad=12)
    ax.set_yticks(range(len(r)))
    ax.set_yticklabels(r["creator"], color=INK, fontsize=10)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, len(r) - 0.1)
    ax.set_xlabel("ROI sul margine: euro di margine guadagnati per ogni euro speso", color=INK2, fontsize=9)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt_dec(v, 1 if v % 1 else 0)))
    fig.tight_layout(rect=(0, 0, 0.78, 1))
    return fig


def fig_png(fig, dpi=144) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    return buf.getvalue()


# ---------------------------------------------------------------- report HTML

CSS = """
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#0b0b0b;background:#f9f9f7;margin:0}
main{max-width:960px;margin:0 auto;padding:32px 20px 64px;background:#fcfcfb}
h1{font-size:28px;margin:0 0 4px} h2{font-size:20px;margin:36px 0 10px} h3{font-size:16px;margin:24px 0 6px}
p,li{line-height:1.5} .muted{color:#52514e} .small{font-size:13px}
.box{border:1px solid #e1e0d9;border-radius:8px;padding:12px 16px;margin:12px 0;background:#fff}
.warn{border-color:#ec835a;background:#fff8f4}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #e1e0d9;vertical-align:top}
th{color:#52514e;font-weight:600} td.num{font-variant-numeric:tabular-nums}
img{max-width:100%;height:auto;display:block;margin:6px 0 14px}
.verdict{white-space:nowrap}
@media print{body{background:#fff} main{padding:0} h2{break-after:avoid} img,table{break-inside:avoid}}
"""


def _table_html(df: pd.DataFrame) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>" for row in df.itertuples(index=False)
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _img(png: bytes, alt: str) -> str:
    return f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{base64.b64encode(png).decode()}">'


def html_report(data: ShopData, res: pd.DataFrame, fit: Fit, margin: float, now: datetime | None = None,
                cal: dict | None = None) -> str:
    now = now or datetime.now()
    e = html.escape
    first, last = data.daily["date"].iloc[0], data.daily["date"].iloc[-1]
    parts = [f"<!doctype html><html lang='it'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Creator Lift: risultati</title><style>{CSS}</style></head><body><main>"]
    parts.append("<h1>Quanto hanno venduto davvero i creator</h1>")
    origine = "dati simulati" if data.origine == "simulati" else "export degli ordini di Shopify"
    parts.append(f"<p class='muted'>Periodo {e(fmt_date(first))} – {e(fmt_date(last))} · {e(origine)} · "
                 f"report creato il {e(fmt_date(now))}</p>")

    parts.append("<h2>In breve</h2><ul>")
    for r in res.itertuples(index=False):
        note = code_note(r)
        parts.append(f"<li>{e(sentence(r))}{(' ' + e(note)) if note else ''}</li>")
    parts.append("</ul>")

    avvisi = [a for a in data.avvisi if a.livello == "importante"]
    if avvisi:
        parts.append("<div class='box warn'><strong>Da tenere presente</strong><ul>"
                     + "".join(f"<li>{e(a.testo)}</li>" for a in avvisi) + "</ul></div>")

    parts.append("<h2>Tabella per creator</h2>")
    parts.append(_table_html(display_table(res)))
    parts.append(
        f"<p class='small muted'>Le <em>vendite in più</em> sono gli ordini che non ci sarebbero stati senza i post, "
        f"con o senza codice sconto. L'<em>intervallo probabile</em> contiene il valore vero 9 volte su 10; se parte "
        f"da 0, il creator potrebbe non aver portato nessuna vendita in più. Il <em>ROI sul margine</em> dice quanti "
        f"euro di margine sono tornati per ogni euro speso: sopra 1 la collaborazione si è ripagata. Calcolato con "
        f"{e(data.aov_label)} di {e(fmt_eur(data.aov))} e margine lordo del {e(fmt_int(margin * 100))}%.</p>")

    parts.append("<h2>Si sono ripagati?</h2>")
    parts.append(_img(fig_png(roi_figure(res)), "ROI sul margine per creator con intervallo probabile"))
    parts.append("<p class='small muted'>Il punto è la stima, la barra l'intervallo probabile. A destra della linea "
                 "verticale il costo si è ripagato. Un cerchio vuoto sullo zero vuol dire nessun effetto rilevato.</p>")

    parts.append("<h2>Giorno per giorno, attorno a ogni post</h2>")
    parts.append("<p class='small muted'>I punti sono gli ordini reali. La linea blu è quanti ordini ci si "
                 "aspettava senza il creator, la fascia azzurra la variazione normale da un giorno all'altro. "
                 "La linea arancione è la previsione che tiene conto del creator: la distanza tra le due linee "
                 "sono le vendite in più.</p>")
    for r in res.itertuples(index=False):
        parts.append(f"<h3>{e(r.creator)}</h3><p class='small'>{e(sentence(r))}</p>")
        parts.append(_img(fig_png(creator_figure(fit, data, r.creator)), f"Ordini attorno ai post di {r.creator}"))

    if data.truth is not None:
        parts.append("<h2>Confronto con la verità (dati simulati)</h2>")
        parts.append("<p class='small muted'>Nei dati simulati l'effetto vero di ogni creator è noto: qui si "
                     "vede se la stima lo ritrova.</p>")
        parts.append(_table_html(truth_table(res, data.truth)))

    parts.append("<h2>Come è stato calcolato</h2>")
    esclusi = "".join(f"<li>{fmt_int(v)} ordini {e(EXCLUSION_LABELS[k])}</li>" for k, v in data.esclusi.items())
    parts.append(
        "<p class='small'>Gli ordini di ogni giorno vengono spiegati con l'andamento del negozio, il giorno della "
        "settimana, la stagione e i giorni di promozione. Per ogni creator si misura quanto salgono gli ordini il "
        "giorno del post, nei 2 giorni dopo, nei giorni da 3 a 6 e da 7 a 13. Le vendite in più sono la differenza "
        "tra gli ordini previsti con i post e quelli previsti senza. L'intervallo probabile si ottiene ripetendo il "
        f"calcolo 2.000 volte. Dati: {fmt_int(data.n_days)} giorni, in media {fmt_dec(data.orders_per_day, 1)} "
        "ordini al giorno.</p>")
    if cal:
        parts.append(f"<p class='small'>{e(calibration_text(cal))}</p>")
    if esclusi:
        parts.append(f"<p class='small'>Ordini non contati:</p><ul class='small'>{esclusi}</ul>")
    info = [a for a in data.avvisi if a.livello != "importante"]
    if info:
        parts.append("<ul class='small muted'>" + "".join(f"<li>{e(a.testo)}</li>" for a in info) + "</ul>")
    parts.append("</main></body></html>")
    return "".join(parts)
