"""Compatibilita' con il prototipo: il simulatore ora sta in creatorlift/simulate.py.

Uso:
    python simulate.py --orders-per-day 20 --seed 1 --out dati_simulati
"""
from creatorlift.simulate import *  # noqa: F401,F403
from creatorlift.simulate import main

if __name__ == "__main__":
    main()
