"""Read only named persisted settings; write a scoped receipt, never a binding.

    uv run --offline --no-project --python 3.11 python -B collect_settings.py --pid <game pid> --screen <fresh native png> [--out DIR]
    uv run --offline --no-project --python 3.11 python -B collect_settings.py --dry-run --out <scratch dir>

Adapted from the slot-4 collector (data/runtime/galacta-pilot-20260922-04-preflight/collect_settings.py): the PID and the
screenshot are arguments, the process is re-read here, and the comparison is to the slot-4 receipt. A dry run reads the
same files but records no process or screen, and issue_binding.py refuses it outside a scratch directory.
"""
import argparse
import configparser
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
USER = Path('C:/Users/volpe/AppData/Local/Marvel/Saved/Saved/Config/1295996384/MarvelUserSetting.json')
VER = Path('C:/Program Files (x86)/Steam/steamapps/common/MarvelRivals/MarvelGame/version.json')
APP = Path('C:/Program Files (x86)/Steam/steamapps/appmanifest_2767030.acf')
DISPLAY = Path('C:/Users/volpe/AppData/Local/Marvel/Saved/Config/Windows/GameUserSettings.ini')
MUST_EQUAL = ('installed_client', 'steam_build_id', 'display_saved', 'controller_saved_profiles', 'enemy_color_saved_raw')


def receipt(p):
    raw = p.read_bytes()
    return {'path': str(p), 'sha256': hashlib.sha256(raw).hexdigest(),
            'mtime_utc': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(), 'size': len(raw)}


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def game_process(pid):
    ps = f"Get-Process -Id {int(pid)} -ErrorAction Stop | Select-Object Id, ProcessName, @{{n='start';e={{$_.StartTime.ToString('o')}}}} | ConvertTo-Json"
    found = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True))
    if found['ProcessName'] != 'Marvel-Win64-Shipping':
        raise SystemExit(f"REFUSED: PID {pid} is {found['ProcessName']}, not the game")
    return {'pid': found['Id'], 'start_local': found['start'], 'source': 'collect_settings.py Get-Process at collection'}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--pid', type=int)
    ap.add_argument('--screen', type=Path, help='fresh native screenshot of the range, taken by the operator')
    ap.add_argument('--out', type=Path, default=HERE)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if not a.dry_run and (a.pid is None or a.screen is None):
        ap.error('--pid and --screen are required outside --dry-run')
    cand = json.loads((HERE / 'candidate.json').read_text(encoding='utf-8'))
    old_path = ROOT / cand['previous_saved_settings']
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
    old = json.loads(old_path.read_text(encoding='utf-8-sig'))
    selected = {
        'installed_client': {k: version[k] for k in ('version', 'changelist', 'BaseVersion', 'BasePakVersion')},
        'steam_build_id': re.search(r'"buildid"\s+"(\d+)"', APP.read_text()).group(1),
        'display_saved': display,
        'controller_saved_profiles': profiles,
        'enemy_color_saved_raw': decoded(user['ColorTeamEnemy']),
        'NoCDSaved_raw': decoded(user['NoCDSaved']),
    }
    patch = f"{selected['installed_client']['version']}/build{selected['steam_build_id']}"
    swing_hold = [v['Value'] for v in profiles['1036']['AbilityUserSettingList'] if v['Key'] == 'bIsHoldAbility' and v['AbilityID'] == 103641]
    result = {
        'status': 'preflight_saved_settings_evidence_not_runtime_binding',
        'dry_run': a.dry_run,
        'input_domain': 'virtual_pad', 'observed_utc': datetime.now(timezone.utc).isoformat(),
        'source_receipts': [receipt(p) for p in (USER, VER, APP, DISPLAY)],
        **selected,
        'patch': patch, 'patch_equals_source_identity': patch == cand['source_identity']['patch'],
        'swing_hold_saved': swing_hold == [True],
        'previous_receipt': receipt(old_path),
        'comparison_to_slot04_receipt': {k: selected[k] == old[k] for k in selected},
        'game_process': None if a.dry_run else game_process(a.pid),
        'screen': None if a.dry_run else {**receipt(a.screen), 'root_inspection': 'Fresh preflight screenshot; interpretation is in effective-setup.json. This saved-value receipt does not establish range or effective settings.'},
        'limits': [
            'Persisted values and a current range scene, not proof of all effective in-memory settings.',
            'Unspecified vertical sensitivity, deadzones and complete/default pad bindings remain unspecified.',
            'NoCDSaved is retained without encoding interpretation; the range menu must independently confirm normal cooldowns.',
            'Client/build does not prove a server hotfix or marketing patch label.',
            'Bot health and bot movement are not exposed by Practice Settings: unknown.',
            'No human source motor settings are backdated from these runtime fields.',
        ],
    }
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / 'saved-settings.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    if not a.dry_run:
        shutil.copyfile(a.screen, a.out / 'preflight-screen.png')
    bad = [k for k in MUST_EQUAL if not result['comparison_to_slot04_receipt'][k]]
    print(json.dumps({'receipt': receipt(a.out / 'saved-settings.json'), 'patch': patch,
                      'patch_equals_source_identity': result['patch_equals_source_identity'],
                      'swing_hold_saved': result['swing_hold_saved'], 'differs_from_slot04': bad}))
    if bad or not result['patch_equals_source_identity'] or not result['swing_hold_saved']:
        raise SystemExit('REFUSED: saved settings differ from the slot-4 receipt or the source patch; the lead decides')


if __name__ == '__main__':
    main()
