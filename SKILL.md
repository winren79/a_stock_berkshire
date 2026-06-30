---
name: a-stock-signal-system
description: "运行、复盘、验证或升级 A股短线规则信号系统。适用于 A股短线股票池、龙虎榜验证、回测、BUY/HOLD/AVOID 规则信号、Codex cron 检查。"
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
- backtest_tested_rows
- backtest_win_rate_1d
- risk_pass_count / risk_watch_count / risk_veto_count
- top_theme / top_theme_strength
- ai_candidates_path / ai_berkshire_status
- 是否运行成功

## 复盘和回测

详细流程见 `RUNBOOK.md`。

手动回测：

```bash
cd /Users/hechen/Documents/Codex/a_stock_berkshire
venv/bin/python backtest.py --max-symbols 30
```

## 严格边界

不要声称：

- AI Berkshire 已参与评分，除非代码或提示词实际调用了对应 skill。
- 已识别游资席位，除非已有席位标签库和匹配逻辑。
- 系统胜率已验证，除非 `backtest_tested_rows` 足够。
- AI Berkshire 已完成风控，除非候选文件已被实际评审并写回。
- `BUY` 是买入建议。

`BUY / HOLD / AVOID` 是规则标签，不构成投资建议。
