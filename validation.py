"""Statistical validation helpers for backtest return samples."""

from __future__ import annotations

from typing import Any

import pandas as pd


def validate_return_series(
    returns: pd.Series,
    min_samples: int = 20,
    iterations: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    series = pd.to_numeric(returns, errors="coerce").dropna()
    sample_size = int(len(series))
    if sample_size == 0:
        return {
            "status": "no_sample",
            "sample_size": 0,
            "win_rate": None,
            "mean_return": None,
            "bootstrap_mean_ci": None,
        }

    mean_return = float(series.mean())
    win_rate = float((series > 0).mean() * 100.0)
    if sample_size < min_samples:
        return {
            "status": "insufficient_sample",
            "sample_size": sample_size,
            "win_rate": win_rate,
            "mean_return": mean_return,
            "bootstrap_mean_ci": None,
        }

    means = []
    for index in range(iterations):
        sample = series.sample(n=sample_size, replace=True, random_state=seed + index)
        means.append(float(sample.mean()))
    ci = pd.Series(means).quantile([0.025, 0.975]).tolist()
    return {
        "status": "validated_sample",
        "sample_size": sample_size,
        "win_rate": win_rate,
        "mean_return": mean_return,
        "bootstrap_mean_ci": [float(ci[0]), float(ci[1])],
    }


def validate_backtest_frame(result_df: pd.DataFrame, horizons: list[int], min_samples: int = 20) -> dict[str, Any]:
    return {
        f"{horizon}d": validate_return_series(
            result_df[f"{horizon}d"] if f"{horizon}d" in result_df.columns else pd.Series(dtype=float),
            min_samples=min_samples,
        )
        for horizon in horizons
    }
