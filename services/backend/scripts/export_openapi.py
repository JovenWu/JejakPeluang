import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

root = Path(__file__).resolve().parents[3]
out = root / 'packages/contracts/openapi.json'
out.write_text(json.dumps(app.openapi(), sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='')
