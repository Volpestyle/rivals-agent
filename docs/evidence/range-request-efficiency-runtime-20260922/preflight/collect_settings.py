"""Read only named persisted settings; write a scoped receipt, never a binding."""
import configparser
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'data/runtime/range-skill-candidate-20260922/current-saved-settings.json'
USER = Path('C:/Users/volpe/AppData/Local/Marvel/Saved/Saved/Config/1295996384/MarvelUserSetting.json')
VER = Path('C:/Program Files (x86)/Steam/steamapps/common/MarvelRivals/MarvelGame/version.json')
APP = Path('C:/Program Files (x86)/Steam/steamapps/appmanifest_2767030.acf')
DISPLAY = Path('C:/Users/volpe/AppData/Local/Marvel/Saved/Config/Windows/GameUserSettings.ini')
SHOT = Path('C:/desk/out/range-request-efficiency-preflight.png')

def receipt(p):
    raw = p.read_bytes()
    return {'path': str(p), 'sha256': hashlib.sha256(raw).hexdigest(),
            'mtime_utc': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            'size': len(raw)}

def decoded(value):
    return json.loads(value) if isinstance(value, str) else value

user = json.loads(USER.read_text(encoding='utf-8-sig'))['RemoteUserSetting']
controls = decoded(user['UserControl'])
profiles = {}
for hero in ('0', '1036'):
    control = decoded(controls[hero])
    profiles[hero] = {k: v for k, v in control.items() if k.startswith('Gamepad')}
    profiles[hero]['AbilityUserSettingList'] = [v for v in control.get('AbilityUserSettingList', []) if v.get('bIsGamepad') is True]
    mappings = control.get('CharControlInputMappings', [])
    profiles[hero]['declared_gamepad_mapping_keys'] = sorted({str(v.get('Key', '')) for v in mappings if isinstance(v, dict) and 'Gamepad' in str(v.get('Key', ''))})
version = json.loads(VER.read_text(encoding='utf-8-sig'))
ini = configparser.ConfigParser(strict=False)
ini.read(DISPLAY, encoding='utf-8-sig')
display = {k: v for s in ini.sections() for k, v in ini[s].items() if k in ('busedynamicresolution', 'resolutionsizex', 'resolutionsizey', 'fullscreenmode')}
old = json.loads(OLD.read_text(encoding='utf-8-sig'))
selected = {
    'installed_client': {k: version[k] for k in ('version', 'changelist', 'BaseVersion', 'BasePakVersion')},
    'steam_build_id': re.search(r'"buildid"\s+"(\d+)"', APP.read_text()).group(1),
    'display_saved': display,
    'controller_saved_profiles': profiles,
    'enemy_color_saved_raw': decoded(user['ColorTeamEnemy']),
    'NoCDSaved_raw': decoded(user['NoCDSaved']),
}
result = {
    'status': 'preflight_saved_settings_evidence_not_runtime_binding',
    'input_domain': 'virtual_pad', 'observed_utc': datetime.now(timezone.utc).isoformat(),
    'source_receipts': [receipt(p) for p in (USER, VER, APP, DISPLAY)],
    **selected,
    'previous_receipt': receipt(OLD),
    'comparison_to_post_D_selected_values': {k: selected[k] == old[k] for k in selected},
    'game_process': {'pid': 48460, 'start_local': '2026-09-22T10:49:03-05:00', 'source': 'root Get-Process Marvel-Win64-Shipping'},
    'screen': {**receipt(SHOT), 'root_inspection': 'Fresh preflight screenshot; interpretation retained in separate root effective-setup record. This saved-value receipt does not establish range or effective settings.'},
    'limits': [
        'Persisted values and a current client lobby, not proof of all effective in-memory settings.',
        'Unspecified vertical sensitivity, deadzones and complete/default pad bindings remain unspecified.',
        'NoCDSaved is retained without encoding interpretation; current range menu must independently confirm normal cooldown setup.',
        'Client/build does not prove a server hotfix or marketing patch label.',
        'D supports historical primitive calibration; current runtime is not approved by this receipt.',
        'No human source motor settings are backdated from these runtime fields.'
    ],
}
with (OUT / 'saved-settings.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(result, stream, indent=2); stream.write('\n')
shutil.copyfile(SHOT, OUT / 'preflight-screen.png')
print(json.dumps({'receipt': receipt(OUT / 'saved-settings.json'), 'selected_equal_to_post_D': result['comparison_to_post_D_selected_values']}))
