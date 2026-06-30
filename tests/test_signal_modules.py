import pandas as pd

from ai_berkshire_gate import export_ai_berkshire_candidates
from dragon_tiger import enrich_with_dragon_tiger, normalize_code, summarize_dragon_tiger
from risk_control import apply_risk_controls
from theme_strength import compute_theme_strength


def test_normalize_code_keeps_six_digits():
    assert normalize_code("21") == "000021"
    assert normalize_code("000021") == "000021"
    assert normalize_code(21) == "000021"


def test_enrich_with_dragon_tiger_marks_positive_and_negative_matches():
    signals = pd.DataFrame(
        [
            {"代码": "000021", "名称": "深科技", "分数": 6},
            {"代码": "300024", "名称": "机器人", "分数": 7},
            {"代码": "688503", "名称": "聚和材料", "分数": 7},
        ]
    )
    lhb = pd.DataFrame(
        [
            {
                "代码": "000021",
                "龙虎榜净买额": 80_000_000,
                "龙虎榜买入额": 120_000_000,
                "龙虎榜卖出额": 40_000_000,
                "上榜原因": "日涨幅偏离值达到7%",
                "解读": "机构买入",
            },
            {
                "代码": "300024",
                "龙虎榜净买额": -60_000_000,
                "龙虎榜买入额": 20_000_000,
                "龙虎榜卖出额": 80_000_000,
                "上榜原因": "日换手率达到20%",
                "解读": "普通席位卖出",
            },
        ]
    )

    enriched = enrich_with_dragon_tiger(signals, lhb)

    assert enriched.loc[enriched["代码"] == "000021", "龙虎榜确认"].iloc[0] == "强确认"
    assert enriched.loc[enriched["代码"] == "300024", "龙虎榜确认"].iloc[0] == "强分歧"
    assert enriched.loc[enriched["代码"] == "688503", "龙虎榜确认"].iloc[0] == "未上榜"

    summary = summarize_dragon_tiger(enriched)
    assert summary["lhb_listed_count"] == 2
    assert summary["lhb_positive_count"] == 1
    assert summary["lhb_negative_count"] == 1


def test_risk_controls_veto_st_and_retired_names():
    signals = pd.DataFrame(
        [
            {
                "代码": "000004",
                "名称": "国华退",
                "涨跌幅": 10,
                "成交额": 100_000_000,
                "换手率": 40,
                "龙虎榜确认": "强分歧",
                "题材": "",
                "分数": 8,
                "信号": "BUY",
                "理由": "测试",
            }
        ]
    )
    enriched = apply_risk_controls(signals)
    assert enriched["风控结论"].iloc[0] == "VETO"
    assert enriched["信号"].iloc[0] == "AVOID"
    assert "ST/退市风险" in enriched["风控标签"].iloc[0]


def test_theme_strength_scores_group_activity():
    universe = pd.DataFrame(
        [
            {"代码": "000001", "题材": "AI", "涨跌幅": 10, "成交额": 20_000_000_000},
            {"代码": "000002", "题材": "AI", "涨跌幅": 6, "成交额": 20_000_000_000},
            {"代码": "000003", "题材": "AI", "涨跌幅": 1, "成交额": 20_000_000_000},
            {"代码": "000004", "题材": "机器人", "涨跌幅": 1, "成交额": 100_000_000},
        ]
    )
    stats = compute_theme_strength(universe)
    ai = stats[stats["题材"] == "AI"].iloc[0]
    assert ai["题材强度"] >= 5


def test_ai_berkshire_candidate_export(tmp_path):
    signals = pd.DataFrame(
        [
            {
                "代码": "000021",
                "名称": "深科技",
                "信号": "HOLD",
                "分数": 6,
                "题材": "",
                "题材强度": 0,
                "涨跌幅": 10,
                "成交额": 1_000_000_000,
                "换手率": 10,
                "龙虎榜确认": "强确认",
                "龙虎榜净买额": 80_000_000,
                "风控结论": "PASS",
                "风控标签": "",
                "理由": "测试",
            }
        ]
    )
    output = tmp_path / "candidates.csv"
    summary = export_ai_berkshire_candidates(signals, output)
    assert summary["ai_candidates_count"] == 1
    exported = pd.read_csv(output)
    assert exported["AI_Berkshire_状态"].iloc[0] == "待评估"
