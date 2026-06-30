# 架构说明

## 目标

系统目标不是预测股票，也不是自动交易，而是把 A股短线复盘流程固化为可重复运行、可审计、可回测的规则信号系统。

核心原则：

- 数据先行：所有结论必须来自已抓取的数据或明确标注为规则判断。
- 风控优先：情绪高潮、龙虎榜分歧、回测样本不足时不输出强结论。
- 可审计：每次运行必须保存 Markdown 报告、CSV 明细和 JSON 摘要日志。
- 不夸大：没有 AI Berkshire 调用时，不声称 AI Berkshire 已参与评分。

## 数据流

```text
AkShare 行情数据
    ↓
涨停池 / 全市场行情回退
    ↓
情绪周期判断
    ↓
题材关键词识别
    ↓
题材强度评分
    ↓
资金强度评分
    ↓
龙虎榜匹配与加减分
    ↓
风控过滤与降级
    ↓
BUY / HOLD / AVOID 规则信号
    ↓
AI Berkshire 二次风控候选导出
    ↓
报告、CSV、JSON 日志
    ↓
历史信号回测摘要
```

## 模块

### `stock_engine.py`

主引擎，负责：

- 获取行情数据
- 计算情绪周期
- 识别题材
- 生成基础规则信号
- 接入龙虎榜确认
- 输出 Markdown / CSV / JSON
- 汇总历史信号回测摘要

### `dragon_tiger.py`

龙虎榜模块，负责：

- 调用 `ak.stock_lhb_detail_em`
- 标准化股票代码
- 将龙虎榜数据匹配到信号池
- 生成 `强确认 / 弱确认 / 未上榜 / 弱分歧 / 强分歧`
- 输出净买额、买入额、卖出额、上榜原因和解读

### `backtest.py`

回测模块，负责：

- 读取 `data/signals_YYYY-MM-DD.csv`
- 调用 `ak.stock_zh_a_hist`
- 统计 1/3/5 个交易日收益
- 输出胜率、平均收益、中位收益
- 输出分信号、分情绪、分龙虎榜、分题材、分风控结论的统计
- 样本不足时返回 `null`，不伪造胜率

### `risk_control.py`

风控模块，负责识别并降级：

- ST/退市风险
- 北交所/流动性结构差异
- 成交额不足
- 涨幅过热
- 换手过热
- 龙虎榜分歧
- 单一题材过度集中

### `theme_strength.py`

题材强度模块，按题材股票数、平均涨幅、接近涨停数量和成交额生成强度分。

### `ai_berkshire_gate.py`

AI Berkshire 交接模块，负责导出 Top 20 候选清单。该模块不直接调用 AI Berkshire skill，只生成待评估文件。

### `scripts/run.sh`

标准运行入口，负责：

- 切换到项目目录
- 使用项目虚拟环境里的 Python
- 将运行日志追加到 `logs/cron.log`

## 评分与信号

基础评分项：

- 成交额
- 涨跌幅
- 换手率
- 量比
- 封板资金
- 连板数
- 题材命中
- 情绪周期
- 龙虎榜确认
- 风控标签
- 题材强度

信号规则：

- `BUY`：强规则分数 + 合适情绪周期 + 非强分歧
- `HOLD`：满足入选阈值但不满足 BUY
- `AVOID`：分数不足或被风险因素压低

注意：`BUY` 是规则标签，不是买入建议。

## 自动化

推荐 Codex cron 三段运行：

- 09:00：开盘前 / 早盘信号
- 11:30：午间修正
- 15:00：收盘确认

每次自动运行必须回传：

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

## 可扩展点

- 游资席位标签库
- AI Berkshire 二次风控
- 板块强度
- 更严格的回测框架
- 企业微信 / 邮件推送
- 参数实验与版本化
