"""Offline native-count measurement: no media, capture, pad or corpus access."""
import copy
import json

import pytest

pytest.importorskip('numpy')
pytest.importorskip('cv2')
from scripts.analyze_camera_schedule import file_sha256, grade, load_native_counts, native_count_rate


def annotation(direction=1):
    return {'role': 'yaw-0', 'direction': direction, 'complete_turns_verified': True,
            'stationary_position_verified': True, 'landmark': 'Inspected unique arch and full scene sequence',
            'crossings': [{'turn_index': i, 'time_bounds_s': [1+i*2.34, 1.1+i*2.34],
                           'frames': [{'path': f'{i}-{side}.png', 'sha256': 'a'*64} for side in (0, 1)]}
                          for i in range(8)]}


@pytest.mark.parametrize('direction', [1, -1])
def test_count_average_and_conservative_endpoint_bounds(direction):
    result = native_count_rate(annotation(direction), 0, 20, direction*.45)
    assert result['full_turns'] == 7
    assert result['candidate_signed_deg_s'] == pytest.approx(direction*360/2.34)
    low, high = result['candidate_signed_deg_s_bounds']
    assert low < direction*360/2.34 < high
    assert not low <= direction*180/2.34 <= high
    assert result['elapsed_bounds_s'] == pytest.approx([7*2.34-.1, 7*2.34+.1])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('fault', ['unverified', 'moving', 'direction', 'missing_turn', 'overlap',
                                  'out_of_segment', 'inconsistent', 'nan', 'no_pins', 'few_returns'])
def test_bad_native_annotations_do_not_manufacture_a_rate(fault):
    row = annotation()
    if fault == 'unverified': row['complete_turns_verified'] = False
    if fault == 'moving': row['stationary_position_verified'] = False
    if fault == 'direction': row['direction'] = -1
    if fault == 'missing_turn': row['crossings'][2]['turn_index'] = 3
    if fault == 'overlap': row['crossings'][2]['time_bounds_s'] = [1, 1.1]
    if fault == 'out_of_segment': row['crossings'][0]['time_bounds_s'] = [0, .1]
    if fault == 'inconsistent': row['crossings'][3]['time_bounds_s'] = [8.8, 8.9]
    if fault == 'nan': row['crossings'][3]['time_bounds_s'][0] = float('nan')
    if fault == 'no_pins': row['crossings'][0]['frames'] = []
    if fault == 'few_returns': row['crossings'] = row['crossings'][:3]
    with pytest.raises(ValueError): native_count_rate(row, 0, 20, .45)


def test_excluded_time_cannot_be_silently_bridged():
    with pytest.raises(ValueError, match='exclusion'):
        native_count_rate(annotation(), 0, 20, .45, [{'start': 5, 'end': 6, 'reason': 'unseen'}])


def test_pitch_never_misuses_yaw_period_as_an_angular_measurement():
    result = grade([], [{'role':'pitch-0','ry':.45}], 0, [])
    assert result[0]['candidate_signed_deg_s'] is None
    assert result[0]['reason'] == 'pitch_requires_focal_and_unclamped_native_registration'


def test_source_binding_detects_changed_video_manifest_and_duplicate_roles(tmp_path):
    video = tmp_path/'synthetic-bytes.mkv'
    video.write_bytes(b'not a video; hash only')
    manifest = {'recording_ref': str(video), 'schedule': [{'role': 'yaw-0'}]}
    manifest_path = tmp_path/'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    row = {'format': 'camera-native-turn-count-v1', 'manifest_sha256': file_sha256(manifest_path),
           'recording_ref': str(video), 'recording_sha256': file_sha256(video), 'segments': [annotation()]}
    path = tmp_path/'counts.json'
    path.write_text(json.dumps(row))
    assert load_native_counts(path, manifest_path, manifest)[0] == row
    for key in ('manifest_sha256', 'recording_sha256', 'recording_ref'):
        bad = copy.deepcopy(row); bad[key] = 'changed'
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='mismatch'): load_native_counts(path, manifest_path, manifest)
    row['segments'] *= 2
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match='duplicate'): load_native_counts(path, manifest_path, manifest)
