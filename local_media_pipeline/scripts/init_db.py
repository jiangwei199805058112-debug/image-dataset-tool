from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import AppServices


if __name__ == "__main__":
    services = AppServices(ROOT)
    ok, message = services.initialize_database()
    print(message)
    raise SystemExit(0 if ok else 1)
