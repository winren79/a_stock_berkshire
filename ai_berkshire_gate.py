#!/usr/bin/env python3
"""Prepare candidates for AI Berkshire second-pass risk review."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_ai_berkshire_candidates(signals: pd.DataFrame, output_path: Path, limit: int = 20) -> dict[str, object]:
    columns = [
        "代码",
        "名称",
        "信号",
        "分数",
        "题材",
        "题材强度",
        "涨跌幅",
        "成交额",
        "换手率",
        "龙虎榜确认",
        "龙虎榜净买额",
        "风控结论",
        "风控标签",
        "理由",
    ]
    present = [column for column in columns if column in signals.columns]
    candidates = signals[present].head(limit).copy() if not signals.empty else pd.DataFrame(columns=columns)
    candidates["AI_Berkshire_状态"] = "待评估"
    candidates["AI_Berkshire_建议"] = ""
    candidates["AI_Berkshire_理由"] = ""
    candidates.to_csv(output_path, index=False, encoding="utf-8-sig")
    return {
        "ai_candidates_path": str(output_path),
        "ai_candidates_count": int(len(candidates)),
        "ai_berkshire_status": "pending_manual_or_codex_skill_review",
    }
