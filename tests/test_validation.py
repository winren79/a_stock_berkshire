import pandas as pd

from validation import validate_return_series


def test_validate_return_series_marks_small_samples_insufficient():
    result = validate_return_series(pd.Series([1.0, -0.5, 2.0]), min_samples=5)

    assert result["status"] == "insufficient_sample"
    assert result["sample_size"] == 3
    assert result["bootstrap_mean_ci"] is None


def test_validate_return_series_bootstraps_mean_ci_when_sample_is_large_enough():
    result = validate_return_series(pd.Series([1, 2, 3, 4, 5, 6]), min_samples=5, iterations=100, seed=7)

    assert result["status"] == "validated_sample"
    assert result["sample_size"] == 6
    assert result["mean_return"] == 3.5
    assert len(result["bootstrap_mean_ci"]) == 2
    assert result["bootstrap_mean_ci"][0] <= result["mean_return"] <= result["bootstrap_mean_ci"][1]
