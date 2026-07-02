# GitHub 发布清单

## 发布前必须确认

- [ ] README 已说明项目用途、功能、快速开始和免责声明。
- [ ] `docs/ARCHITECTURE.md` 已说明架构和数据流。
- [ ] `docs/INSTALLATION.md` 已说明 Mac 安装步骤。
- [ ] `docs/USAGE.md` 已说明运行、查看报告和回测。
- [ ] `docs/OPERATIONS.md` 已说明 cron、日志和故障处理。
- [ ] `DISCLAIMER.md` 已说明非投资建议。
- [ ] `.gitignore` 已排除 `venv/`、`logs/`、`data/`、`__pycache__/`。
- [ ] 不提交本地敏感配置、API key、个人账户信息。
- [ ] 不提交本地运行数据，除非是脱敏后的示例数据。

## 许可证

GitHub 不强制要求许可证，但公开仓库最好明确许可证。

可选策略：

- **MIT**：最宽松，允许别人商用、修改、再分发，需保留版权和许可声明。
- **Apache-2.0**：宽松，额外包含专利授权条款。
- **GPL-3.0**：强 copyleft，衍生作品也需要开源。
- **All rights reserved**：不添加开源许可证，默认保留全部权利；别人不能明确合法复用。

如果你只是先公开展示，建议先不添加许可证，等确定开源策略后再添加。

## 建议仓库描述

```text
A股短线规则信号系统：基于 AkShare 的行情、龙虎榜和历史回测，生成 BUY/HOLD/AVOID 规则信号。仅用于研究和复盘，不构成投资建议。
```

## 建议 Topics

```text
akshare
a-share
stock-analysis
quant
backtest
dragon-tiger-list
codex
python
trading-research
```

## 首次提交建议

```bash
git init
git add README.md RUNBOOK.md SKILL.md requirements.txt stock_engine.py dragon_tiger.py backtest.py risk_control.py theme_strength.py ai_berkshire_gate.py ai_berkshire_review.py advice_engine.py scripts tests docs CONTRIBUTING.md DISCLAIMER.md .gitignore
git commit -m "feat: add A-share short-term signal system"
```

注意：不要 `git add .`，避免误提交本地日志、数据和虚拟环境。

如果你要把它作为 Codex skill 发布，`SKILL.md`、`RUNBOOK.md` 和 `docs/USAGE.md` 必须一起提交；否则别人只能看到代码，无法复用固定复盘流程。
