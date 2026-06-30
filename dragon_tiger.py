#!/usr/bin/env python3
"""Dragon Tiger list enrichment for A-share signal files."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd


def normalize_code(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)[-6:]


def today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def fetch_dragon_tiger(date: str | None = None, fallback_days: int = 7) -> tuple[pd.DataFrame, str]:
    requested_date = date or today_yyyymmdd()
    errors: list[str] = []
    start = datetime.strptime(requested_date, "%Y%m%d")

    for offset in range(fallback_days + 1):
        trade_date = (start - timedelta(days=offset)).strftime("%Y%m%d")
        source = f"akshare.stock_lhb_detail_em(start_date={trade_date}, end_date={trade_date})"
        try:
            df = ak.stock_lhb_detail_em(start_date=trade_date, end_date=trade_date)
        except Exception as exc:
            errors.append(f"{trade_date}: {type(exc).__name__}: {exc}")
            continue

        if df is not None and not df.empty and "代码" in df.columns:
            if trade_date == requested_date:
                return df, source
            return df, f"{source} (fallback from requested_date={requested_date})"
        errors.append(f"{trade_date}: empty or invalid dataframe")

    detail = "; ".join(errors)
    raise RuntimeError(f"dragon tiger fetch failed: {detail}")


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


def _empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["龙虎榜上榜"] = False
    enriched["龙虎榜净买额"] = 0.0
    enriched["龙虎榜买入额"] = 0.0
    enriched["龙虎榜卖出额"] = 0.0
    enriched["龙虎榜原因"] = ""
    enriched["龙虎榜解读"] = ""
    enriched["龙虎榜确认"] = "未上榜"
    enriched["龙虎榜分"] = 0
    return enriched


def enrich_with_dragon_tiger(signals: pd.DataFrame, lhb: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return _empty_columns(signals)
    if lhb.empty or "代码" not in lhb.columns:
        return _empty_columns(signals)

    enriched = signals.copy()
    enriched["代码"] = enriched["代码"].apply(normalize_code)
    lhb_norm = lhb.copy()
    lhb_norm["代码"] = lhb_norm["代码"].apply(normalize_code)

    columns = [
        "代码",
        "龙虎榜净买额",
        "龙虎榜买入额",
        "龙虎榜卖出额",
        "上榜原因",
        "解读",
    ]
    present = [column for column in columns if column in lhb_norm.columns]
    lhb_view = lhb_norm[present].drop_duplicates("代码", keep="first")

    merged = enriched.merge(lhb_view, on="代码", how="left")
    merged["龙虎榜上榜"] = merged["龙虎榜净买额"].notna()
    merged["龙虎榜净买额"] = merged["龙虎榜净买额"].apply(_num)
    merged["龙虎榜买入额"] = merged.get("龙虎榜买入额", pd.Series([0] * len(merged))).apply(_num)
    merged["龙虎榜卖出额"] = merged.get("龙虎榜卖出额", pd.Series([0] * len(merged))).apply(_num)
    merged["龙虎榜原因"] = merged.get("上榜原因", pd.Series([""] * len(merged))).fillna("")
    merged["龙虎榜解读"] = merged.get("解读", pd.Series([""] * len(merged))).fillna("")

    def verdict(row: pd.Series) -> str:
        if not bool(row["龙虎榜上榜"]):
            return "未上榜"
        net = _num(row["龙虎榜净买额"])
        if net >= 50_000_000:
            return "强确认"
        if net > 0:
            return "弱确认"
        if net <= -50_000_000:
            return "强分歧"
        return "弱分歧"

    def score(row: pd.Series) -> int:
        label = verdict(row)
        return {"强确认": 2, "弱确认": 1, "未上榜": 0, "弱分歧": -1, "强分歧": -2}[label]

    merged["龙虎榜确认"] = merged.apply(verdict, axis=1)
    merged["龙虎榜分"] = merged.apply(score, axis=1)
    drop_cols = [column for column in ["上榜原因", "解读"] if column in merged.columns]
    return merged.drop(columns=drop_cols)


def summarize_dragon_tiger(enriched: pd.DataFrame) -> dict[str, Any]:
    if enriched.empty or "龙虎榜上榜" not in enriched.columns:
        return {
            "lhb_listed_count": 0,
            "lhb_positive_count": 0,
            "lhb_negative_count": 0,
            "lhb_net_buy_total": 0.0,
        }

    listed = enriched[enriched["龙虎榜上榜"] == True]
    positive = listed[listed["龙虎榜净买额"] > 0]
    negative = listed[listed["龙虎榜净买额"] < 0]
    return {
        "lhb_listed_count": int(len(listed)),
        "lhb_positive_count": int(len(positive)),
        "lhb_negative_count": int(len(negative)),
        "lhb_net_buy_total": float(listed["龙虎榜净买额"].sum()) if not listed.empty else 0.0,
    }
