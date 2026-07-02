#!/usr/bin/env python3
"""Persist close recommendations and review them after the next trading day."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backtest import returns_for_symbol
from dragon_tiger import normalize_code


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"


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


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _latest_file(prefix: str, before_date: str | None = None) -> Path | None:
    files = []
    for path in DATA_DIR.glob(f"{prefix}_*.csv"):
        date_text = path.stem.replace(f"{prefix}_", "")
        if before_date is None or date_text < before_date:
            files.append(path)
    return sorted(files)[-1] if files else None


def _evidence(row: pd.Series) -> str:
    parts = []
    for column in ["建议依据", "龙虎榜确认", "资金流确认", "风控结论", "AI_Berkshire_复核"]:
        value = str(row.get(column) or "")
        if value and value.lower() != "nan":
            parts.append(f"{column}:{value}")
    return "；".join(parts)


def select_close_recommendations(advice: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    if advice.empty:
        return pd.DataFrame()
    candidates = advice.copy()
    for column in ["代码", "建议等级", "风控结论", "AI_Berkshire_复核", "资金流确认", "龙虎榜确认"]:
        if column not in candidates.columns:
            candidates[column] = ""

    candidates["代码"] = candidates["代码"].apply(normalize_code)
    allowed = (
        candidates["建议等级"].isin(["A", "B"])
        & (candidates["风控结论"] != "VETO")
        & (candidates["AI_Berkshire_复核"] != "AI_VETO")
        & (candidates["资金流确认"] != "强分歧")
    )
    candidates = candidates[allowed].copy()
    if candidates.empty:
        return candidates

    grade_rank = candidates["建议等级"].map({"A": 0, "B": 1}).fillna(9)
    lhb_rank = candidates["龙虎榜确认"].map({"强确认": 0, "弱确认": 1, "未上榜": 2, "弱分歧": 3, "强分歧": 9}).fillna(5)
    flow_rank = candidates["资金流确认"].map({"强确认": 0, "弱确认": 1, "未匹配": 2, "强分歧": 9}).fillna(5)
    candidates["_grade_rank"] = grade_rank
    candidates["_lhb_rank"] = lhb_rank
    candidates["_flow_rank"] = flow_rank
    candidates["_score"] = candidates["分数"].apply(_num) if "分数" in candidates.columns else 0
    candidates["_amount"] = candidates["成交额"].apply(_num) if "成交额" in candidates.columns else 0
    candidates = candidates.sort_values(
        ["_grade_rank", "_flow_rank", "_lhb_rank", "_score", "_amount"],
        ascending=[True, True, True, False, False],
    ).head(limit)
    candidates = candidates.drop(columns=["_grade_rank", "_lhb_rank", "_flow_rank", "_score", "_amount"])
    candidates.insert(0, "推荐排名", range(1, len(candidates) + 1))
    candidates["推荐证据"] = candidates.apply(_evidence, axis=1)
    return candidates


def export_close_recommendations(date: str | None = None, limit: int = 5) -> dict[str, Any]:
    date = date or _today()
    advice_path = DATA_DIR / f"advice_{date}.csv"
    if not advice_path.exists():
        raise FileNotFoundError(f"advice file not found: {advice_path}")
    advice = pd.read_csv(advice_path, dtype={"代码": str})
    selected = select_close_recommendations(advice, limit=limit)
    if not selected.empty:
        selected.insert(0, "推荐日期", date)

    csv_path = DATA_DIR / f"recommendations_{date}.csv"
    md_path = LOG_DIR / f"recommendations_{date}.md"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    selected.to_csv(csv_path, index=False, encoding="utf-8-sig")

    lines = [f"# 收盘候选推荐 - {date}", ""]
    if selected.empty:
        lines.append("今日无满足 A/B、非 VETO、非资金流强分歧条件的候选。")
    else:
        columns = [column for column in ["推荐排名", "代码", "名称", "信号", "建议等级", "AI_Berkshire_复核", "题材", "题材强度", "龙虎榜确认", "资金流确认", "触发条件", "止损价", "失效条件", "推荐证据"] if column in selected.columns]
        lines.append(selected[columns].to_markdown(index=False))
    lines.extend(["", "> 仅用于研究和次日复盘，不构成个性化投资建议。"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"date": date, "recommendation_count": int(len(selected)), "recommendations_path": str(csv_path), "recommendations_md_path": str(md_path)}


def build_recommendation_review(recommendations: pd.DataFrame, returns: dict[str, dict[str, float | None]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for _, row in recommendations.iterrows():
        code = normalize_code(row.get("代码", ""))
        one_day = returns.get(code, {}).get("1d")
        if one_day is None:
            conclusion = "待验证"
        elif one_day > 0:
            conclusion = "有价值"
        else:
            conclusion = "未验证"
        item = row.to_dict()
        item["代码"] = code
        item["1d收益率"] = one_day
        item["复盘结论"] = conclusion
        rows.append(item)

    reviewed = pd.DataFrame(rows)
    series = pd.to_numeric(reviewed["1d收益率"], errors="coerce").dropna() if not reviewed.empty else pd.Series(dtype=float)
    summary = {
        "reviewed_count": int(len(reviewed)),
        "valuable_count": int((reviewed["复盘结论"] == "有价值").sum()) if not reviewed.empty else 0,
        "pending_count": int((reviewed["复盘结论"] == "待验证").sum()) if not reviewed.empty else 0,
        "win_rate_1d": float((series > 0).mean() * 100.0) if not series.empty else None,
        "avg_return_1d": float(series.mean()) if not series.empty else None,
    }
    return reviewed, summary


def review_latest_recommendations(today: str | None = None) -> dict[str, Any]:
    today = today or _today()
    recommendation_path = _latest_file("recommendations", before_date=today)
    if recommendation_path is None:
        raise FileNotFoundError("no previous recommendations file found")
    recommendations = pd.read_csv(recommendation_path, dtype={"代码": str})
    if recommendations.empty:
        reviewed, summary = build_recommendation_review(recommendations, {})
    else:
        recommendation_date = str(recommendations["推荐日期"].iloc[0])
        returns = {}
        for code in recommendations["代码"].apply(normalize_code):
            try:
                returns[code] = returns_for_symbol(code, recommendation_date, [1])
            except Exception:
                returns[code] = {"1d": None}
        reviewed, summary = build_recommendation_review(recommendations, returns)

    review_date = today
    csv_path = DATA_DIR / f"recommendation_review_{review_date}.csv"
    md_path = LOG_DIR / f"recommendation_review_{review_date}.md"
    reviewed.to_csv(csv_path, index=False, encoding="utf-8-sig")
    lines = [
        f"# 收盘候选次日复盘 - {review_date}",
        "",
        f"- 推荐文件：{recommendation_path}",
        f"- 复盘数量：{summary['reviewed_count']}",
        f"- 有价值数量：{summary['valuable_count']}",
        f"- 1日胜率：{summary['win_rate_1d'] if summary['win_rate_1d'] is not None else 'NA'}",
        f"- 1日平均收益：{summary['avg_return_1d'] if summary['avg_return_1d'] is not None else 'NA'}",
        "",
    ]
    if reviewed.empty:
        lines.append("上一份推荐文件为空，无标的可复盘。")
    else:
        columns = [column for column in ["推荐日期", "推荐排名", "代码", "名称", "建议等级", "1d收益率", "复盘结论", "推荐证据"] if column in reviewed.columns]
        lines.append(reviewed[columns].to_markdown(index=False))
    lines.extend(["", "> 复盘只验证推荐是否具备次日研究价值，不代表未来收益可持续。"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary.update({"recommendation_path": str(recommendation_path), "review_path": str(csv_path), "review_md_path": str(md_path)})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Export and review close recommendations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--date")
    export_parser.add_argument("--limit", type=int, default=5)
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--today")
    args = parser.parse_args()

    if args.command == "export":
        result = export_close_recommendations(date=args.date, limit=args.limit)
    else:
        result = review_latest_recommendations(today=args.today)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
