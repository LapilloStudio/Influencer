"""Stile del report per il brand (CSS, simboli dei giudizi, logo).

Solo caratteri di sistema e nessuna risorsa esterna: il report si apre anche
senza connessione. Colori dei grafici come nell'app (blu = senza il creator,
arancio = con il creator); il colore d'accento (ardesia) serve solo per la
cornice del documento, mai per i dati. I giudizi hanno sempre simbolo +
testo, quindi si leggono anche stampati in bianco e nero.
"""

ACCENT = "#22344a"

CSS = r"""
:root{
  --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --hair:#e1e0d9; --axis:#c3c2b7;
  --surface:#fcfcfb; --paper:#ffffff; --desk:#ecebe5; --tint:#f3f2ed;
  --good:#0ca30c; --good-t:#006300; --serious:#ec835a;
  --accent:#22344a;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Charter, Georgia, Cambria, Caladea, "Times New Roman", serif;
  color-scheme: light;
}
*{box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact}
html{font-size:16px; -webkit-text-size-adjust:100%; background:var(--desk)}
body{margin:0; background:var(--desk); color:var(--ink); font:400 1rem/1.55 var(--sans);
  font-kerning:normal; text-rendering:optimizeLegibility}
h1,h2,h3,h4,p,ol,ul,dl,dd,figure{margin:0}
b,strong{font-weight:600}
.svg-defs{position:absolute; width:0; height:0; overflow:hidden}

/* ---------- fogli (schermo) ---------- */
.sheet{background:var(--surface); max-width:880px; margin:28px auto; padding:64px 80px 60px;
  border:1px solid var(--hair); box-shadow:0 1px 2px rgba(11,11,11,.04),0 10px 30px rgba(11,11,11,.05)}
.sheet + .sheet{margin-top:24px}

/* ---------- prima pagina ---------- */
.first{border-top:6px solid var(--accent)}
.topbar{display:flex; justify-content:space-between; align-items:center; gap:24px; padding-bottom:18px;
  border-bottom:1px solid var(--hair)}
.mark{display:flex; align-items:center; gap:10px; font:600 1rem/1 var(--sans)}
.mark svg{width:22px; height:22px; display:block}
.client{font:600 1rem/1.2 var(--sans); text-align:right}
.demo-tag{display:inline-block; font:600 .72rem/1 var(--sans); letter-spacing:.1em; text-transform:uppercase;
  color:var(--ink); border:1px solid var(--ink); padding:5px 8px}
.eyebrow{font:600 .75rem/1.3 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:var(--ink2); margin-top:36px}
h1{font:400 3rem/1.08 var(--serif); letter-spacing:-.012em; margin:14px 0 14px; max-width:15em; text-wrap:balance}
.sub-title{font-size:1.06rem; line-height:1.5; color:var(--ink2); max-width:36em}
.meta{display:flex; flex-wrap:wrap; margin-top:28px; border-top:1px solid var(--ink)}
.meta > div{flex:1 1 auto; padding:10px 16px 0 0}
.meta > div + div{padding-left:16px; border-left:1px solid var(--hair)}
.m-v{white-space:nowrap}
.m-l{font:600 .72rem/1.2 var(--sans); letter-spacing:.1em; text-transform:uppercase; color:var(--ink2); margin-bottom:5px}
.m-v{font-size:.92rem; line-height:1.35}

/* ---------- testata di sezione ---------- */
.kicker{display:flex; align-items:baseline; gap:12px; font:600 .75rem/1.2 var(--sans); letter-spacing:.14em;
  text-transform:uppercase; color:var(--ink2)}
.kicker .no{color:var(--accent); font-variant-numeric:tabular-nums; letter-spacing:.06em;
  border-top:2px solid var(--accent); padding-top:6px}
.kicker .lab{padding-top:8px}
.kicker .count{margin-left:auto; letter-spacing:.04em; text-transform:none; font-weight:500}
.action{font:400 1.95rem/1.22 var(--serif); letter-spacing:-.008em; margin:14px 0 0; max-width:26em; text-wrap:balance}
.sec-lead{margin-top:12px; color:var(--ink2); max-width:42em}
h4.sub{font:600 .75rem/1.2 var(--sans); letter-spacing:.12em; text-transform:uppercase; color:var(--ink2); margin:0 0 10px}

/* ---------- numeri chiave ---------- */
.kpis{display:grid; grid-template-columns:repeat(4,1fr); border-top:2px solid var(--ink); border-bottom:1px solid var(--hair); margin-top:32px}
.kpi{padding:14px 16px 16px 0}
.kpi + .kpi{padding-left:16px; border-left:1px solid var(--hair)}
.kpi-l{font:600 .72rem/1.3 var(--sans); letter-spacing:.06em; text-transform:uppercase; color:var(--ink2); min-height:2.6em}
.kpi-v{font:400 2.6rem/1.05 var(--serif); letter-spacing:-.01em; margin:8px 0 6px; font-variant-numeric:lining-nums tabular-nums; white-space:nowrap}
.kpi-v .u{font-size:.55em; letter-spacing:0}
.kpi-v .su{font-size:.55em; color:var(--ink2); letter-spacing:0}
.kpi-v--txt{font:italic 400 1.25rem/1.2 var(--serif); white-space:normal}
.kpi-s{font-size:.82rem; line-height:1.4; color:var(--ink2)}
.icons{display:flex; gap:3px; margin:2px 0 4px}
.icons .vi{width:15px; height:15px}

.block{display:grid; grid-template-columns:10rem 1fr; gap:24px; margin-top:28px}
.punto p{font:400 1.1rem/1.6 var(--serif)}
.punto p + p{margin-top:8px}
.recs ol{list-style:none; padding:0; counter-reset:r}
.recs li{counter-increment:r; position:relative; padding:10px 0 10px 2.2rem; border-top:1px solid var(--hair); font-size:.95rem}
.recs li:last-child{border-bottom:1px solid var(--hair)}
.recs li::before{content:counter(r); position:absolute; left:0; top:8px; font:400 1.25rem/1.2 var(--serif); color:var(--accent)}
.recs li b{display:block; margin-bottom:2px}
.warn{margin-top:24px; border:1px solid var(--serious); background:#fff8f4; padding:12px 16px; font-size:.9rem}
.warn ul{margin:6px 0 0; padding-left:1.2em}
.note{margin-top:18px; font-size:.78rem; line-height:1.5; color:var(--ink2); max-width:56em}

/* ---------- giudizi ---------- */
.vi{width:1.05em; height:1.05em; flex:none; display:inline-block; vertical-align:-.17em}
.vt{display:inline-flex; align-items:flex-start; gap:.45em; line-height:1.3}
.vt .vi{margin-top:.08em}
.badge{display:inline-flex; align-items:center; gap:.5em; font:600 .82rem/1 var(--sans); white-space:nowrap;
  padding:.5em .85em .5em .55em; border:1px solid var(--axis); border-radius:999px; background:var(--paper)}
.badge .vi{width:1.15em; height:1.15em}

/* ---------- grafico "si sono ripagati?" ---------- */
.exhibit{break-inside:avoid; page-break-inside:avoid; margin-top:26px}
.ex-h{display:flex; justify-content:space-between; align-items:baseline; gap:10px 16px; flex-wrap:wrap;
  padding-bottom:10px; border-bottom:1px solid var(--hair); margin-bottom:4px}
.ex-t{font:600 .95rem/1.35 var(--sans)}
.legend{display:flex; flex-wrap:wrap; gap:6px 16px; font-size:.78rem; color:var(--ink2)}
.legend span{display:inline-flex; align-items:center; gap:6px}
.sw{display:inline-block; flex:none}
.sw-dot{width:10px; height:10px; border-radius:50%; background:var(--good)}
.sw-dot2{width:10px; height:10px; border-radius:50%; background:var(--ink2)}
.sw-ring{width:10px; height:10px; border-radius:50%; border:2px solid var(--ink2); background:var(--paper)}
.sw-bar{width:14px; height:6px; border-radius:3px; background:#9ed79e}
.sw-bar2{width:14px; height:6px; border-radius:3px; background:#d6d5ce}
.sw-be{width:0; height:14px; border-left:2px solid var(--ink)}
.sw-zone{width:16px; height:12px; background:var(--tint); border:1px solid var(--hair)}
.sw-diamond{width:9px; height:9px; background:var(--ink); transform:rotate(45deg); margin:0 2px}

.rc{display:grid; grid-template-columns:13rem minmax(0,1fr); column-gap:18px; font-variant-numeric:tabular-nums}
.rc-name{border-top:1px solid var(--hair); padding:3px 0; display:flex; flex-direction:column; justify-content:center; gap:1px; min-width:0}
.rc-name b{font-weight:600; font-size:.9rem; overflow-wrap:anywhere}
.rc-name b span{font-weight:400; color:var(--ink2); font-size:.8rem}
.rc-name .vt{font-size:.78rem; color:var(--ink2)}
.rc-trk{position:relative; border-top:1px solid var(--hair); min-height:2.4rem}
.rc-head{position:relative; height:1.9rem}
.zone{position:absolute; top:0; bottom:0; left:0; background:var(--tint)}
.gl{position:absolute; top:0; bottom:0; width:0; border-left:1px solid #ebeae4}
.be{position:absolute; top:0; bottom:0; width:0; border-left:2px solid var(--ink); margin-left:-1px; z-index:2}
.be-lab{position:absolute; bottom:4px; white-space:nowrap; padding-left:7px; font:600 .78rem/1.1 var(--sans); color:var(--ink)}
.be-lab span{font-weight:400; color:var(--ink2)}
.bar{position:absolute; top:62%; height:6px; margin-top:-3px; border-radius:3px; z-index:1; min-width:4px}
.bar--pos{background:#9ed79e}
.bar--neu{background:#d6d5ce}
.dot{position:absolute; top:62%; width:12px; height:12px; margin:-6px 0 0 -6px; border-radius:50%; z-index:3}
.dot--pos{background:var(--good); box-shadow:0 0 0 2px var(--surface)}
.dot--neu{background:var(--ink2); box-shadow:0 0 0 2px var(--surface)}
.dot--zero{background:var(--surface); border:2px solid var(--ink2)}
.dv{position:absolute; top:6px; transform:translateX(-50%); font:600 .78rem/1 var(--sans); color:var(--ink); z-index:3; white-space:nowrap}
.trk-txt{position:absolute; left:8px; top:50%; transform:translateY(-50%); font-size:.82rem; color:var(--ink2); font-style:italic}
.rc-ax{position:relative; height:24px; border-top:1px solid var(--axis)}
.tk{position:absolute; top:5px; transform:translateX(-50%); font-size:.76rem; color:var(--ink2)}
.tk--be{font-weight:700; color:var(--ink)}
.tk--end{transform:translateX(-100%)}
.rc-axt{font-size:.78rem; color:var(--ink2); padding-top:2px}
.fig-c{font-size:.8rem; line-height:1.5; color:var(--ink2); margin-top:10px; max-width:56em}
.truth{position:absolute; top:62%; width:11px; height:11px; margin:-5.5px 0 0 -5.5px; background:var(--ink); transform:rotate(45deg); z-index:4; box-shadow:0 0 0 2px var(--surface)}

/* ---------- tabella ---------- */
.tbl{width:100%; border-collapse:collapse; font-size:.86rem; font-variant-numeric:tabular-nums}
.tbl thead th{font:600 .72rem/1.25 var(--sans); letter-spacing:.04em; text-transform:uppercase; color:var(--ink2);
  text-align:left; vertical-align:bottom; padding:0 8px 7px; border-bottom:1px solid var(--ink)}
.th-sub{display:block; text-transform:none; letter-spacing:0; font-weight:400; font-size:.72rem; margin-top:2px}
.tbl tbody th,.tbl td,.tbl tfoot th{padding:5px 8px; border-bottom:1px solid var(--hair); vertical-align:top; text-align:left}
.tbl tbody th,.tbl tfoot th{font-weight:500; overflow-wrap:anywhere}
.tbl th:first-child,.tbl td:first-child{padding-left:0}
.tbl th:last-child,.tbl td:last-child{padding-right:0}
.tbl .num{text-align:right}
.tbl td small{display:block; font-size:.76rem; color:var(--ink2); margin-top:1px; white-space:nowrap}
.tbl td.merged{text-align:center; background:var(--tint)}
.tbl .nr{font-style:italic; color:var(--ink2)}
.tbl tfoot th,.tbl tfoot td{border-top:1px solid var(--ink); border-bottom:0; font-weight:600}
.tbl tfoot td small{font-weight:400}
.tbl .vt{font-size:.8rem; white-space:nowrap}
.tbl tbody th,.tbl tfoot th{white-space:nowrap}
.tbl .nr{white-space:nowrap}

/* ---------- come leggere ---------- */
.schema{display:block; width:100%; height:auto; margin:8px 0 0}
.gloss{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:32px; border-top:1px solid var(--ink)}
.gloss > div{padding:10px 0; border-bottom:1px solid var(--hair)}
.gloss dt{font:400 1.05rem/1.3 var(--serif); margin-bottom:3px}
.gloss dd{font-size:.88rem; line-height:1.5}
.verd{display:grid; grid-template-columns:16.5rem 1fr; border-top:1px solid var(--ink)}
.verd > div{padding:9px 0; border-bottom:1px solid var(--hair); font-size:.9rem}
.verd > div:nth-child(odd){padding-right:16px}
.two{margin-top:28px}

/* ---------- schede creator ---------- */
.cr-head{display:flex; justify-content:space-between; align-items:flex-end; gap:12px 16px; flex-wrap:wrap; margin-top:14px}
.cr-name{font:400 2.2rem/1.1 var(--serif); letter-spacing:-.01em; overflow-wrap:anywhere}
.cr-meta{font-size:.86rem; color:var(--ink2); margin-top:6px}
.cr-lead{font:400 1.18rem/1.5 var(--serif); max-width:38em; margin-top:14px; text-wrap:pretty}
.stats{display:grid; grid-template-columns:repeat(4,1fr); margin:20px 0 6px; border-top:2px solid var(--ink); border-bottom:1px solid var(--hair)}
.st{padding:10px 12px 12px 0}
.st + .st{padding-left:12px; border-left:1px solid var(--hair)}
.st-l{font:600 .72rem/1.25 var(--sans); letter-spacing:.06em; text-transform:uppercase; color:var(--ink2)}
.st-v{font:400 1.85rem/1.1 var(--serif); margin:6px 0 4px; font-variant-numeric:lining-nums tabular-nums; white-space:nowrap}
.st-v .u{font-size:.6em}
.st-v--txt{font:italic 400 1.05rem/1.25 var(--serif); white-space:normal; min-height:2.03rem; display:flex; align-items:center}
.st-s{font-size:.78rem; line-height:1.4; color:var(--ink2)}

.mv{margin-top:18px}
.mv-row{display:grid; grid-template-columns:12rem minmax(0,1fr); column-gap:16px; align-items:center}
.mv-lab{font-size:.82rem; color:var(--ink2); line-height:1.25; padding:3px 0}
.mv-lab b{display:block; color:var(--ink); font-size:.95rem}
.mv-lab b.nr{font-style:italic; font-weight:500}
.mv-plot{position:relative; height:1.9rem}
.mv-plot--head{height:1.3rem}
.mv-plot--axis{height:1.3rem; border-top:1px solid var(--axis)}
.mv .bar,.mv .dot{top:50%}
.cbar{position:absolute; top:50%; height:10px; margin-top:-5px; left:0; background:#c9c8c0; border-radius:0 2px 2px 0}
.clab{position:absolute; top:50%; transform:translateY(-50%); margin-left:6px; padding:0 4px; font-size:.78rem; color:var(--ink2); white-space:nowrap; background:var(--surface); z-index:3}
.mv-be-lab{position:absolute; bottom:3px; white-space:nowrap; font:600 .76rem/1.1 var(--sans); color:var(--ink); padding:0 6px}
.mv-be-lab--r{transform:translateX(-100%)}
.mv .tk{top:4px}

.fig{margin-top:20px}
.fig-t{font:600 .9rem/1.35 var(--sans); padding-bottom:8px; border-bottom:1px solid var(--hair); margin-bottom:6px}
.fig-scroll img{display:block; width:100%; height:auto}
.fig-src{font-size:.74rem; color:var(--ink2); margin-top:4px}
.cr-foot{display:grid; grid-template-columns:1fr 1fr 1fr; gap:26px; margin-top:18px; padding-top:14px; border-top:1px solid var(--ink)}
.cr-foot p{font-size:.88rem; line-height:1.55}
.cr-foot .sub{margin-bottom:6px}

/* ---------- dati e metodo ---------- */
.facts{display:grid; grid-template-columns:13rem 1fr; border-top:1px solid var(--ink); font-size:.92rem; margin-top:26px}
.facts dt,.facts dd{padding:9px 0; border-bottom:1px solid var(--hair)}
.facts dt{color:var(--ink2); padding-right:16px}
.facts dd{font-variant-numeric:tabular-nums}
.facts dd ul{margin:0; padding-left:1.1em}
.cols2{display:grid; grid-template-columns:1fr 1fr; gap:36px; margin-top:32px}
.steps{list-style:none; padding:0; counter-reset:s}
.steps li{counter-increment:s; position:relative; padding:0 0 10px 2rem; font-size:.92rem}
.steps li::before{content:counter(s); position:absolute; left:0; top:-2px; font:400 1.1rem/1.3 var(--serif); color:var(--accent)}
.limits{padding-left:1.1em}
.limits li{margin-bottom:8px; font-size:.92rem}

/* ---------- appendice ---------- */
.demo-box{border:1px dashed var(--axis); padding:12px 16px; font-size:.88rem; color:var(--ink2); margin-top:22px; display:flex; gap:14px; align-items:flex-start}
.demo-box .demo-tag{flex:none}
.find{display:grid; grid-template-columns:repeat(auto-fit,minmax(13rem,1fr)); gap:24px; margin-top:22px}
.find h4{font:400 1.1rem/1.3 var(--serif); margin-bottom:6px}
.find p{font-size:.92rem}

/* ---------- schermo stretto ---------- */
@media screen and (max-width: 720px){
  .sheet{margin:0; padding:32px 16px 32px; border:0; border-bottom:10px solid var(--desk); box-shadow:none}
  .sheet + .sheet{margin-top:0}
  .first{border-top:6px solid var(--accent)}
  h1{font-size:2.1rem}
  .action{font-size:1.45rem}
  .meta > div{flex:1 1 45%; padding-bottom:10px}
  .meta > div:nth-child(odd){padding-left:0; border-left:0}
  .m-v{white-space:normal}
  .kpis{grid-template-columns:1fr 1fr}
  .kpi{padding:12px 10px 14px 0}
  .kpi:nth-child(3){padding-left:0; border-left:0; border-top:1px solid var(--hair)}
  .kpi:nth-child(4){border-top:1px solid var(--hair)}
  .kpi-v{font-size:2rem}
  .block{grid-template-columns:1fr; gap:8px}
  .punto p{font-size:1.03rem}
  .rc{grid-template-columns:minmax(0,1fr)}
  .rc > .rc-sp{display:none}
  .rc-name{padding:10px 0 0}
  .rc-trk{border-top:0}
  .stats{grid-template-columns:1fr 1fr}
  .st:nth-child(3){padding-left:0; border-left:0; border-top:1px solid var(--hair)}
  .st:nth-child(4){border-top:1px solid var(--hair)}
  .cr-name{font-size:1.8rem}
  .cr-lead{font-size:1.06rem}
  .cr-foot,.cols2,.find,.gloss{grid-template-columns:1fr; gap:16px}
  .mv-row{grid-template-columns:minmax(0,1fr)}
  .mv-row > .mv-sp{display:none}
  .mv-lab{padding:8px 0 0}
  .tbl thead{display:none}
  .tbl,.tbl tbody,.tbl tfoot,.tbl tr,.tbl td,.tbl th{display:block; width:100%}
  .tbl tr{padding:10px 0; border-bottom:1px solid var(--hair)}
  .tbl tbody th,.tbl tfoot th{border:0; padding:0 0 6px; font:400 1.15rem/1.2 var(--serif)}
  .tbl td{display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:4px 12px; border:0; padding:3px 0; text-align:right}
  .tbl td::before{content:attr(data-l); color:var(--ink2); font-size:.8rem; text-align:left; margin-right:auto}
  .tbl td.merged{background:none; text-align:right}
  .tbl td small{display:inline; margin-left:6px; white-space:normal}
  .tbl tfoot tr{border-top:1px solid var(--ink); border-bottom:0}
  .tbl tfoot th,.tbl tfoot td{border-top:0}
  .tbl td.empty{display:none}
  .verd{grid-template-columns:1fr}
  .verd > div:nth-child(odd){border-bottom:0; padding-bottom:2px}
  .facts{grid-template-columns:1fr}
  .facts dt{border-bottom:0; padding-bottom:2px}
  .facts dd{padding-top:2px}
  .fig-scroll{overflow-x:auto; -webkit-overflow-scrolling:touch; margin:0 -16px; padding:0 16px;
    scroll-snap-type:x proximity}
  .fig-scroll img,.fig-scroll .schema{min-width:600px}
  .fig-scroll::after{content:"Scorri il grafico in orizzontale →"; display:block; font-size:.75rem; color:var(--ink2); margin-top:6px}
  .demo-box{flex-direction:column}
}

/* ---------- stampa A4 ---------- */
@media print{
  html{font-size:10pt; background:#fcfcfb}
  body{background:#fcfcfb}
  .sheet{max-width:none; margin:0; padding:0; border:0; box-shadow:none; background:transparent;
    break-before:page; page-break-before:always}
  .sheet:first-of-type{break-before:auto; page-break-before:auto}
  .sheet + .sheet{margin-top:0}
  .first{border-top:3px solid var(--accent); padding-top:7mm}
  .eyebrow{margin-top:7mm}
  h1{font-size:2.6rem; margin:8px 0 8px}
  .meta{margin-top:18px}
  .kpis{margin-top:20px}
  .block{margin-top:16px}
  .punto p{font-size:1.04rem; line-height:1.55}
  .recs li{padding:7px 0 7px 2.2rem; font-size:.92rem}
  .schema{max-height:54mm; width:auto; max-width:100%; margin:4px auto 0}
  .gloss > div{padding:6px 0}
  .gloss dd{font-size:.84rem; line-height:1.45}
  .verd > div{padding:6px 0; font-size:.86rem}
  .two{margin-top:16px}
  .exhibit{margin-top:16px}
  .action{font-size:1.75rem}
  .facts dt,.facts dd{padding:7px 0}
  .tbl td small{font-size:.74rem}
  .cr-lead{font-size:1.1rem; margin-top:10px}
  .stats{margin-top:14px}
  .mv{margin-top:12px}
  .fig{margin-top:12px}
  .cr-foot{margin-top:12px; padding-top:10px}
  .cr-foot p{font-size:.84rem; line-height:1.5}
  .fig-scroll::after{display:none}
  .exhibit,.stats,.mv,.fig,.cr-foot,.kpis,.recs li,.verd > div,.gloss > div{break-inside:avoid; page-break-inside:avoid}
  .ex-h,.fig-t,h4.sub{break-after:avoid; page-break-after:avoid}
  .fig-scroll img{max-height:150mm; width:auto; max-width:100%}
  .badge{background:#fff}
}
"""

