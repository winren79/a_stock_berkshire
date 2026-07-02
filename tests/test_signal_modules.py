import pandas as pd

from advice_engine import build_advice
from ai_berkshire_gate import export_ai_berkshire_candidates
from ai_berkshire_review import review_candidates
from backtest import backtest_signal_file
from data_sources import fetch_market_data_result, validate_market_frame
from dragon_tiger import enrich_with_dragon_tiger, fetch_dragon_tiger, normalize_code, summarize_dragon_tiger
from fund_flow import enrich_with_fund_flow, summarize_fund_flow
from risk_control import apply_risk_controls
from run_card import write_run_card
from stock_engine import build_signals, fetch_market_data
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


def test_enrich_with_fund_flow_scores_positive_and_negative_matches():
    signals = pd.DataFrame(
        [
            {"代码": "000021", "名称": "深科技", "分数": 6, "理由": "测试"},
            {"代码": "300024", "名称": "机器人", "分数": 7, "理由": "测试"},
            {"代码": "688503", "名称": "聚和材料", "分数": 7, "理由": "测试"},
        ]
    )
    flow = pd.DataFrame(
        [
            {"代码": "000021", "名称": "深科技", "主力净流入": "8000万"},
            {"代码": "300024", "名称": "机器人", "主力净流入": "-7000万"},
        ]
    )

    enriched = enrich_with_fund_flow(signals, flow)

    assert enriched.loc[enriched["代码"] == "000021", "资金流确认"].iloc[0] == "强确认"
    assert enriched.loc[enriched["代码"] == "000021", "分数"].iloc[0] == 7
    assert enriched.loc[enriched["代码"] == "300024", "资金流确认"].iloc[0] == "强分歧"
    assert enriched.loc[enriched["代码"] == "300024", "分数"].iloc[0] == 6
    assert enriched.loc[enriched["代码"] == "688503", "资金流确认"].iloc[0] == "未匹配"

    summary = summarize_fund_flow(enriched)
    assert summary["fund_flow_positive_count"] == 1
    assert summary["fund_flow_negative_count"] == 1


def test_fetch_dragon_tiger_falls_back_to_previous_available_date(monkeypatch):
    import dragon_tiger

    def fake_lhb(start_date, end_date):
        if start_date == "20260630":
            raise TypeError("'NoneType' object is not subscriptable")
        if start_date == "20260629":
            return pd.DataFrame(
                [
                    {
                        "代码": "000021",
                        "龙虎榜净买额": 80_000_000,
                    }
                ]
            )
        return pd.DataFrame()

    monkeypatch.setattr(dragon_tiger.ak, "stock_lhb_detail_em", fake_lhb)

    df, source = fetch_dragon_tiger("20260630", fallback_days=2)

    assert len(df) == 1
    assert df["代码"].iloc[0] == "000021"
    assert "start_date=20260629" in source
    assert "fallback from requested_date=20260630" in source


def test_fetch_dragon_tiger_reports_all_failed_dates(monkeypatch):
    import dragon_tiger

    monkeypatch.setattr(dragon_tiger.ak, "stock_lhb_detail_em", lambda *args, **kwargs: pd.DataFrame())

    try:
        fetch_dragon_tiger("20260630", fallback_days=1)
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("fetch_dragon_tiger should fail when all fallback dates are empty")

    assert "20260630: empty or invalid dataframe" in message
    assert "20260629: empty or invalid dataframe" in message


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
    assert summary["ai_berkshire_status"] == "rule_review_enabled"
    exported = pd.read_csv(output)
    assert exported["AI_Berkshire_状态"].iloc[0] == "queued_for_rule_review"


def test_fetch_market_data_falls_back_to_sina_when_eastmoney_fails(monkeypatch):
    import stock_engine

    seen_dates = []

    def fail_zt(*args, **kwargs):
        seen_dates.append(kwargs.get("date"))
        raise ConnectionError("eastmoney zt unavailable")

    def fail(*args, **kwargs):
        raise ConnectionError("eastmoney unavailable")

    fallback = pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"测试{i}",
                "最新价": 10.0,
                "涨跌幅": 1.2,
                "成交额": 1_000_000_000,
            }
            for i in range(100)
        ]
    )

    monkeypatch.setattr(stock_engine.ak, "stock_zt_pool_em", fail_zt)
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot_em", fail)
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot", lambda: fallback)

    df, source = fetch_market_data(date="20260630")

    assert source == "akshare.stock_zh_a_spot(fallback: eastmoney spot unavailable)"
    assert df["代码"].iloc[0] == "000000"
    assert seen_dates == ["20260630"]


