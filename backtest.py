#!/usr/bin/env python3
"""Backtest existing signal files against future daily closes."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import akshare as ak
import pandas as pd

from dragon_tiger import normalize_code


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"


@dataclass
class BacktestSummary:
    signal_date: str
    horizons: list[int]
    input_rows: int
    tested_rows: int
    skipped_rows: int
    win_rate_by_horizon: dict[str, float | None]
    avg_return_by_horizon: dict[str, float | None]
    median_return_by_horizon: dict[str, float | None]
    max_loss_by_horizon: dict[str, float | None]
    grouped_output_path: str
    output_path: str


def parse_signal_date(path: Path) -> str:
    stem = path.stem
    date_text = stem.replace("signals_", "")
    datetime.strptime(date_text, "%Y-%m-%d")
    return date_text


def fetch_history(symbol: str, signal_date: str, max_horizon: int) -> pd.DataFrame:
    start = signal_date.replace("-", "")
    end_date = datetime.strptime(signal_date, "%Y-%m-%d") + timedelta(days=max_horizon * 3 + 10)
    end = end_date.strftime("%Y%m%d")
    return ak.stock_zh_a_hist(symbol=normalize_code(symbol), period="daily", start_date=start, end_date=end, adjust="")


def returns_for_symbol(symbol: str, signal_date: str, horizons: Iterable[int]) -> dict[str, float | None]:
    hist = fetch_history(symbol, signal_date, max(horizons))
    if hist.empty or "收盘" not in hist.columns:
        return {f"{h}d": None for h in horizons}

    hist = hist.sort_values("日期").reset_index(drop=True)
    if len(hist) < 2:
        return {f"{h}d": None for h in horizons}

    entry = float(hist.loc[0, "收盘"])
    result: dict[str, float | None] = {}
    for horizon in horizons:
        key = f"{horizon}d"
        if len(hist) <= horizon or entry == 0:
            result[key] = None
            continue
        exit_price = float(hist.loc[horizon, "收盘"])
        result[key] = (exit_price / entry - 1.0) * 100.0
    return result


def backtest_signal_file(
    signal_file: Path,
    horizons: list[int] | None = None,
    max_symbols: int = 30,
) -> tuple[pd.DataFrame, BacktestSummary]:
    horizons = horizons or [1, 3, 5]
    signal_date = parse_signal_date(signal_file)
    signals = pd.read_csv(signal_file, dtype={"代码": str})
    if "信号" in signals.columns:
        candidates = signals[signals["信号"].isin(["BUY", "HOLD"])].copy()
    else:
        candidates = signals.copy()
    candidates = candidates.head(max_symbols)

    rows = []
    skipped = 0
    for _, row in candidates.iterrows():
        code = normalize_code(row.get("代码", ""))
        try:
            returns = returns_for_symbol(code, signal_date, horizons)
        except Exception:
            skipped += 1
            continue
        if all(value is None for value in returns.values()):
            skipped += 1
            continue
        result = {
            "信号日期": signal_date,
            "代码": code,
            "名称": row.get("名称", ""),
            "原信号": row.get("信号", ""),
            "原分数": row.get("分数", ""),
            "情绪周期": row.get("情绪周期", ""),
            "龙虎榜确认": row.get("龙虎榜确认", ""),
            "题材": row.get("题材", ""),
            "风控结论": row.get("风控结论", ""),
        }
        result.update(returns)
        rows.append(result)

    result_df = pd.DataFrame(rows)
    output_path = DATA_DIR / f"backtest_{signal_date}.csv"
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    win_rate: dict[str, float | None] = {}
    avg_return: dict[str, float | None] = {}
    median_return: dict[str, float | None] = {}
    max_loss: dict[str, float | None] = {}
    for horizon in horizons:
        key = f"{horizon}d"
        series = pd.to_numeric(result_df[key], errors="coerce").dropna() if key in result_df else pd.Series(dtype=float)
        if series.empty:
            win_rate[key] = None
            avg_return[key] = None
            median_return[key] = None
            max_loss[key] = None
        else:
            win_rate[key] = float((series > 0).mean() * 100.0)
            avg_return[key] = float(series.mean())
            median_return[key] = float(series.median())
            max_loss[key] = float(series.min())

    grouped_output_path = DATA_DIR / f"backtest_groups_{signal_date}.csv"
    group_df = grouped_backtest_stats(result_df, horizons)
    group_df.to_csv(grouped_output_path, index=False, encoding="utf-8-sig")

    summary = BacktestSummary(
        signal_date=signal_date,
        horizons=horizons,
        input_rows=int(len(signals)),
        tested_rows=int(len(result_df)),
        skipped_rows=int(skipped + max(0, len(candidates) - len(result_df) - skipped)),
        win_rate_by_horizon=win_rate,
        avg_return_by_horizon=avg_return,
        median_return_by_horizon=median_return,
        max_loss_by_horizon=max_loss,
        grouped_output_path=str(grouped_output_path),
        output_path=str(output_path),
    )
    return result_df, summary


def grouped_backtest_stats(result_df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    if result_df.empty:
        return pd.DataFrame(
            columns=["分组字段", "分组值", "样本数", "周期", "胜率", "平均收益", "中位收益", "最大亏损"]
        )

    rows = []
    group_fields = ["原信号", "情绪周期", "龙虎榜确认", "题材", "风控结论"]
    for field in group_fields:
        if field not in result_df.columns:
            continue
        for value, group in result_df.groupby(field, dropna=False):
            label = str(value) if str(value) else "未标注"
            for horizon in horizons:
                key = f"{horizon}d"
                if key not in group.columns:
                    continue
                series = pd.to_numeric(group[key], errors="coerce").dropna()
                if series.empty:
                    continue
                rows.append(
                    {
                        "分组字段": field,
                        "分组值": label,
                        "样本数": int(len(series)),
                        "周期": key,
                        "胜率": float((series > 0).mean() * 100.0),
                        "平均收益": float(series.mean()),
                        "中位收益": float(series.median()),
                        "最大亏损": float(series.min()),
                    }
                )
    return pd.DataFrame(rows)


def latest_signal_file() -> Path | None:
    files = sorted(DATA_DIR.glob("signals_*.csv"))
    return files[-1] if files else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest saved A-share signal files.")
    parser.add_argument("--file", help="Signal CSV path. Defaults to latest data/signals_*.csv.")
    parser.add_argument("--max-symbols", type=int, default=30)
    args = parser.parse_args()

    signal_file = Path(args.file) if args.file else latest_signal_file()
    if signal_file is None:
        print("No signal file found.")
        return 1

    _, summary = backtest_signal_file(signal_file, max_symbols=args.max_symbols)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
