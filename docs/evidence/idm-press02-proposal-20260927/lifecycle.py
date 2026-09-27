from modal_lifecycle import atomic
import json
from pathlib import Path

def update_inventory(local, fn):
    path = Path(local) / 'inventory.json'
    value = json.loads(path.read_text())
    fn(value)
    atomic(path, value)
