import pandas as pd

from recommendations import build_recommendation_review, select_close_recommendations


def test_select_close_recommendations_excludes_veto_and_ranks_evidence():
    advice = pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "建议等级": "B",
                "建议动作": "等待触发",
                "信号": "BUY",
                "分数": 8,
                "题材强度": 6,
                "成交额": 2_000_000_000,
                "风控结论": "PASS",
                "AI_Berkshire_复核": "AI_WATCH",
                "龙虎榜确认": "强确认",
                "资金流确认": "强确认",
            },
            {
                "代码": "000002",
                "名称": "万科A",
                "建议等级": "D",
                "建议动作": "回避",
                "信号": "AVOID",
                "分数": 9,
                "题材强度": 9,
                "成交额": 5_000_000_000,
                "风控结论": "PASS",
                "AI_Berkshire_复核": "AI_VETO",
                "龙虎榜确认": "强确认",
                "资金流确认": "强确认",
            },
        ]
    )

    selected = select_close_recommendations(advice, limit=5)

    assert selected["代码"].tolist() == ["000001"]
    assert selected["推荐排名"].iloc[0] == 1
    assert "强确认" in selected["推荐证据"].iloc[0]


def test_build_recommendation_review_scores_next_day_returns():
    recommendations = pd.DataFrame(
        [
            {"推荐日期": "2026-07-01", "代码": "000001", "名称": "平安银行", "建议等级": "B"},
            {"推荐日期": "2026-07-01", "代码": "000002", "名称": "万科A", "建议等级": "B"},
        ]
    )
    returns = {"000001": {"1d": 2.3}, "000002": {"1d": -1.2}}

    reviewed, summary = build_recommendation_review(recommendations, returns)

    assert reviewed.loc[reviewed["代码"] == "000001", "复盘结论"].iloc[0] == "有价值"
    assert reviewed.loc[reviewed["代码"] == "000002", "复盘结论"].iloc[0] == "未验证"
    assert summary["reviewed_count"] == 2
    assert summary["valuable_count"] == 1
    assert summary["win_rate_1d"] == 50.0
