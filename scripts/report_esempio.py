"""Rigenera il report d'esempio per i brand (dati simulati) in demo/.

    python scripts/report_esempio.py            # HTML e, se c'e' Chromium, PDF
    python scripts/report_esempio.py --brand "Nome brand" --autore "Mario Rossi"

Stessi passi dell'app: taratura con i post finti, stima, report. Il PDF si fa
con Chromium in locale (nessun servizio esterno).
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from creatorlift import report as R  # noqa: E402
from creatorlift.io_shopify import from_simulation  # noqa: E402
from creatorlift.placebo import calibrate  # noqa: E402

CHROMIUM = ["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "chromium", "chromium-browser", "google-chrome"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="demo/report_esempio")
    ap.add_argument("--brand", default="Negozio di esempio")
    ap.add_argument("--autore", default="")
    a = ap.parse_args(argv)
    d = from_simulation(20, 1)
    cal = calibrate(d.daily, d.posts)
    est, _, fit = R.analyze(d, seed=0, widen=cal["fattore_usato"])
    res = R.results(est, d, R.DEFAULT_MARGIN)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_suffix(".html")
    html_path.write_text(R.html_report(d, res, fit, R.DEFAULT_MARGIN, cal=cal, brand=a.brand, autore=a.autore),
                         encoding="utf-8")
    print("scritto", html_path)
    chrome = next((c for c in CHROMIUM if os.path.exists(c) or shutil.which(c)), None)
    if chrome is None:
        print("Chromium non trovato: PDF non creato (si puo' stampare l'HTML dal browser)")
        return
    pdf = out.with_suffix(".pdf")
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--print-to-pdf={pdf}",
                    "--no-pdf-header-footer", html_path.resolve().as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("scritto", pdf)


if __name__ == "__main__":
    main()
