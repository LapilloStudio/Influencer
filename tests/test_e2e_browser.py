"""Prova completa nel browser: l'app vera, usata con Chromium, non fa nessuna
richiesta di rete fuori da questo computer (ne' dal browser ne' da Python).

Serve il pacchetto playwright e un Chromium; senza, il test viene saltato.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
CHROMIUM = os.environ.get("CREATORLIFT_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    if not Path(CHROMIUM).exists():
        pytest.skip("Chromium non trovato (variabile CREATORLIFT_CHROMIUM)")
    log = tmp_path_factory.mktemp("rete") / "connessioni.log"
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(ROOT / "tests/e2e/avvia_con_controllo_rete.py"), str(log), str(port)],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("l'app non si e' avviata")
    yield url, log
    proc.terminate()
    proc.wait(timeout=20)


def test_nessuna_richiesta_esterna(server, tmp_path):
    url, log = server
    host = urlparse(url).netloc
    richieste = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        page = browser.new_page(accept_downloads=True, viewport={"width": 1300, "height": 900})
        page.on("request", lambda r: richieste.append(r.url))
        page.on("websocket", lambda ws: richieste.append(ws.url))
        page.goto(url)
        page.get_by_text("Dati simulati", exact=True).click()
        page.get_by_role("button", name="Usa dati simulati").click()
        page.get_by_role("heading", name="Risultati").wait_for(timeout=120_000)
        page.get_by_text("Confronto con la verità").wait_for(timeout=60_000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(tmp_path / "risultati.png"), full_page=True)
        with page.expect_download(timeout=120_000) as dl:
            page.get_by_role("button", name="Scarica il report").click()
        report = Path(dl.value.path()).read_text(encoding="utf-8")
        assert "Quanto hanno venduto davvero i creator" in report
        assert "http://" not in report and "https://" not in report
        # la pagina resta sui risultati dopo un'interazione
        page.get_by_role("heading", name="Risultati").wait_for(timeout=30_000)
        browser.close()

    esterne = [u for u in richieste if urlparse(u).scheme not in ("data", "blob") and urlparse(u).netloc != host]
    assert esterne == [], esterne
    assert len(richieste) > 5
    python_side = log.read_text().strip()
    assert python_side == "", python_side
