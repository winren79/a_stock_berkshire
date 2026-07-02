"""Main fund-flow enrichment for A-share short-term candidates."""

from __future__ import annotations

from typing import Any

import akshare as ak
import pandas as pd

from dragon_tiger import normalize_code


def _num(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    multiplier = 1.0
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
        if value.endswith("亿"):
            multiplier = 100_000_000.0
            value = value[:-1]
        elif value.endswith("万"):
            multiplier = 10_000.0
            value = value[:-1]
        if not value:
            return 0.0
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return 0.0


def fetch_fund_flow(indicator: str = "今日") -> tuple[pd.DataFrame, str]:
    try:
        flow = ak.stock_individual_fund_flow_rank(indicator=indicator)
        source = f"akshare.stock_individual_fund_flow_rank(indicator={indicator})"
    except Exception:
        flow = ak.stock_fund_flow_individual(symbol="即时")
        source = "akshare.stock_fund_flow_individual(symbol=即时)"
    if flow.empty:
        raise RuntimeError("fund flow source returned empty dataframe")
    return flow, source


def _pick_flow_columns(flow: pd.DataFrame) -> pd.DataFrame:
    code_column = next((col for col in ["代码", "股票代码"] if col in flow.columns), None)
    name_column = next((col for col in ["名称", "股票简称"] if col in flow.columns), None)
    net_column = next(
        (
            col
            for col in [
                "主力净流入",
                "今日主力净流入-净额",
                "主力净流入-净额",
                "净额",
                "主力净额",
            ]
            if col in flow.columns
        ),
        None,
    )
    picked = pd.DataFrame()
    picked["代码"] = flow[code_column].apply(normalize_code) if code_column else ""
    picked["资金流名称"] = flow[name_column] if name_column else ""
    picked["主力净流入"] = flow[net_column].apply(_num) if net_column else 0.0
    return picked


def enrich_with_fund_flow(signals: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    enriched = signals.copy()
    if enriched.empty:
        for column in ["主力净流入", "资金流确认", "资金流分"]:
            enriched[column] = pd.Series(dtype="object")
        return enriched

    enriched["代码"] = enriched["代码"].apply(normalize_code)
    picked = _pick_flow_columns(flow)
    merged = enriched.merge(picked[["代码", "主力净流入"]], on="代码", how="left")
    merged["主力净流入"] = merged["主力净流入"].fillna(0.0)

    def verdict(value: float) -> str:
        if value >= 50_000_000:
            return "强确认"
        if value <= -50_000_000:
            return "强分歧"
        if value != 0:
            return "弱确认"
        return "未匹配"

    merged["资金流确认"] = merged["主力净流入"].apply(verdict)
    merged["资金流分"] = merged["资金流确认"].map({"强确认": 1, "弱确认": 0, "未匹配": 0, "强分歧": -1}).fillna(0).astype(int)
    if "分数" in merged.columns:
        merged["分数"] = merged["分数"].apply(_num).astype(int) + merged["资金流分"]
    if "理由" in merged.columns:
        merged["理由"] = merged.apply(
            lambda row: row["理由"]
            if row["资金流确认"] == "未匹配"
            else f"{row['理由']}；资金流:{row['资金流确认']}",
            axis=1,
        )
    return merged


def summarize_fund_flow(enriched: pd.DataFrame) -> dict[str, Any]:
    if enriched.empty or "资金流确认" not in enriched.columns:
        return {
            "fund_flow_matched_count": 0,
            "fund_flow_positive_count": 0,
            "fund_flow_negative_count": 0,
            "fund_flow_net_total": 0.0,
        }
    return {
        "fund_flow_matched_count": int((enriched["资金流确认"] != "未匹配").sum()),
        "fund_flow_positive_count": int((enriched["资金流确认"] == "强确认").sum()),
        "fund_flow_negative_count": int((enriched["资金流确认"] == "强分歧").sum()),
        "fund_flow_net_total": float(pd.to_numeric(enriched["主力净流入"], errors="coerce").fillna(0).sum()),
    }