def test_data_source_result_records_chain_warnings(monkeypatch):
    import data_sources

    def fail_zt(*args, **kwargs):
        raise ConnectionError("zt down")

    fallback = pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"测试{i}",
                "最新价": 10.0,
                "涨跌幅": 1.2,
                "成交额": 1_000_000_000,
            }
            for i in range(100)
        ]
    )

    monkeypatch.setattr(data_sources.ak, "stock_zt_pool_em", fail_zt)
    monkeypatch.setattr(data_sources.ak, "stock_zh_a_spot_em", lambda: fallback)

    result = fetch_market_data_result(date="20260630")

    assert result.source == "akshare.stock_zh_a_spot_em"
    assert result.stale is False
    assert result.quality.total_rows == 100
    assert result.quality.usable_amount_rows == 100
    assert any("stock_zt_pool_em" in warning and "zt down" in warning for warning in result.warnings)


def test_validate_market_frame_flags_dirty_rows():
    dirty = pd.DataFrame(
        [
            {"代码": "000001", "名称": "正常", "最新价": 10, "涨跌幅": 1.2, "成交额": 100_000_000},
            {"代码": "", "名称": "缺代码", "最新价": 0, "涨跌幅": 0, "成交额": 0},
        ]
    )

    report = validate_market_frame(dirty)

    assert report.total_rows == 2
    assert report.usable_amount_rows == 1
    assert report.zero_price_rows == 1
    assert report.missing_code_rows == 1
    assert report.is_usable is False
    assert "可用成交额行数过少" in "；".join(report.warnings)


def test_backtest_skips_symbols_when_history_fetch_fails(monkeypatch, tmp_path):
    import backtest

    signal_file = tmp_path / "signals_2026-06-29.csv"
    pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "信号": "HOLD",
                "分数": 5,
            }
        ]
    ).to_csv(signal_file, index=False)

    monkeypatch.setattr(backtest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        backtest,
        "returns_for_symbol",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("history unavailable")),
    )

    result_df, summary = backtest_signal_file(signal_file, max_symbols=1)

    assert result_df.empty
    assert summary.tested_rows == 0
    assert summary.skipped_rows == 1


