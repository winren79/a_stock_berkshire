#!/usr/bin/env python3
"""A-share short-term signal engine: emotion + theme + fund strength."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from advice_engine import export_advice
from ai_berkshire_gate import export_ai_berkshire_candidates
from ai_berkshire_review import export_ai_berkshire_review, review_candidates
from backtest import backtest_signal_file
from dragon_tiger import enrich_with_dragon_tiger, fetch_dragon_tiger, summarize_dragon_tiger
from risk_control import apply_risk_controls
from theme_strength import apply_theme_strength, compute_theme_strength


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"

THEMES = {
    "AI": ["AI", "人工智能", "智能", "算力", "大模型"],
    "半导体": ["半导体", "芯片", "集成", "电子", "光电", "微", "硅", "材料"],
    "机器人": ["机器人", "自动化", "智能装备"],
    "华为链": ["华为", "鸿蒙", "昇腾"],
    "低空经济": ["低空", "无人机", "航空"],
}


@dataclass
class RunSummary:
    run_at: str
    source: str
    market_emotion: str
    limit_up_like_count: int
    rows_fetched: int
    rows_selected: int
    buy_count: int
    hold_count: int
    avoid_count: int
    lhb_source: str
    lhb_listed_count: int
    lhb_positive_count: int
    lhb_negative_count: int
    lhb_net_buy_total: float
    backtest_signal_date: str
    backtest_tested_rows: int
    backtest_win_rate_1d: float | None
    backtest_avg_return_1d: float | None
    backtest_max_loss_1d: float | None
    backtest_grouped_path: str
    risk_pass_count: int
    risk_watch_count: int
    risk_veto_count: int
    top_theme: str
    top_theme_strength: int
    ai_candidates_count: int
    ai_candidates_path: str
    ai_berkshire_status: str
    advice_count: int
    advice_a_count: int
    advice_b_count: int
    advice_c_count: int
    advice_d_count: int
    advice_path: str
    ai_review_count: int
    ai_pass_count: int
    ai_watch_count: int
    ai_veto_count: int
    ai_review_path: str
    csv_path: str
    markdown_path: str
    log_path: str


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


def _pick_columns(df: pd.DataFrame) -> pd.DataFrame:
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


def _has_usable_market_values(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    picked = _pick_columns(df)
    amount_count = int((picked["成交额"].apply(_num) > 0).sum())
    pct_count = int((picked["涨跌幅"].apply(_num) != 0).sum())
    return amount_count >= 50 or pct_count >= 50


def fetch_market_data(date: str | None = None) -> tuple[pd.DataFrame, str]:
    errors: list[str] = []
    used_date = date or datetime.now().strftime("%Y%m%d")

    try:
        zt = ak.stock_zt_pool_em(date=used_date)
    except Exception as exc:
        errors.append(f"stock_zt_pool_em: {type(exc).__name__}: {exc}")
        zt = pd.DataFrame()

    if not zt.empty:
        if _has_usable_market_values(zt):
            return zt, f"akshare.stock_zt_pool_em(date={used_date})"
        errors.append("stock_zt_pool_em: unusable zero market values")

    try:
        spot = ak.stock_zh_a_spot_em()
    except Exception as exc:
        errors.append(f"stock_zh_a_spot_em: {type(exc).__name__}: {exc}")
    else:
        if _has_usable_market_values(spot):
            return spot, "akshare.stock_zh_a_spot_em(fallback: stock_zt_pool_em empty/unavailable)"
        errors.append("stock_zh_a_spot_em: empty dataframe" if spot.empty else "stock_zh_a_spot_em: unusable zero market values")

    try:
        sina_spot = ak.stock_zh_a_spot()
    except Exception as exc:
        errors.append(f"stock_zh_a_spot: {type(exc).__name__}: {exc}")
    else:
        if _has_usable_market_values(sina_spot):
            return sina_spot, "akshare.stock_zh_a_spot(fallback: eastmoney spot unavailable)"
        errors.append("stock_zh_a_spot: empty dataframe" if sina_spot.empty else "stock_zh_a_spot: unusable zero market values")

    detail = "; ".join(errors) if errors else "all market data sources returned empty"
    raise RuntimeError(f"market data fetch failed: {detail}")


def market_emotion(limit_up_like_count: int) -> str:
    if limit_up_like_count < 30:
        return "冰点"
    if limit_up_like_count < 60:
        return "启动"
    if limit_up_like_count < 90:
        return "主升"
    return "高潮"


def detect_theme(name: str) -> str:
    for theme, keywords in THEMES.items():
        if any(keyword in name for keyword in keywords):
            return theme
    return ""


def score_row(row: pd.Series, emotion: str) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []

    amount = _num(row.get("成交额"))
    pct = _num(row.get("涨跌幅"))
    turnover = _num(row.get("换手率"))
    volume_ratio = _num(row.get("量比"))
    seal_money = _num(row.get("封板资金"))
    streak = _num(row.get("连板数"))
    theme = str(row.get("题材") or "")

    if amount >= 2_000_000_000:
        score += 2
        reasons.append("成交额>=20亿")
    elif amount >= 1_000_000_000:
        score += 1
        reasons.append("成交额>=10亿")

    if pct >= 9.8:
        score += 2
        reasons.append("接近涨停")
    elif pct >= 5:
        score += 1
        reasons.append("涨幅>=5%")

    if 3 <= turnover <= 25:
        score += 1
        reasons.append("换手适中")

    if volume_ratio >= 2:
        score += 1
        reasons.append("量比>=2")

    if seal_money >= 100_000_000:
        score += 2
        reasons.append("封板资金>=1亿")
    elif seal_money >= 30_000_000:
        score += 1
        reasons.append("封板资金>=3000万")

    if streak >= 2:
        score += 1
        reasons.append("连板")

    if theme:
        score += 2
        reasons.append(f"题材:{theme}")

    if emotion in {"启动", "主升"}:
        score += 1
        reasons.append(f"情绪:{emotion}")
    elif emotion == "高潮":
        score -= 1
        reasons.append("情绪高潮降权")

    if score >= 7 and pct >= 5 and emotion in {"启动", "主升"}:
        signal = "BUY"
    elif score >= 4:
        signal = "HOLD"
    else:
        signal = "AVOID"

    return score, signal, reasons


def signal_from_score(row: pd.Series, emotion: str) -> str:
    score = int(row.get("分数", 0))
    pct = _num(row.get("涨跌幅"))
    lhb_verdict = str(row.get("龙虎榜确认", "未上榜"))
    if score >= 7 and pct >= 5 and emotion in {"启动", "主升"} and lhb_verdict != "强分歧":
        return "BUY"
    if score >= 4:
        return "HOLD"
    return "AVOID"


def sort_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return signals
    ranked = signals.copy()
    ranked["_信号排序"] = ranked["信号"].map({"BUY": 0, "HOLD": 1, "AVOID": 2}).fillna(9)
    sort_columns = [column for column in ["_信号排序", "分数", "题材强度", "龙虎榜净买额", "成交额"] if column in ranked.columns]
    ascending = [True] + [False] * (len(sort_columns) - 1)
    return ranked.sort_values(sort_columns, ascending=ascending).drop(columns=["_信号排序"])


def build_signals(raw: pd.DataFrame, min_score: int) -> tuple[pd.DataFrame, str, int, pd.DataFrame]:
    df = _pick_columns(raw).copy()
    if df.empty:
        df["题材"] = pd.Series(dtype="str")
        df["分数"] = pd.Series(dtype="int64")
        df["信号"] = pd.Series(dtype="str")
        df["理由"] = pd.Series(dtype="str")
        return df, "冰点", 0, pd.DataFrame()

    df["题材"] = df["名称"].fillna("").astype(str).apply(detect_theme)
    theme_stats = compute_theme_strength(df)
    limit_up_like_count = int((_pick_columns(raw)["涨跌幅"].apply(_num) >= 9.8).sum())
    emotion = market_emotion(limit_up_like_count)

    scored = df.apply(lambda row: score_row(row, emotion), axis=1, result_type="expand")
    df["分数"] = scored[0]
    df["信号"] = scored[1]
    df["理由"] = scored[2].apply(lambda items: "；".join(items))

    selected = df[df["分数"] >= min_score].copy()
    selected = apply_theme_strength(selected, theme_stats)
    if not selected.empty:
        selected["情绪周期"] = emotion
        selected["分数"] = selected["分数"] + selected["题材强度"].apply(lambda value: 1 if int(value) >= 5 else 0)
        selected["理由"] = selected.apply(
            lambda row: f"{row['理由']}；题材强度:{int(row['题材强度'])}" if int(row["题材强度"]) > 0 else row["理由"],
            axis=1,
        )
    selected = sort_signals(selected)
    return selected, emotion, limit_up_like_count, theme_stats


def apply_dragon_tiger(signals: pd.DataFrame, date: str | None, emotion: str) -> tuple[pd.DataFrame, dict[str, Any], str]:
    try:
        lhb, source = fetch_dragon_tiger(date)
    except Exception as exc:
        enriched = enrich_with_dragon_tiger(signals, pd.DataFrame())
        summary = summarize_dragon_tiger(enriched)
        return enriched, summary, f"龙虎榜获取失败: {type(exc).__name__}: {exc}"

    enriched = enrich_with_dragon_tiger(signals, lhb)
    if not enriched.empty:
        enriched["分数"] = enriched["分数"] + enriched["龙虎榜分"]
        enriched["理由"] = enriched.apply(
            lambda row: row["理由"]
            if row["龙虎榜确认"] == "未上榜"
            else f"{row['理由']}；龙虎榜:{row['龙虎榜确认']}",
            axis=1,
        )
        enriched["信号"] = enriched.apply(lambda row: signal_from_score(row, emotion), axis=1)
        enriched = sort_signals(enriched[enriched["分数"] >= 4])
    return enriched, summarize_dragon_tiger(enriched), source


def maybe_backtest_previous_signal(current_file_day: str) -> dict[str, Any]:
    previous = []
    for path in sorted(DATA_DIR.glob("signals_*.csv")):
        signal_date = path.stem.replace("signals_", "")
        if signal_date < current_file_day:
            previous.append(path)
    if not previous:
        return {
            "signal_date": "",
            "tested_rows": 0,
            "win_rate_1d": None,
            "avg_return_1d": None,
            "max_loss_1d": None,
            "grouped_path": "",
        }

    _, summary = backtest_signal_file(previous[-1], max_symbols=20)
    return {
        "signal_date": summary.signal_date,
        "tested_rows": summary.tested_rows,
        "win_rate_1d": summary.win_rate_by_horizon.get("1d"),
        "avg_return_1d": summary.avg_return_by_horizon.get("1d"),
        "max_loss_1d": summary.max_loss_by_horizon.get("1d"),
        "grouped_path": summary.grouped_output_path,
    }


def write_markdown(signals: pd.DataFrame, summary: RunSummary) -> None:
    path = Path(summary.markdown_path)
    lines = [
        f"# A股短线信号系统 3.0 - {summary.run_at[:10]}",
        "",
        f"- 运行时间：{summary.run_at}",
        f"- 数据源：{summary.source}",
        f"- 情绪周期：{summary.market_emotion}",
        f"- 接近涨停数量：{summary.limit_up_like_count}",
        f"- 获取数量：{summary.rows_fetched}",
        f"- 入选数量：{summary.rows_selected}",
        f"- 信号分布：BUY {summary.buy_count} / HOLD {summary.hold_count} / AVOID {summary.avoid_count}",
        f"- 龙虎榜来源：{summary.lhb_source}",
        f"- 龙虎榜匹配：上榜 {summary.lhb_listed_count} / 净买 {summary.lhb_positive_count} / 净卖 {summary.lhb_negative_count} / 净买额合计 {summary.lhb_net_buy_total:.0f}",
        f"- 回测摘要：信号日 {summary.backtest_signal_date or '无可回测历史信号'} / 样本 {summary.backtest_tested_rows} / 1日胜率 {summary.backtest_win_rate_1d if summary.backtest_win_rate_1d is not None else 'NA'} / 1日均值 {summary.backtest_avg_return_1d if summary.backtest_avg_return_1d is not None else 'NA'}",
        f"- 分组回测：{summary.backtest_grouped_path or '无'}",
        f"- 风控分布：PASS {summary.risk_pass_count} / WATCH {summary.risk_watch_count} / VETO {summary.risk_veto_count}",
        f"- 最强题材：{summary.top_theme or '无'} / 强度 {summary.top_theme_strength}",
        f"- AI Berkshire 候选：{summary.ai_candidates_count} / 状态 {summary.ai_berkshire_status} / 文件 {summary.ai_candidates_path}",
        f"- AI Berkshire 复核：PASS {summary.ai_pass_count} / WATCH {summary.ai_watch_count} / VETO {summary.ai_veto_count} / 文件 {summary.ai_review_path}",
        f"- 投资建议层：A {summary.advice_a_count} / B {summary.advice_b_count} / C {summary.advice_c_count} / D {summary.advice_d_count} / 文件 {summary.advice_path}",
        "",
        "> 仅用于研究和复盘，不构成个性化投资建议。BUY/HOLD/AVOID 是规则信号；A/B/C/D 是基于固定规则的研究建议层，必须结合账户风险和人工复核。",
        "> AI_PASS 不是买入建议，仅表示多角色复核未发现否决性问题；AI_WATCH/AI_VETO 会限制或否决建议层。",
        "",
    ]

    if signals.empty:
        lines.append("本次没有满足阈值的标的。")
    else:
        view = signals[
            [
                "代码",
                "名称",
                "信号",
                "分数",
                "题材",
                "题材强度",
                "涨跌幅",
                "成交额",
                "换手率",
                "量比",
                "龙虎榜确认",
                "龙虎榜净买额",
                "风控结论",
                "风控标签",
                "AI_Berkshire_复核",
                "AI_Berkshire_短线",
                "AI_Berkshire_财务",
                "AI_Berkshire_风险",
                "理由",
            ]
        ].head(80)
        lines.append(view.to_markdown(index=False))
        if len(signals) > len(view):
            lines.append("")
            lines.append(f"仅展示前 {len(view)} 条，完整明细见 CSV。")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(date: str | None, min_score: int) -> RunSummary:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_day = datetime.now().strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"{file_day}.log"
    csv_path = DATA_DIR / f"signals_{file_day}.csv"
    markdown_path = LOG_DIR / f"{file_day}.md"

    raw, source = fetch_market_data(date)
    signals, emotion, limit_up_like_count, theme_stats = build_signals(raw, min_score)
    signals, lhb_summary, lhb_source = apply_dragon_tiger(signals, date, emotion)
    signals = apply_risk_controls(signals)
    if not signals.empty:
        signals = sort_signals(signals)
    backtest_summary = maybe_backtest_previous_signal(file_day)
    advice_context = {
        "market_emotion": emotion,
        "backtest_tested_rows": int(backtest_summary["tested_rows"]),
        "backtest_win_rate_1d": backtest_summary["win_rate_1d"],
        "finance_data_available": False,
    }
    ai_output_path = DATA_DIR / f"ai_berkshire_candidates_{file_day}.csv"
    ai_summary = export_ai_berkshire_candidates(signals, ai_output_path)
    reviewed_signals = review_candidates(signals, advice_context)
    reviewed_signals.to_csv(csv_path, index=False, encoding="utf-8-sig")
    ai_review_output_path = DATA_DIR / f"ai_berkshire_review_{file_day}.csv"
    ai_review_summary = export_ai_berkshire_review(reviewed_signals, ai_review_output_path, advice_context)
    advice_output_path = DATA_DIR / f"advice_{file_day}.csv"
    advice_summary = export_advice(reviewed_signals, advice_output_path, advice_context)
    top_theme = ""
    top_theme_strength = 0
    if not theme_stats.empty:
        top_theme = str(theme_stats.iloc[0]["题材"])
        top_theme_strength = int(theme_stats.iloc[0]["题材强度"])

    summary = RunSummary(
        run_at=run_at,
        source=source,
        market_emotion=emotion,
        limit_up_like_count=limit_up_like_count,
        rows_fetched=len(raw),
        rows_selected=len(reviewed_signals),
        buy_count=int((reviewed_signals["信号"] == "BUY").sum()) if not reviewed_signals.empty else 0,
        hold_count=int((reviewed_signals["信号"] == "HOLD").sum()) if not reviewed_signals.empty else 0,
        avoid_count=int((reviewed_signals["信号"] == "AVOID").sum()) if not reviewed_signals.empty else 0,
        lhb_source=lhb_source,
        lhb_listed_count=int(lhb_summary["lhb_listed_count"]),
        lhb_positive_count=int(lhb_summary["lhb_positive_count"]),
        lhb_negative_count=int(lhb_summary["lhb_negative_count"]),
        lhb_net_buy_total=float(lhb_summary["lhb_net_buy_total"]),
        backtest_signal_date=str(backtest_summary["signal_date"]),
        backtest_tested_rows=int(backtest_summary["tested_rows"]),
        backtest_win_rate_1d=backtest_summary["win_rate_1d"],
        backtest_avg_return_1d=backtest_summary["avg_return_1d"],
        backtest_max_loss_1d=backtest_summary["max_loss_1d"],
        backtest_grouped_path=str(backtest_summary["grouped_path"]),
        risk_pass_count=int((reviewed_signals["风控结论"] == "PASS").sum()) if not reviewed_signals.empty else 0,
        risk_watch_count=int((reviewed_signals["风控结论"] == "WATCH").sum()) if not reviewed_signals.empty else 0,
        risk_veto_count=int((reviewed_signals["风控结论"] == "VETO").sum()) if not reviewed_signals.empty else 0,
        top_theme=top_theme,
        top_theme_strength=top_theme_strength,
        ai_candidates_count=int(ai_summary["ai_candidates_count"]),
        ai_candidates_path=str(ai_summary["ai_candidates_path"]),
        ai_berkshire_status=str(ai_summary["ai_berkshire_status"]),
        advice_count=int(advice_summary["advice_count"]),
        advice_a_count=int(advice_summary["advice_a_count"]),
        advice_b_count=int(advice_summary["advice_b_count"]),
        advice_c_count=int(advice_summary["advice_c_count"]),
        advice_d_count=int(advice_summary["advice_d_count"]),
        advice_path=str(advice_summary["advice_path"]),
        ai_review_count=int(ai_review_summary["ai_review_count"]),
        ai_pass_count=int(ai_review_summary["ai_pass_count"]),
        ai_watch_count=int(ai_review_summary["ai_watch_count"]),
        ai_veto_count=int(ai_review_summary["ai_veto_count"]),
        ai_review_path=str(ai_review_summary["ai_review_path"]),
        csv_path=str(csv_path),
        markdown_path=str(markdown_path),
        log_path=str(log_path),
    )

    write_markdown(reviewed_signals, summary)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(summary), ensure_ascii=False) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run A-share Berkshire short-term signal engine.")
    parser.add_argument("--date", help="Trading date in YYYYMMDD format. Defaults to latest available data.")
    parser.add_argument("--min-score", type=int, default=4, help="Minimum score to include in output.")
    args = parser.parse_args()

    try:
        summary = run(args.date, args.min_score)
    except Exception as exc:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        error_path = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.error.log"
        error_path.write_text(f"{datetime.now().isoformat()} {type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
