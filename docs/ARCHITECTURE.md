# 架构说明

## 目标

系统目标不是预测股票，也不是自动交易，而是把 A股短线复盘流程固化为可重复运行、可审计、可回测的规则信号系统。

核心原则：

- 数据先行：所有结论必须来自已抓取的数据或明确标注为规则判断。
- 风控优先：情绪高潮、龙虎榜分歧、回测样本不足时不输出强结论。
- 可审计：每次运行必须保存 Markdown 报告、CSV 明细、JSON 摘要日志和 Run Card。
- 不夸大：没有 AI Berkshire 调用时，不声称 AI Berkshire 已参与评分。

## 数据流

```text
数据源注册表
    ↓
涨停池 / 全市场行情 / Sina / 本地快照 fallback
    ↓
数据质量校验与 warning
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
资金流匹配与加减分
    ↓
风控过滤与降级
    ↓
BUY / HOLD / AVOID 规则信号
    ↓
AI Berkshire 二次风控候选导出
    ↓
AI Berkshire 规则化四角色复核
    ↓
A / B / C / D 建议层与风险预算
    ↓
报告、CSV、JSON 日志
    ↓
Run Card / Hypothesis Registry
    ↓
历史信号回测与统计验证
```

## 模块

### `data_sources.py`

数据源注册表，负责：

- 依次尝试 `stock_zt_pool_em`、`stock_zh_a_spot_em`、`stock_zh_a_spot`、本地历史信号快照
- 校验成交额、涨跌幅、价格、代码字段可用性
- 输出结构化 warning，避免接口失败被静默吞掉

### `stock_engine.py`

主引擎，负责：

- 获取行情数据
- 计算情绪周期
- 识别题材
- 生成基础规则信号
- 接入龙虎榜确认
- 接入资金流确认
- 输出 Markdown / CSV / JSON
- 输出 Run Card
- 登记 Hypothesis Registry
- 汇总历史信号回测摘要

### `dragon_tiger.py`

龙虎榜模块，负责：

- 调用 `ak.stock_lhb_detail_em`
- 标准化股票代码
- 将龙虎榜数据匹配到信号池
- 生成 `强确认 / 弱确认 / 未上榜 / 弱分歧 / 强分歧`
- 输出净买额、买入额、卖出额、上榜原因和解读

### `fund_flow.py`

资金流模块，负责：

- 调用 AkShare 个股资金流接口
- 解析 `万 / 亿` 中文金额单位
- 匹配信号池股票代码
- 生成 `强确认 / 弱确认 / 未匹配 / 强分歧`
- 对规则分数做小幅加减分

### `backtest.py`

回测模块，负责：

- 读取 `data/signals_YYYY-MM-DD.csv`
- 调用 `ak.stock_zh_a_hist`
- 统计 1/3/5 个交易日收益
- 输出胜率、平均收益、中位收益
- 输出分信号、分情绪、分龙虎榜、分题材、分风控结论的统计
- 输出分 AI Berkshire 复核、分建议等级的统计
- 样本不足时返回 `null`，不伪造胜率
- 同步输出 `backtest_validation_YYYY-MM-DD.json`

### `validation.py`

统计验证模块，负责：

- 对 1/3/5 日收益样本做最小样本门槛判断
- 样本不足时输出 `insufficient_sample` 或 `no_sample`
- 样本足够时输出 bootstrap 均值置信区间

### `run_card.py`

运行卡模块，负责记录每次运行的摘要、warning、artifact 路径和 sha256。

### `hypothesis_registry.py`

假设注册表模块，负责把每日运行挂到固定研究假设下，保留策略版本、run card 路径和核心指标。


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

AI Berkshire 交接模块，负责导出 Top 20 候选清单。该模块不直接调用远端 AI Berkshire skill，而是把候选送入本地规则化复核队列。

### `ai_berkshire_review.py`

AI Berkshire 规则化二次风控模块，使用短线、财务、生意、风险四个角色输出：

- `AI_PASS`
- `AI_WATCH`
- `AI_VETO`

该模块借鉴 AI Berkshire 的质量筛选、新闻/风险脉搏、财务校验思想，但不是完整远端多 Agent 投研。

### `advice_engine.py`

建议层模块，综合原始信号、基础风控、AI Berkshire 复核、回测样本和情绪周期，生成 `A / B / C / D` 等级、触发条件、止损价、目标价和风险预算。

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
- 资金流确认
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
- fund_flow_matched_count / fund_flow_positive_count / fund_flow_negative_count
- backtest_tested_rows
- backtest_win_rate_1d
- backtest_validation_status_1d
- risk_pass_count / risk_watch_count / risk_veto_count
- top_theme / top_theme_strength
- ai_candidates_path / ai_berkshire_status
- ai_review_path / ai_pass_count / ai_watch_count / ai_veto_count
- advice_path / advice_a_count / advice_b_count / advice_c_count / advice_d_count
- run_card_json_path
- hypothesis_registry_path / strategy_version

## 可扩展点

- 游资席位标签库
- 远端 AI Berkshire 多 Agent 复核写回
- 板块强度
- 更严格的回测框架
- 企业微信 / 邮件推送
- 参数实验与版本化
