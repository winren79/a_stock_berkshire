#!/usr/bin/env python3
"""Convert rule signals into executable advice plans with risk budgets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


MIN_BACKTEST_ROWS_FOR_ACTIONABLE = 20


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


def _has_label(row: pd.Series, label: str) -> bool:
    return label in str(row.get("风控标签") or "") or label in str(row.get("理由") or "")


def _grade_and_action(row: pd.Series, context: dict[str, Any]) -> tuple[str, str, str]:
    signal = str(row.get("信号") or "")
    risk = str(row.get("风控结论") or "")
    lhb = str(row.get("龙虎榜确认") or "")
    ai_review = str(row.get("AI_Berkshire_复核") or "")
    emotion = str(row.get("情绪周期") or context.get("market_emotion") or "")
    score = int(_num(row.get("分数")))
    theme_strength = int(_num(row.get("题材强度")))
    tested_rows = int(context.get("backtest_tested_rows") or 0)

    blockers: list[str] = []
    if tested_rows < MIN_BACKTEST_ROWS_FOR_ACTIONABLE:
        blockers.append("回测样本不足")
    if risk == "VETO":
        blockers.append("风控否决")
    if ai_review == "AI_VETO":
        blockers.append("AI Berkshire复核否决")
    if ai_review == "AI_WATCH":
        blockers.append("AI Berkshire复核观察")
    if risk == "WATCH":
        blockers.append("风控观察")
    if lhb == "强分歧":
        blockers.append("龙虎榜强分歧")
    if emotion == "高潮":
        blockers.append("情绪高潮不追高")
    if _has_label(row, "成交额<3亿"):
        blockers.append("流动性不足")
    if _has_label(row, "涨幅过热") and emotion in {"主升", "高潮"}:
        blockers.append("涨幅过热")

    if risk == "VETO" or lhb == "强分歧" or ai_review == "AI_VETO":
        return "D", "回避", "；".join(blockers)
    if signal == "BUY" and risk == "PASS" and ai_review == "AI_PASS" and not blockers and score >= 7 and theme_strength >= 5:
        return "A", "可执行计划", "风控通过；题材强；信号分数达标；历史样本达标"
    if signal in {"BUY", "HOLD"} and risk == "PASS":
        return "B", "等待触发", "；".join(blockers or ["风控通过但执行条件未完全满足"])
    if risk == "WATCH" or signal == "AVOID":
        return "C", "仅复盘观察", "；".join(blockers or ["信号或风控不足"])
    return "C", "仅复盘观察", "证据不足"


def _risk_budget(row: pd.Series, grade: str, context: dict[str, Any]) -> tuple[float, str]:
    emotion = str(row.get("情绪周期") or context.get("market_emotion") or "")
    risk = str(row.get("风控结论") or "")
    lhb = str(row.get("龙虎榜确认") or "")

    if grade == "A":
        budget = 1.0
    elif grade == "B":
        budget = 0.5
    elif grade == "C":
        budget = 0.0
    else:
        budget = 0.0

    if emotion == "高潮":
        budget *= 0.5
    if risk == "WATCH":
        budget = min(budget, 0.25)
    if lhb in {"强分歧", "弱分歧"}:
        budget = min(budget, 0.25)
    if _has_label(row, "成交额<3亿"):
        budget = min(budget, 0.25)

    if budget == 0:
        note = "不建议建仓"
    else:
        note = f"单票最大亏损预算不超过账户 {budget:.2f}%"
    return round(budget, 2), note


def _price_plan(row: pd.Series, grade: str) -> tuple[str, str, str, str]:
    price = _num(row.get("最新价"))
    pct = _num(row.get("涨跌幅"))
    if price <= 0:
        return "等待有效报价", "无法计算", "无法计算", "无有效价格"

    if grade == "A":
        trigger = f"放量不破 {price * 0.985:.2f} 且回到 {price:.2f} 上方"
    elif grade == "B":
        trigger = f"回踩 {price * 0.97:.2f}-{price * 0.985:.2f} 后重新转强"
    else:
        trigger = "不设置买入触发，仅复盘观察"

    stop = f"{price * 0.94:.2f}"
    target = f"{price * 1.06:.2f} / {price * 1.10:.2f}"
    invalid = f"跌破 {stop}，或次日高开冲高回落且收盘弱于开盘；当前涨跌幅 {pct:.2f}%"
    return trigger, stop, target, invalid


def build_advice(signals: pd.DataFrame, context: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "代码",
        "名称",
        "信号",
        "分数",
        "题材",
        "题材强度",
        "情绪周期",
        "最新价",
        "涨跌幅",
        "成交额",
        "龙虎榜确认",
        "资金流确认",
        "主力净流入",
        "风控结论",
        "风控标签",
        "AI_Berkshire_复核",
        "AI_Berkshire_短线",
        "AI_Berkshire_财务",
        "AI_Berkshire_生意",
        "AI_Berkshire_风险",
    ]
    if signals.empty:
        return pd.DataFrame(
            columns=columns
            + [
                "建议等级",
                "建议动作",
                "建议仓位上限_pct",
                "风险预算说明",
                "触发条件",
                "止损价",
                "目标价",
                "失效条件",
                "建议依据",
            ]
        )

    present = [column for column in columns if column in signals.columns]
    advice = signals[present].copy()
    grades = advice.apply(lambda row: _grade_and_action(row, context), axis=1, result_type="expand")
    advice["建议等级"] = grades[0]
    advice["建议动作"] = grades[1]
    advice["建议依据"] = grades[2]

    budgets = advice.apply(lambda row: _risk_budget(row, str(row["建议等级"]), context), axis=1, result_type="expand")
    advice["建议仓位上限_pct"] = budgets[0]
    advice["风险预算说明"] = budgets[1]

    plans = advice.apply(lambda row: _price_plan(row, str(row["建议等级"])), axis=1, result_type="expand")
    advice["触发条件"] = plans[0]
    advice["止损价"] = plans[1]
    advice["目标价"] = plans[2]
    advice["失效条件"] = plans[3]

    advice["_sort"] = advice["建议等级"].map({"A": 0, "B": 1, "C": 2, "D": 3}).fillna(9)
    advice = advice.sort_values(["_sort", "分数", "成交额"], ascending=[True, False, False]).drop(columns=["_sort"])
    return advice


def export_advice(signals: pd.DataFrame, output_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    advice = build_advice(signals, context)
    advice.to_csv(output_path, index=False, encoding="utf-8-sig")
    counts = advice["建议等级"].value_counts().to_dict() if not advice.empty else {}
    return {
        "advice_path": str(output_path),
        "advice_count": int(len(advice)),
        "advice_a_count": int(counts.get("A", 0)),
        "advice_b_count": int(counts.get("B", 0)),
        "advice_c_count": int(counts.get("C", 0)),
        "advice_d_count": int(counts.get("D", 0)),
    }
