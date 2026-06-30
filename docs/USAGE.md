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
- 回测摘要
- 风控分布
- 最强题材
- AI Berkshire 候选文件
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

## AI Berkshire 二次风控候选

每次运行会生成：

```bash
data/ai_berkshire_candidates_YYYY-MM-DD.csv
```

这个文件是给 Codex/AI Berkshire 做二次风控的输入。默认状态是：

```text
pending_manual_or_codex_skill_review
```

在没有实际评审并写回 `PASS / WATCH / VETO` 前，不要声称 AI Berkshire 已参与评分。

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

禁止这样解释：

- “系统预测明天上涨”
- “BUY 就可以买入”
- “AI Berkshire 已经参与评分”
- “AI Berkshire 已经完成风控”，除非候选文件已经被实际评审
- “样本为 0 但胜率很好”
- “未上榜就是资金不认可”
