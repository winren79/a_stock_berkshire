from dataclasses import dataclass

import pandas as pd

from run_card import write_run_card


@dataclass
class DummySummary:
    run_at: str
    source: str
    rows_fetched: int
    rows_selected: int
    market_emotion: str
    csv_path: str


def test_write_run_card_records_artifacts_hashes_and_warnings(tmp_path):
    signal_path = tmp_path / "signals.csv"
    pd.DataFrame([{"代码": "000001", "名称": "平安银行"}]).to_csv(signal_path, index=False)
    summary = DummySummary(
        run_at="2026-07-02 09:00:00",
        source="akshare.stock_zh_a_spot_em",
        rows_fetched=100,
        rows_selected=1,
        market_emotion="启动",
        csv_path=str(signal_path),
    )

    card = write_run_card(
        summary=summary,
        output_dir=tmp_path / "runs" / "2026-07-02",
        artifacts={"signals": signal_path},
        warnings=["stock_zt_pool_em failed"],
    )

    assert card["schema_version"] == "run_card.v1"
    assert card["summary"]["rows_selected"] == 1
    assert card["warnings"] == ["stock_zt_pool_em failed"]
    assert card["artifacts"][0]["name"] == "signals"
    assert len(card["artifacts"][0]["sha256"]) == 64
    assert (tmp_path / "runs" / "2026-07-02" / "run_card.json").exists()
    assert (tmp_path / "runs" / "2026-07-02" / "run_card.md").exists()
