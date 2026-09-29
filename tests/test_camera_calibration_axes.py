"""Regression for pitch review N1: yaw must keep RY zero on every report."""
from agent import camera_calibration as c
from test_camera_calibration_schedule import device


def test_complete_yaw_schedule_never_reports_pitch():
    target, count = device()
    now = [0.]
    pad = c.CameraPad(target, lambda: None, 100., clock=lambda: now[0])
    rows = c.schedule([-.1, -1., .45, 1.], seconds=.5)
    c.execute(pad, rows, 0., clock=lambda: now[0], sleep=lambda dt: now.__setitem__(0, now[0]+dt))
    assert {r['role'] for r in pad.reports} >= {'opener','prime','neutral','yaw-0','yaw-1','yaw-2','yaw-3','cleanup'}
    assert all(r['ry'] == 0 for r in pad.reports)
    assert all(row[1] == 0 for row in target.ry_rows)
    assert count['remove'] == 1 and not count['attached']
