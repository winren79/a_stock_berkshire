#!/usr/bin/env python3
"""Theme strength scoring based on the current A-share universe."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _num(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0


def compute_theme_strength(universe: pd.DataFrame) -> pd.DataFrame:
    if universe.empty or "题材" not in universe.columns:
        return pd.DataFrame(columns=["题材", "题材股票数", "题材平均涨幅", "题材接近涨停数", "题材成交额", "题材强度"])

    df = universe.copy()
    df = df[df["题材"].fillna("") != ""].copy()
    if df.empty:
        return pd.DataFrame(columns=["题材", "题材股票数", "题材平均涨幅", "题材接近涨停数", "题材成交额", "题材强度"])

    df["涨跌幅_num"] = df["涨跌幅"].apply(_num)
    df["成交额_num"] = df["成交额"].apply(_num)
    grouped = (
        df.groupby("题材")
        .agg(
            题材股票数=("代码", "count"),
            题材平均涨幅=("涨跌幅_num", "mean"),
            题材接近涨停数=("涨跌幅_num", lambda s: int((s >= 9.8).sum())),
            题材成交额=("成交额_num", "sum"),
        )
        .reset_index()
    )
    grouped["题材强度"] = grouped.apply(score_theme, axis=1)
    return grouped.sort_values(["题材强度", "题材成交额"], ascending=[False, False])


def score_theme(row: pd.Series) -> int:
    score = 0
    if int(row["题材股票数"]) >= 10:
        score += 2
    elif int(row["题材股票数"]) >= 5:
        score += 1

    if float(row["题材平均涨幅"]) >= 5:
        score += 2
    elif float(row["题材平均涨幅"]) >= 2:
        score += 1

    if int(row["题材接近涨停数"]) >= 3:
        score += 2
    elif int(row["题材接近涨停数"]) >= 1:
        score += 1

    if float(row["题材成交额"]) >= 50_000_000_000:
        score += 2
    elif float(row["题材成交额"]) >= 10_000_000_000:
        score += 1
    return score


def apply_theme_strength(signals: pd.DataFrame, theme_stats: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        enriched = signals.copy()
        enriched["题材强度"] = pd.Series(dtype="int64")
        return enriched
    if theme_stats.empty:
        enriched = signals.copy()
        enriched["题材强度"] = 0
        return enriched
    return signals.merge(theme_stats[["题材", "题材强度"]], on="题材", how="left").fillna({"题材强度": 0})