# simboli dei giudizi: simbolo + testo, mai il solo colore
SYMBOLS = """<svg class="svg-defs" aria-hidden="true" focusable="false">
  <symbol id="v-certo" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="7.25" fill="#0ca30c"/>
    <path d="M4.6 8.3l2.2 2.2 4.6-4.7" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
  </symbol>
  <symbol id="v-prob" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="6.6" fill="#fff" stroke="#0ca30c" stroke-width="1.5"/>
    <path d="M5 8.3l2 2 4-4.2" fill="none" stroke="#006300" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
  </symbol>
  <symbol id="v-noripaga" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="7.25" fill="#ec835a"/>
    <path d="M8 4.2v4.9" stroke="#0b0b0b" stroke-width="1.8" stroke-linecap="round"/>
    <circle cx="8" cy="11.6" r="1.05" fill="#0b0b0b"/>
  </symbol>
  <symbol id="v-nessuno" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="6.6" fill="#fff" stroke="#898781" stroke-width="1.5"/>
    <path d="M4.4 8.9c1.2-1.9 2.4-1.9 3.6 0s2.4 1.9 3.6 0" fill="none" stroke="#52514e" stroke-width="1.6" stroke-linecap="round"/>
  </symbol>
  <symbol id="v-insuff" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="7.25" fill="#fab219"/>
    <path d="M6 6.3a2 2 0 1 1 2.9 1.8c-.6.3-.9.7-.9 1.3v.4" fill="none" stroke="#0b0b0b" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="8" cy="11.9" r="1" fill="#0b0b0b"/>
  </symbol>
  <symbol id="i-si" viewBox="0 0 16 16">
    <path d="M3.5 8.4l2.8 2.8 6.2-6.4" fill="none" stroke="#0ca30c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </symbol>
  <symbol id="i-no" viewBox="0 0 16 16">
    <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="#d03b3b" stroke-width="2" stroke-linecap="round"/>
  </symbol>
</svg>"""

LOGO = ('<svg viewBox="0 0 22 22" aria-hidden="true"><rect x="0.5" y="0.5" width="21" height="21" fill="#22344a"/>'
        '<path d="M5 15.5l4-4 3 2.5 5-6.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="square"/></svg>')
