"""Market data source registry and quality checks for A-share signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


@dataclass
class DataQualityReport:
    total_rows: int
    usable_amount_rows: int
    usable_pct_rows: int
    zero_price_rows: int
    missing_code_rows: int
    is_usable: bool
    warnings: list[str]


@dataclass
class MarketDataResult:
    data: pd.DataFrame
    source: str
    display_source: str
    requested_date: str
    quality: DataQualityReport
    warnings: list[str]
    stale: bool = False


def _num(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
        if not value:
            return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def pick_market_columns(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "代码": ["代码", "股票代码"],
        "名称": ["名称", "股票简称", "简称"],
        "最新价": ["最新价", "收盘价"],
        "涨跌幅": ["涨跌幅", "涨跌幅%", "涨幅"],
        "成交额": ["成交额", "成交金额"],
        "换手率": ["换手率", "实际换手率"],
        "量比": ["量比"],
        "封板资金": ["封板资金", "封单资金"],
        "连板数": ["连板数", "连续涨停天数"],
    }
    picked: dict[str, pd.Series] = {}
    for target, candidates in aliases.items():
        for candidate in candidates:
            if candidate in df.columns:
                picked[target] = df[candidate]
                break
        if target not in picked:
            picked[target] = pd.Series([None] * len(df))
    return pd.DataFrame(picked)


def validate_market_frame(df: pd.DataFrame, min_usable_rows: int = 50) -> DataQualityReport:
    warnings: list[str] = []
    if df.empty:
        return DataQualityReport(
            total_rows=0,
            usable_amount_rows=0,
            usable_pct_rows=0,
            zero_price_rows=0,
            missing_code_rows=0,
            is_usable=False,
            warnings=["空数据表"],
        )

    picked = pick_market_columns(df)
    usable_amount_rows = int((picked["成交额"].apply(_num) > 0).sum())
    usable_pct_rows = int((picked["涨跌幅"].apply(_num) != 0).sum())
    zero_price_rows = int((picked["最新价"].apply(_num) <= 0).sum())
    missing_code_rows = int((picked["代码"].fillna("").astype(str).str.strip() == "").sum())

    if usable_amount_rows < min_usable_rows:
        warnings.append(f"可用成交额行数过少: {usable_amount_rows} < {min_usable_rows}")
    if usable_pct_rows < min_usable_rows:
        warnings.append(f"可用涨跌幅行数过少: {usable_pct_rows} < {min_usable_rows}")
    if zero_price_rows:
        warnings.append(f"最新价<=0行数: {zero_price_rows}")
    if missing_code_rows:
        warnings.append(f"缺失代码行数: {missing_code_rows}")

    is_usable = (usable_amount_rows >= min_usable_rows or usable_pct_rows >= min_usable_rows) and missing_code_rows < len(df)
    return DataQualityReport(
        total_rows=int(len(df)),
        usable_amount_rows=usable_amount_rows,
        usable_pct_rows=usable_pct_rows,
        zero_price_rows=zero_price_rows,
        missing_code_rows=missing_code_rows,
        is_usable=is_usable,
        warnings=warnings,
    )


def _latest_signal_snapshot(data_dir: Path, before_date: str) -> Path | None:
    normalized_before_date = before_date.replace("-", "")
    snapshots = []
    for path in data_dir.glob("signals_*.csv"):
        signal_date = path.stem.replace("signals_", "").replace("-", "")
        if signal_date < normalized_before_date:
            snapshots.append(path)
    return sorted(snapshots)[-1] if snapshots else None


def fetch_market_data_result(date: str | None = None, data_dir: Path | None = None) -> MarketDataResult:
    requested_date = date or datetime.now().strftime("%Y%m%d")
    data_dir = data_dir or DATA_DIR
    warnings: list[str] = []

    attempts = [
        (
            "akshare.stock_zt_pool_em",
            f"akshare.stock_zt_pool_em(date={requested_date})",
            lambda: ak.stock_zt_pool_em(date=requested_date),
        ),
        (
            "akshare.stock_zh_a_spot_em",
            "akshare.stock_zh_a_spot_em(fallback: stock_zt_pool_em empty/unavailable)",
            ak.stock_zh_a_spot_em,
        ),
        (
            "akshare.stock_zh_a_spot",
            "akshare.stock_zh_a_spot(fallback: eastmoney spot unavailable)",
            ak.stock_zh_a_spot,
        ),
    ]

    for source, display_source, loader in attempts:
        try:
            data = loader()
        except Exception as exc:
            warnings.append(f"{source}: {type(exc).__name__}: {exc}")
            continue

        quality = validate_market_frame(data)
        if quality.is_usable:
            return MarketDataResult(
                data=data,
                source=source,
                display_source=display_source,
                requested_date=requested_date,
                quality=quality,
                warnings=warnings + quality.warnings,
            )
        reason = "empty dataframe" if data.empty else "unusable zero market values"
        warnings.append(f"{source}: {reason}; {'; '.join(quality.warnings)}")

    detail = "; ".join(warnings) if warnings else "all market data sources returned empty"
    snapshot = _latest_signal_snapshot(data_dir, requested_date)
    if snapshot is not None:
        stale = pd.read_csv(snapshot, dtype={"代码": str})
        quality = validate_market_frame(stale, min_usable_rows=1)
        if quality.is_usable:
            return MarketDataResult(
                data=stale,
                source="local.stale_signal_snapshot",
                display_source=f"stale fallback: {snapshot.name}; live market data fetch failed: {detail}",
                requested_date=requested_date,
                quality=quality,
                warnings=warnings + [f"使用过期快照: {snapshot.name}"] + quality.warnings,
                stale=True,
            )

    raise RuntimeError(f"market data fetch failed: {detail}")
