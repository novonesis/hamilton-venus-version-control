import sys
from pathlib import Path

_deployment_dir = str(Path(__file__).resolve().parent.parent / "Deployment")
if _deployment_dir not in sys.path:
    sys.path.insert(0, _deployment_dir)
