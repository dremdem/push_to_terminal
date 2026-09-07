import sys
from pathlib import Path

# lingua_core.py sits at the package root — the same place Sublime loads it from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
