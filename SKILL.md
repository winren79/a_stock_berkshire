---
name: a-stock-signal-system
description: "运行、复盘、验证或升级 A股短线规则信号系统。适用于 A股短线股票池、数据源质量校验、龙虎榜/资金流验证、Run Card、假设注册表、回测统计验证、BUY/HOLD/AVOID 规则信号、Codex cron 检查。"
---

# A股短线规则信号系统

当用户要求运行、复盘、验证、解释或升级 A股短线规则信号系统时，使用本 skill。

## 固定路径

```bash
/Users/hechen/Documents/Codex/a_stock_berkshire
```

## 标准运行

```bash
cd /Users/hechen/Documents/Codex/a_stock_berkshire
./scripts/run.sh
```

运行后必须验证：

```bash
tail -n 80 logs/cron.log
sed -n '1,120p' logs/$(date '+%Y-%m-%d').md
test -f data/runs/$(date '+%Y-%m-%d')/run_card.json
test -f data/hypotheses.json
```

## 必须汇报

- 报告路径
- CSV 路径
- rows_fetched
- rows_selected
- market_emotion
- BUY / HOLD / AVOID 数量
- lhb_listed_count
- lhb_net_buy_total
- fund_flow_matched_count / fund_flow_positive_count / fund_flow_negative_count
- backtest_tested_rows
- backtest_win_rate_1d
- backtest_validation_status_1d
- risk_pass_count / risk_watch_count / risk_veto_count
- top_theme / top_theme_strength
- ai_candidates_path / ai_berkshire_status
- ai_review_path / ai_pass_count / ai_watch_count / ai_veto_count
- advice_path / advice_a_count / advice_b_count / advice_c_count / advice_d_count
- data_warnings，尤其是否使用 stale fallback
- run_card_json_path / hypothesis_registry_path / strategy_version
- 是否运行成功

## 复盘和回测

详细流程见 `RUNBOOK.md`。

手动回测：

```bash
cd /Users/hechen/Documents/Codex/a_stock_berkshire
venv/bin/python backtest.py --max-symbols 30
```

回测后同时检查：

```bash
ls -lh data/backtest_validation_*.json
```

`no_sample` 或 `insufficient_sample` 只能说明样本不足，不能说明系统有效。

## 严格边界

不要声称：

- 远端 AI Berkshire 多 Agent 已参与评分，除非代码或提示词实际调用了对应 skill。
- 已识别游资席位，除非已有席位标签库和匹配逻辑。
- 系统胜率已验证，除非 `backtest_tested_rows` 足够。
- AI Berkshire 已完成完整深度投研。当前只有本地规则化二次复核。
- `BUY` 是买入建议。
- 使用 stale fallback 时隐瞒数据源 warning。
- 样本不足时声称 bootstrap 或回测已经证明策略有效。

`BUY / HOLD / AVOID` 是规则标签，不构成投资建议。
`AI_PASS / AI_WATCH / AI_VETO` 是规则化二次复核标签，不构成投资建议。
Run Card 和 Hypothesis Registry 是审计与复盘工具，不是收益保证。
