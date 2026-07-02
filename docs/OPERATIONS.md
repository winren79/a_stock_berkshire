# 运维说明

## 本地运行检查

```bash
cd /Users/hechen/Documents/Codex/a_stock_berkshire
./scripts/run.sh
tail -n 80 logs/cron.log
```

## Codex Cron

当前推荐三段任务：

| 任务 | 时间 | 用途 |
|---|---:|---|
| `a-3-0` | 09:00 | 开盘前 / 早盘信号 |
| `a-3-0-2` | 11:30 | 午间修正 |
| `a-3-0-3` | 15:00 | 收盘确认 |

检查任务配置：

```bash
sed -n '1,220p' /Users/hechen/.codex/automations/a-3-0/automation.toml
sed -n '1,220p' /Users/hechen/.codex/automations/a-3-0-2/automation.toml
sed -n '1,220p' /Users/hechen/.codex/automations/a-3-0-3/automation.toml
```

## 每次运行后的最低验证

必须确认：

- `logs/YYYY-MM-DD.md` 已生成或更新
- `data/signals_YYYY-MM-DD.csv` 已生成或更新
- `logs/YYYY-MM-DD.log` 有 JSON 摘要
- `logs/cron.log` 没有 `failed`
- 报告中有 rows_fetched 和 rows_selected
- 报告中有风控分布和最强题材
- `data/ai_berkshire_candidates_YYYY-MM-DD.csv` 已生成
- `data/ai_berkshire_review_YYYY-MM-DD.csv` 已生成
- `data/advice_YYYY-MM-DD.csv` 已生成

## 故障处理

### 依赖缺失

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### AkShare 数据源慢

全市场实时行情接口可能需要 1-2 分钟。不要在未完成时判断失败。

### AkShare 数据源失败

检查：

```bash
tail -n 120 logs/cron.log
ls -lh logs/
```

报告时必须给出错误类型和日志路径。

### 回测样本为 0

这是常见正常情况，原因是：

- 只有当天信号，没有未来行情
- 信号文件太新
- 标的历史行情接口暂时不可用

不能据此声称系统胜率。

### AI Berkshire 复核为空或全是 WATCH

如果报告中显示 AI Berkshire 复核全是 `AI_WATCH`，优先检查：

- `backtest_tested_rows` 是否小于 20
- 是否缺少财务双源数据
- 当日是否处于 `高潮` 情绪周期
- 龙虎榜是否出现强分歧

这不是程序错误，而是第二道风控在收紧。只有当回测样本、基础风控、题材强度和复核层都通过时，建议层才可能给出 A 级。

当前复核是本地规则化 AI Berkshire 复核，不等同于远端真实多 Agent 深度投研。不要说“远端 AI Berkshire 团队已完成研究”。

## 发布前清理

发布到 GitHub 前，不应提交：

- `venv/`
- `__pycache__/`
- `logs/`
- `data/`
- 本地自动任务配置

`.gitignore` 已默认忽略这些路径。
