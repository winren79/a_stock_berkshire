#!/usr/bin/env python3
"""Rule-based AI Berkshire multi-role review for short-term candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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


def _txt(value: Any) -> str:
    return "" if value is None or pd.isna(value) else str(value)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _signal_agent(row: pd.Series) -> tuple[str, str]:
    grade = _txt(row.get("建议等级"))
    signal = _txt(row.get("信号"))
    score = _num(row.get("分数"))
    theme_strength = _num(row.get("题材强度"))
    lhb = _txt(row.get("龙虎榜确认"))
    if grade == "A" or (signal == "BUY" and score >= 7):
        return "PASS", "短线信号达到可执行强度"
    if grade == "B" and score >= 6 and lhb != "强分歧":
        if theme_strength >= 5:
            return "PASS", "短线强度高且题材强"
        return "WATCH", "短线强度尚可但题材确认不足"
    if grade == "D" or lhb == "强分歧":
        return "VETO", "短线层存在强分歧或回避信号"
    return "WATCH", "短线层只适合观察"


def _financial_agent(row: pd.Series, context: dict[str, Any]) -> tuple[str, str]:
    amount = _num(row.get("成交额"))
    tested_rows = int(context.get("backtest_tested_rows") or 0)
    finance_data_available = bool(context.get("finance_data_available", False))
    if not finance_data_available:
        if amount >= 300_000_000 and tested_rows >= 20:
            return "WATCH", "缺少ROE/FCF/估值双源数据，只能以流动性和回测样本作弱验证"
        return "VETO", "缺少财务双源数据且流动性或样本不足"
    return "PASS", "财务数据已通过双源校验"


def _business_agent(row: pd.Series) -> tuple[str, str]:
    theme = _txt(row.get("题材"))
    name = _txt(row.get("名称"))
    labels = _txt(row.get("风控标签")) + _txt(row.get("建议依据"))
    if _contains_any(labels, ["涨幅过热", "成交额<3亿"]):
        return "WATCH", "短线过热或流动性瑕疵，不能外推为好生意"
    if theme in {"半导体", "AI", "机器人", "华为链", "低空经济"}:
        return "WATCH", f"{theme}题材清晰，但需财务和护城河数据确认"
    if name in {"多氟多", "中矿资源", "东方锆业"}:
        return "WATCH", "偏周期或资源属性，需验证周期位置和成本优势"
    return "WATCH", "商业模式未完成AI Berkshire六关验证"


def _risk_agent(row: pd.Series, context: dict[str, Any]) -> tuple[str, str]:
    emotion = _txt(row.get("情绪周期")) or _txt(context.get("market_emotion"))
    lhb = _txt(row.get("龙虎榜确认"))
    risk = _txt(row.get("风控结论"))
    labels = _txt(row.get("风控标签")) + _txt(row.get("建议依据"))
    pct = _num(row.get("涨跌幅"))
    if risk == "VETO" or lhb == "强分歧":
        return "VETO", "风控否决或龙虎榜强分歧"
    if emotion == "高潮" and pct >= 9.8:
        return "WATCH", "高潮期接近涨停，不允许追高"
    if _contains_any(labels, ["涨幅过热", "换手过热", "龙虎榜强分歧"]):
        return "WATCH", "风险标签提示过热或分歧"
    if risk == "WATCH":
        return "WATCH", "基础风控为观察"
    return "PASS", "未触发硬性风险"


def _final_verdict(role_results: list[tuple[str, str]]) -> str:
    labels = [label for label, _ in role_results]
    if "VETO" in labels:
        return "AI_VETO"
    if all(label == "PASS" for label in labels):
        return "AI_PASS"
    return "AI_WATCH"


def review_candidates(candidates: pd.DataFrame, context: dict[str, Any]) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(
            columns=list(candidates.columns)
            + [
                "AI_Berkshire_复核",
                "AI_Berkshire_短线",
                "AI_Berkshire_财务",
                "AI_Berkshire_生意",
                "AI_Berkshire_风险",
                "AI_Berkshire_结论",
            ]
        )

    reviewed = candidates.copy()
    verdicts = []
    signal_notes = []
    financial_notes = []
    business_notes = []
    risk_notes = []
    conclusions = []

    for _, row in reviewed.iterrows():
        signal = _signal_agent(row)
        financial = _financial_agent(row, context)
        business = _business_agent(row)
        risk = _risk_agent(row, context)
        roles = [signal, financial, business, risk]
        verdict = _final_verdict(roles)

        verdicts.append(verdict)
        signal_notes.append(f"{signal[0]}: {signal[1]}")
        financial_notes.append(f"{financial[0]}: {financial[1]}")
        business_notes.append(f"{business[0]}: {business[1]}")
        risk_notes.append(f"{risk[0]}: {risk[1]}")
        conclusions.append("；".join(note for _, note in roles))

    reviewed["AI_Berkshire_复核"] = verdicts
    reviewed["AI_Berkshire_短线"] = signal_notes
    reviewed["AI_Berkshire_财务"] = financial_notes
    reviewed["AI_Berkshire_生意"] = business_notes
    reviewed["AI_Berkshire_风险"] = risk_notes
    reviewed["AI_Berkshire_结论"] = conclusions
    return reviewed


def export_ai_berkshire_review(candidates: pd.DataFrame, output_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    reviewed = review_candidates(candidates, context)
    reviewed.to_csv(output_path, index=False, encoding="utf-8-sig")
    counts = reviewed["AI_Berkshire_复核"].value_counts().to_dict() if not reviewed.empty else {}
    return {
        "ai_review_path": str(output_path),
        "ai_review_count": int(len(reviewed)),
        "ai_pass_count": int(counts.get("AI_PASS", 0)),
        "ai_watch_count": int(counts.get("AI_WATCH", 0)),
        "ai_veto_count": int(counts.get("AI_VETO", 0)),
    }
