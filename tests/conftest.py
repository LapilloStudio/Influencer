import sys
from pathlib import Path

# permette "pytest" dalla radice del progetto senza installare il pacchetto
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
