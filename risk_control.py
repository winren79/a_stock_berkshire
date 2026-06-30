#!/usr/bin/env python3
"""Risk filters for A-share short-term rule signals."""

from __future__ import annotations

from typing import Any

import pandas as pd

from dragon_tiger import normalize_code


def _num(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0


def risk_flags(row: pd.Series, theme_concentration: float = 0.0) -> tuple[int, list[str], str]:
    code = normalize_code(row.get("代码", ""))
    name = str(row.get("名称", ""))
    pct = _num(row.get("涨跌幅"))
    amount = _num(row.get("成交额"))
    turnover = _num(row.get("换手率"))
    lhb_verdict = str(row.get("龙虎榜确认", "未上榜"))

    risk_score = 0
    flags: list[str] = []

    if "ST" in name.upper() or "退" in name:
        risk_score -= 5
        flags.append("ST/退市风险")

    if code.startswith(("83", "87", "88", "92")):
        risk_score -= 3
        flags.append("北交所/流动性结构差异")

    if amount < 300_000_000:
        risk_score -= 2
        flags.append("成交额<3亿")

    if pct >= 18:
        risk_score -= 1
        flags.append("涨幅过热")

    if turnover >= 35:
        risk_score -= 2
        flags.append("换手过热")
    elif turnover >= 25:
        risk_score -= 1
        flags.append("换手偏热")

    if lhb_verdict == "强分歧":
        risk_score -= 3
        flags.append("龙虎榜强分歧")
    elif lhb_verdict == "弱分歧":
        risk_score -= 1
        flags.append("龙虎榜弱分歧")

    if theme_concentration >= 0.35:
        risk_score -= 1
        flags.append("单一题材过度集中")

    if risk_score <= -5:
        verdict = "VETO"
    elif risk_score <= -2:
        verdict = "WATCH"
    else:
        verdict = "PASS"
    return risk_score, flags, verdict


def apply_risk_controls(signals: pd.DataFrame) -> pd.DataFrame:
    enriched = signals.copy()
    if enriched.empty:
        enriched["风控分"] = pd.Series(dtype="int64")
        enriched["风控标签"] = pd.Series(dtype="str")
        enriched["风控结论"] = pd.Series(dtype="str")
        return enriched

    theme_counts = enriched["题材"].fillna("").value_counts(normalize=True) if "题材" in enriched else pd.Series(dtype=float)

    risk_rows = []
    for _, row in enriched.iterrows():
        theme = str(row.get("题材", ""))
        concentration = float(theme_counts.get(theme, 0.0)) if theme else 0.0
        score, flags, verdict = risk_flags(row, concentration)
        risk_rows.append((score, "；".join(flags), verdict))

    enriched["风控分"] = [item[0] for item in risk_rows]
    enriched["风控标签"] = [item[1] for item in risk_rows]
    enriched["风控结论"] = [item[2] for item in risk_rows]
    enriched["分数"] = enriched["分数"] + enriched["风控分"]

    def downgrade(row: pd.Series) -> str:
        if row["风控结论"] == "VETO":
            return "AVOID"
        if row["风控结论"] == "WATCH" and row.get("信号") == "BUY":
            return "HOLD"
        if row["分数"] < 4:
            return "AVOID"
        return str(row.get("信号", "HOLD"))

    enriched["信号"] = enriched.apply(downgrade, axis=1)
    enriched["理由"] = enriched.apply(
        lambda row: row["理由"] if not row["风控标签"] else f"{row['理由']}；风控:{row['风控标签']}",
        axis=1,
    )
    return enriched
