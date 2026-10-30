"""Run every numbered pipeline step (01_*.py, 02_*.py, ...) in order."""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
for step in sorted(here.glob("[0-9][0-9]_*.py")):
    print(f"== {step.name}", flush=True)
    subprocess.run([sys.executable, str(step)], check=True)
