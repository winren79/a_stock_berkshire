from hypothesis_registry import record_daily_run


def test_record_daily_run_creates_and_updates_hypothesis(tmp_path):
    registry_path = tmp_path / "hypotheses.json"

    first = record_daily_run(
        registry_path=registry_path,
        hypothesis_id="short_signal_v1",
        title="A股短线规则信号",
        thesis="情绪、题材、资金、龙虎榜和AI复核组合能提高短线信号质量。",
        strategy_version="2026.07.phase2",
        run_card_path=tmp_path / "runs" / "run_card.json",
        metrics={"rows_selected": 3, "buy_count": 1},
    )
    second = record_daily_run(
        registry_path=registry_path,
        hypothesis_id="short_signal_v1",
        title="A股短线规则信号",
        thesis="情绪、题材、资金、龙虎榜和AI复核组合能提高短线信号质量。",
        strategy_version="2026.07.phase2",
        run_card_path=tmp_path / "runs" / "run_card_2.json",
        metrics={"rows_selected": 4, "buy_count": 2},
    )

    assert first["id"] == "short_signal_v1"
    assert second["status"] == "testing"
    assert second["strategy_version"] == "2026.07.phase2"
    assert len(second["runs"]) == 2
    assert second["runs"][-1]["metrics"]["buy_count"] == 2
    assert registry_path.exists()
