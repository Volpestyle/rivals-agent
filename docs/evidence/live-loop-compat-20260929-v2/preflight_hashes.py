"""Read-only PC byte preflight. No game input or settings attestation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent.camera_acceptance import load_yaw_compatibility

receipt = load_yaw_compatibility('alt-247-124', settings_match='alt-247-124').receipt
print('Map SHA256:', receipt['sha256'])
print('Acceptance record SHA256:', receipt['record_sha256'])
print('Map, record and pinned evidence bytes match. This is not live approval or a settings attestation.')
