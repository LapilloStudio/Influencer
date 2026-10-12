"""Controlli perche' nessun dato esca dal computer quando gira l'app.

Le impostazioni stanno in .streamlit/config.toml accanto ad app.py. Qui si
verifica all'avvio che siano davvero attive (un'altra configurazione
dell'utente o una variabile d'ambiente potrebbe cambiarle) e si spengono le
due funzioni di Streamlit che cercano l'indirizzo IP del computer su Internet.
"""

EXPECTED = {
    "browser.gatherUsageStats": False,
    "server.showEmailPrompt": False,
    "server.enableCORS": True,
    "server.enableXsrfProtection": True,
    "global.developmentMode": False,
}
LOCAL_ADDRESSES = {"127.0.0.1", "localhost", "::1"}


def problems(get_option) -> list[str]:
    """Elenco (in italiano) delle impostazioni che non garantiscono la privacy."""
    out = []
    for name, value in EXPECTED.items():
        if get_option(name) != value:
            out.append(f"l'opzione {name} dovrebbe essere {str(value).lower()}")
    if get_option("server.address") not in LOCAL_ADDRESSES:
        out.append("l'app e' raggiungibile da altri computer della rete (server.address)")
    if (get_option("theme.base") or "").startswith(("http://", "https://")):
        out.append("il tema viene scaricato da Internet (theme.base)")
    return out


def disable_ip_lookup():
    """Streamlit, per controllare da dove arriva una connessione, puo'
    chiedere a un servizio esterno l'indirizzo IP pubblico del computer.
    All'app basta l'indirizzo locale."""
    from streamlit import net_util

    net_util.get_external_ip = lambda: None
    net_util.get_internal_ip = lambda: "127.0.0.1"
