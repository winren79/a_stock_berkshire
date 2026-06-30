# A股短线规则信号系统 Runbook

## 适用场景

当用户要求运行、复盘、验证、解释或升级 A股短线规则信号系统时，使用本流程。

触发语示例：

- 运行 A股短线信号系统
- 复盘今天 A股短线股票池
- 查看 A股规则信号和龙虎榜验证
- 回测 A股短线系统
- 检查 09:00 / 11:30 / 15:00 cron 是否正常

## 系统边界

这是本地规则信号系统，不是自动交易系统。

当前能力：

- AkShare A股行情抓取
- 情绪周期判断
- 题材关键词过滤
- 资金强度评分
- 龙虎榜净买额验证
- 已保存历史信号的 1/3/5 日收益回测
- 分信号、分情绪、分龙虎榜、分题材、分风控结论的回测统计
- ST/退市、北交所、流动性、过热、分歧、题材集中风控
- 题材强度评分
- AI Berkshire 二次风控候选文件导出
- BUY / HOLD / AVOID 规则信号

当前没有：

- 券商下单
- 自动交易
- 游资席位标签识别
- 真正调用 AI Berkshire skill
- 自动写回 AI Berkshire PASS/WATCH/VETO
- 当天信号的未来收益胜率

## 固定路径

项目目录：

```bash
/Users/hechen/Documents/Codex/a_stock_berkshire
```

核心文件：

```bash
stock_engine.py
dragon_tiger.py
backtest.py
risk_control.py
theme_strength.py
ai_berkshire_gate.py
scripts/run.sh
```

输出文件：

```bash
logs/YYYY-MM-DD.md
logs/YYYY-MM-DD.log
logs/cron.log
data/signals_YYYY-MM-DD.csv
data/backtest_YYYY-MM-DD.csv
data/backtest_groups_YYYY-MM-DD.csv
data/ai_berkshire_candidates_YYYY-MM-DD.csv
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

最终汇报必须包含：

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

## 回测规则

手动回测最近一个信号文件：

```bash
cd /Users/hechen/Documents/Codex/a_stock_berkshire
venv/bin/python backtest.py --max-symbols 30
```

解释回测时必须说明：

- 回测只验证已经保存的历史信号文件
- 当天信号没有未来收益，`tested_rows: 0` 时不能声称胜率
- 样本数太少时只能说“样本不足”，不能说系统有效
- 分组回测文件存在不代表结论有效；必须看每组样本数

## 自动任务

Codex cron：

- `a-3-0`：09:00 开盘前
- `a-3-0-2`：11:30 午间修正
- `a-3-0-3`：15:00 收盘确认

三个任务都应该保持 ACTIVE。

检查配置：

```bash
sed -n '1,220p' /Users/hechen/.codex/automations/a-3-0/automation.toml
sed -n '1,220p' /Users/hechen/.codex/automations/a-3-0-2/automation.toml
sed -n '1,220p' /Users/hechen/.codex/automations/a-3-0-3/automation.toml
```

## 禁止误报

不要说：

- “AI Berkshire 已参与评分”
- “AI Berkshire 已完成风控”，除非候选文件已被实际评审并写回
- “已识别章盟主/佛山/量化席位”
- “系统胜率已验证”
- “BUY 是买入建议”
- “空结果代表市场没有机会”

只有在对应数据真实存在时才能说：

- AI Berkshire skill 已调用
- 游资席位已识别
- 回测有胜率
- 数据源有效返回

## 与 AI Berkshire 的合理组合

当前系统没有实际调用 AI Berkshire skill。

如果未来要结合，推荐作为二次风控层：

1. 本系统生成 Top 10-20 短线候选。
2. 对候选调用 AI Berkshire 的质量/新闻/行业风控。
3. AI Berkshire 只输出 PASS / WATCH / VETO。
4. 回测比较原始系统与 VETO 后系统。
5. 如果胜率、平均收益、最大回撤没有改善，不应声称 AI Berkshire 增强有效。

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

## 风控与题材
- PASS/WATCH/VETO：
- 最强题材：
- 题材强度：
- AI Berkshire 候选文件：
- AI Berkshire 状态：

## 结论
- 今天能确认的事实：
- 不能确认的部分：
- 下一步观察：
```
