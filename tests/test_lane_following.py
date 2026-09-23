from smartcar.lane_following import steering_from_model_output


def test_center_output_stays_neutral():
    assert steering_from_model_output(0.5) == 1500


def test_right_calibration_branch():
    assert steering_from_model_output(0.6) == 2052


def test_left_calibration_branch():
    assert steering_from_model_output(0.0) == 782
