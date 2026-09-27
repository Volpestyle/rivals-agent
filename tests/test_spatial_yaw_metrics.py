import pytest

from policy.range_bc.spatial_yaw_metrics import retention, yaw_slices


def item(yaw, predicted, pitch=0, known=True):
    return ({"valid": True, "target": {"camera_known": known, "yaw": yaw, "pitch": pitch}},
            {"yaw": predicted, "pitch": pitch, "held": [0], "press": [0], "release": [0]})


def test_left_right_zero_and_unknown_are_separate():
    runs = [[item(-2, -1), item(2, -1), item(0, .6), item(0, -.05, pitch=None), item(0, 9, known=False)]]
    report = yaw_slices(runs)
    assert report["all"]["n"] == 4
    assert report["left"]["mae_deg"] == 1 and report["left"]["zero_motion_mae_deg"] == 2
    assert report["left"]["sign_accuracy"] == 1
    assert report["right"]["mae_deg"] == 3 and report["right"]["opposite_turn_rate"] == 1
    assert report["human_yaw_zero"]["false_turn_ge_point6_rate"] == .5
    assert report["human_yaw_zero"]["false_left_rate"] == .5
    assert report["both_axes_zero"]["n"] == 1
    assert report["both_axes_zero"]["false_turn_ge_point6_rate"] == 1


def test_empty_subsets_are_unknown_not_zero_and_missing_prediction_refused():
    assert yaw_slices([[item(1, 0)]])["left"]["mae_deg"] is None
    assert yaw_slices([[item(1, 0)]])["right"]["missed_turn_rate"] == 1
    with pytest.raises(ValueError, match="missing"):
        yaw_slices([[item(1, None)]])


def test_retention_allows_only_yaw_to_change_and_requires_same_rows():
    base, candidate = [[item(-2, -1)]], [[item(-2, -2)]]
    assert retention(base, candidate)["exact_action_and_pitch_predictions"]
    candidate[0][0][1]["press"] = [1]
    with pytest.raises(ValueError, match="frozen"):
        retention(base, candidate)
    with pytest.raises(ValueError, match="rows differ"):
        retention(base, [[item(-1, -1)]])
