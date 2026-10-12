"""Compatibilita' con il prototipo: il motore ora sta in creatorlift/model.py.

Uso:
    python estimate.py dati_simulati
"""
from creatorlift.model import *  # noqa: F401,F403
from creatorlift.model import main

if __name__ == "__main__":
    main()