def test_fetch_market_data_uses_stale_snapshot_when_live_values_are_unusable(monkeypatch, tmp_path):
    import stock_engine

    zero_live = pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"测试{i}",
                "最新价": 0,
                "涨跌幅": 0,
                "成交额": 0,
            }
            for i in range(100)
        ]
    )

    monkeypatch.setattr(stock_engine, "DATA_DIR", tmp_path)
    pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"测试{i}",
                "最新价": 10,
                "涨跌幅": 1.2,
                "成交额": 1_000_000_000,
            }
            for i in range(100)
        ]
    ).to_csv(tmp_path / "signals_2026-06-30.csv", index=False)
    monkeypatch.setattr(stock_engine.ak, "stock_zt_pool_em", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot_em", lambda: zero_live)
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot", lambda: zero_live)

    df, source = fetch_market_data(date="20260701")

    assert len(df) == 100
    assert df["代码"].iloc[0] == "000000"
    assert "stale fallback" in source
    assert "signals_2026-06-30.csv" in source
    assert "unusable zero market values" in source


def test_fetch_market_data_accepts_small_stale_signal_snapshot(monkeypatch, tmp_path):
    import stock_engine

    zero_live = pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"测试{i}",
                "最新价": 0,
                "涨跌幅": 0,
                "成交额": 0,
            }
            for i in range(100)
        ]
    )

    monkeypatch.setattr(stock_engine, "DATA_DIR", tmp_path)
    pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "最新价": 10,
                "涨跌幅": 1.2,
                "成交额": 1_000_000_000,
            }
        ]
    ).to_csv(tmp_path / "signals_2026-06-30.csv", index=False)
    monkeypatch.setattr(stock_engine.ak, "stock_zt_pool_em", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot_em", lambda: zero_live)
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot", lambda: zero_live)

    df, source = fetch_market_data(date="20260701")

    assert len(df) == 1
    assert df["代码"].iloc[0] == "000001"
    assert "stale fallback" in source


def test_fetch_market_data_uses_stale_snapshot_when_requested_date_has_dashes(monkeypatch, tmp_path):
    import stock_engine

    zero_live = pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"测试{i}",
                "最新价": 0,
                "涨跌幅": 0,
                "成交额": 0,
            }
            for i in range(100)
        ]
    )

    monkeypatch.setattr(stock_engine, "DATA_DIR", tmp_path)
    pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "最新价": 10,
                "涨跌幅": 1.2,
                "成交额": 1_000_000_000,
            }
        ]
    ).to_csv(tmp_path / "signals_2026-07-01.csv", index=False)
    monkeypatch.setattr(stock_engine.ak, "stock_zt_pool_em", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot_em", lambda: zero_live)
    monkeypatch.setattr(stock_engine.ak, "stock_zh_a_spot", lambda: zero_live)

    df, source = fetch_market_data(date="2026-07-02")

    assert len(df) == 1
    assert df["代码"].iloc[0] == "000001"
    assert "signals_2026-07-01.csv" in source


def test_build_signals_preserves_market_emotion_on_selected_rows():
    raw = pd.DataFrame(
        [
            {
                "代码": f"000{i:03d}",
                "名称": f"半导体测试{i}",
                "最新价": 10,
                "涨跌幅": 10,
                "成交额": 2_000_000_000,
                "换手率": 10,
                "封板资金": 100_000_000,
                "连板数": 1,
            }
            for i in range(65)
        ]
    )

    signals, emotion, _, _ = build_signals(raw, min_score=4)

    assert emotion == "主升"
    assert "情绪周期" in signals.columns
    assert set(signals["情绪周期"]) == {"主升"}


def test_advice_engine_allows_a_only_with_actionable_evidence():
    signals = pd.DataFrame(
        [
            {
                "代码": "600363",
                "名称": "联创光电",
                "信号": "BUY",
                "分数": 8,
                "题材": "半导体",
                "题材强度": 7,
                "情绪周期": "主升",
                "最新价": 35.78,
                "涨跌幅": 9.9,
                "成交额": 1_300_000_000,
                "龙虎榜确认": "未上榜",
                "风控结论": "PASS",
                "风控标签": "",
                "AI_Berkshire_复核": "AI_PASS",
                "理由": "测试",
            }
        ]
    )

    advice = build_advice(signals, {"market_emotion": "主升", "backtest_tested_rows": 20})

    assert advice["建议等级"].iloc[0] == "A"
    assert advice["建议动作"].iloc[0] == "可执行计划"
    assert advice["建议仓位上限_pct"].iloc[0] == 1.0


def test_advice_engine_preserves_fund_flow_fields_for_recommendation_review():
    signals = pd.DataFrame(
        [
            {
                "代码": "600641",
                "名称": "先导基电",
                "信号": "HOLD",
                "分数": 7,
                "题材": "",
                "题材强度": 0,
                "情绪周期": "启动",
                "最新价": 48.24,
                "涨跌幅": 10,
                "成交额": 1_300_000_000,
                "龙虎榜确认": "强确认",
                "资金流确认": "强确认",
                "主力净流入": 80_000_000,
                "风控结论": "PASS",
                "风控标签": "",
                "AI_Berkshire_复核": "AI_WATCH",
                "理由": "测试",
            }
        ]
    )

    advice = build_advice(signals, {"market_emotion": "启动", "backtest_tested_rows": 20})

    assert advice["资金流确认"].iloc[0] == "强确认"
    assert advice["主力净流入"].iloc[0] == 80_000_000


def test_advice_engine_downgrades_overheated_or_disputed_rows():
    signals = pd.DataFrame(
        [
            {
                "代码": "603078",
                "名称": "江化微",
                "信号": "HOLD",
                "分数": 4,
                "题材": "半导体",
                "题材强度": 7,
                "情绪周期": "高潮",
                "最新价": 49.42,
                "涨跌幅": 9.99,
                "成交额": 2_100_000_000,
                "龙虎榜确认": "强分歧",
                "风控结论": "WATCH",
                "风控标签": "龙虎榜强分歧",
                "理由": "测试",
            }
        ]
    )

    advice = build_advice(signals, {"market_emotion": "高潮", "backtest_tested_rows": 20})

    assert advice["建议等级"].iloc[0] == "D"
    assert advice["建议动作"].iloc[0] == "回避"
    assert advice["建议仓位上限_pct"].iloc[0] == 0.0


def test_ai_berkshire_review_constrains_advice_layer():
    signals = pd.DataFrame(
        [
            {
                "代码": "600363",
                "名称": "联创光电",
                "信号": "HOLD",
                "分数": 8,
                "题材": "半导体",
                "题材强度": 7,
                "情绪周期": "高潮",
                "最新价": 35.78,
                "涨跌幅": 9.99,
                "成交额": 1_370_000_000,
                "龙虎榜确认": "未上榜",
                "风控结论": "PASS",
                "风控标签": "",
                "理由": "测试",
            },
            {
                "代码": "603078",
                "名称": "江化微",
                "信号": "HOLD",
                "分数": 4,
                "题材": "半导体",
                "题材强度": 7,
                "情绪周期": "高潮",
                "最新价": 49.42,
                "涨跌幅": 9.99,
                "成交额": 2_100_000_000,
                "龙虎榜确认": "强分歧",
                "风控结论": "WATCH",
                "风控标签": "龙虎榜强分歧",
                "理由": "测试",
            },
        ]
    )

    reviewed = review_candidates(signals, {"market_emotion": "高潮", "backtest_tested_rows": 20})
    advice = build_advice(reviewed, {"market_emotion": "高潮", "backtest_tested_rows": 20})

    assert reviewed.loc[reviewed["代码"] == "600363", "AI_Berkshire_复核"].iloc[0] == "AI_WATCH"
    assert reviewed.loc[reviewed["代码"] == "603078", "AI_Berkshire_复核"].iloc[0] == "AI_VETO"
    assert advice.loc[advice["代码"] == "600363", "建议等级"].iloc[0] == "B"
    assert advice.loc[advice["代码"] == "603078", "建议等级"].iloc[0] == "D"


def test_ai_berkshire_review_treats_missing_financial_data_as_watch_not_veto():
    signals = pd.DataFrame(
        [
            {
                "代码": "002407",
                "名称": "多氟多",
                "信号": "BUY",
                "分数": 7,
                "题材": "",
                "题材强度": 0,
                "情绪周期": "启动",
                "最新价": 20.0,
                "涨跌幅": 9.99,
                "成交额": 3_500_000_000,
                "龙虎榜确认": "强确认",
                "风控结论": "PASS",
                "风控标签": "",
                "理由": "测试",
            }
        ]
    )

    reviewed = review_candidates(signals, {"market_emotion": "启动", "backtest_tested_rows": 11})

    assert reviewed["AI_Berkshire_复核"].iloc[0] == "AI_WATCH"
    assert "回测样本不足" in reviewed["AI_Berkshire_财务"].iloc[0]


def test_backtest_groups_include_ai_review_and_advice_grade(monkeypatch, tmp_path):
    import backtest

    signal_file = tmp_path / "signals_2026-06-29.csv"
    pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "信号": "HOLD",
                "分数": 5,
                "AI_Berkshire_复核": "AI_WATCH",
                "建议等级": "B",
            }
        ]
    ).to_csv(signal_file, index=False)

    monkeypatch.setattr(backtest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(backtest, "returns_for_symbol", lambda *args, **kwargs: {"1d": 1.2, "3d": -0.5, "5d": 2.0})

    result_df, summary = backtest_signal_file(signal_file, max_symbols=1)
    group_df = pd.read_csv(summary.grouped_output_path)

    assert result_df["AI_Berkshire_复核"].iloc[0] == "AI_WATCH"
    assert result_df["建议等级"].iloc[0] == "B"
    assert "AI_Berkshire_复核" in set(group_df["分组字段"])
    assert "建议等级" in set(group_df["分组字段"])


def test_backtest_preserves_existing_non_empty_results_when_fetch_fails(monkeypatch, tmp_path):
    import backtest

    signal_file = tmp_path / "signals_2026-06-30.csv"
    pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "信号": "HOLD",
                "分数": 5,
            }
        ]
    ).to_csv(signal_file, index=False)
    existing = pd.DataFrame(
        [
            {
                "信号日期": "2026-06-30",
                "代码": "000001",
                "名称": "平安银行",
                "原信号": "HOLD",
                "原分数": 5,
                "1d": 1.5,
                "3d": 2.0,
                "5d": 3.0,
            }
        ]
    )
    existing.to_csv(tmp_path / "backtest_2026-06-30.csv", index=False)

    monkeypatch.setattr(backtest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        backtest,
        "returns_for_symbol",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("history unavailable")),
    )

    result_df, summary = backtest_signal_file(signal_file, max_symbols=1)

    assert summary.tested_rows == 1
    assert summary.win_rate_by_horizon["1d"] == 100.0
    assert result_df["1d"].iloc[0] == 1.5
    assert pd.read_csv(tmp_path / "backtest_2026-06-30.csv")["1d"].iloc[0] == 1.5


def test_fetch_history_falls_back_to_tx_daily_source(monkeypatch):
    import backtest

    def fail_em(*args, **kwargs):
        raise ConnectionError("eastmoney history unavailable")

    def tx_history(**kwargs):
        assert kwargs["symbol"] == "sz000001"
        return pd.DataFrame(
            [
                {"date": "2026-06-30", "close": 10.0},
                {"date": "2026-07-01", "close": 11.0},
            ]
        )

    monkeypatch.setattr(backtest.ak, "stock_zh_a_hist", fail_em)
    monkeypatch.setattr(backtest.ak, "stock_zh_a_hist_tx", tx_history)

    returns = backtest.returns_for_symbol("000001", "2026-06-30", [1])

    assert returns["1d"] == 10.000000000000009
