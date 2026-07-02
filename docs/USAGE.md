# 使用说明

## 标准运行

```bash
cd /Users/hechen/Documents/Codex/a_stock_berkshire
./scripts/run.sh
```

## 查看报告

```bash
sed -n '1,160p' logs/$(date '+%Y-%m-%d').md
```

报告包含：

- 数据源
- 情绪周期
- 接近涨停数量
- 入选数量
- BUY / HOLD / AVOID 分布
- 龙虎榜匹配
- 资金流匹配
- 回测摘要
- 统计验证状态
- 风控分布
- 最强题材
- AI Berkshire 候选文件
- AI Berkshire 复核分布
- 投资建议层分布
- Run Card 路径
- 策略版本与假设注册表路径
- 前 80 条信号明细

## 查看 CSV

```bash
python3 - <<'PY'
import pandas as pd
df = pd.read_csv("data/signals_2026-06-29.csv", dtype={"代码": str})
print(df.head(20).to_string(index=False))
PY
```

## 手动回测

```bash
venv/bin/python backtest.py --max-symbols 30
```

指定信号文件：

```bash
venv/bin/python backtest.py --file data/signals_2026-06-29.csv --max-symbols 30
```

回测会同步生成：

```bash
data/backtest_YYYY-MM-DD.csv
data/backtest_groups_YYYY-MM-DD.csv
data/backtest_validation_YYYY-MM-DD.json
```

`backtest_validation_*.json` 中的状态含义：

- `no_sample`：没有可验证样本。
- `insufficient_sample`：样本不足，只能记录事实，不能声称有效。
- `validated_sample`：样本达到门槛，输出 bootstrap 均值置信区间。

## Run Card 与假设注册表

每次运行会生成：

```bash
data/runs/YYYY-MM-DD/run_card.json
data/runs/YYYY-MM-DD/run_card.md
data/hypotheses.json
```

Run Card 用于审计本次运行，包含数据源 warning、输出文件路径和 sha256。`hypotheses.json` 用于追踪固定研究假设和策略版本，避免每天只看孤立结果。

## AI Berkshire 二次风控

每次运行会生成：

```bash
data/ai_berkshire_candidates_YYYY-MM-DD.csv
data/ai_berkshire_review_YYYY-MM-DD.csv
```

候选文件是第二道风控的输入，复核文件是输出。当前实现是本地规则化 AI Berkshire 复核，不是远端真实多 Agent 深度投研。

复核层使用四个角色：

- 短线信号：检查信号、分数、题材强度、龙虎榜分歧。
- 财务验证：检查是否具备双源财务数据；缺失时按流动性和回测样本降级。
- 生意质量：检查题材是否清晰，但不会把题材等同于好生意。
- 风险控制：检查情绪高潮、龙虎榜分歧、基础风控标签。

输出状态：

```text
AI_PASS
AI_WATCH
AI_VETO
```

`AI_PASS` 不是买入建议，只表示规则化二次复核未发现否决性问题。`AI_WATCH` 会限制建议层，`AI_VETO` 会进入回避。

## 复盘模板

```markdown
# A股短线规则信号复盘 - YYYY-MM-DD

## 运行状态
- 报告：
- CSV：
- 数据源：
- rows_fetched：
- rows_selected：

## 信号分布
- BUY：
- HOLD：
- AVOID：

## 情绪周期
- market_emotion：
- limit_up_like_count：

## 龙虎榜验证
- 上榜数量：
- 净买数量：
- 净卖数量：
- 净买额合计：
- 强确认标的：
- 强分歧标的：

## 资金流验证
- 匹配数量：
- 强确认数量：
- 强分歧数量：
- 主力净流入合计：

## 回测验证
- 回测信号日期：
- 样本数：
- 1日胜率：
- 1日平均收益：
- 样本是否足够：

## 结论
- 今天能确认的事实：
- 不能确认的部分：
- 下一步观察：
```

## 解释规则

必须这样解释：

- `BUY / HOLD / AVOID` 是规则标签，不是交易建议。
- 回测样本不足时不能声称系统有效。
- 龙虎榜未上榜不等于利空，只表示没有匹配到龙虎榜确认。
- 情绪周期为 `高潮` 时，系统会降权，避免追高。
- `WATCH` 表示需要观察，不等于否决。
- `VETO` 表示规则风控否决，不等于未来一定下跌。
- `AI_PASS / AI_WATCH / AI_VETO` 是 AI Berkshire 规则化二次复核标签，不是完整深度投研结论。
- `A / B / C / D` 是建议层等级，不是账户个性化交易指令。

禁止这样解释：

- “系统预测明天上涨”
- “BUY 就可以买入”
- “AI Berkshire 远端多 Agent 已经参与评分”
- “AI Berkshire 已经完成完整深度投研”
- “样本为 0 但胜率很好”
- “未上榜就是资金不认可”
- “样本不足但 bootstrap 已经证明策略有效”
- “使用 stale fallback 时不需要披露数据源 warning”
