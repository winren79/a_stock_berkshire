# 贡献指南

欢迎提交改进，但本项目涉及金融数据和信号解释，贡献必须优先保证可验证性。

## 开发原则

- 不伪造数据。
- 不把规则信号写成投资建议。
- 不在样本不足时声称胜率。
- 不把未实现能力写进文档。
- 所有新增信号规则必须能在报告或 CSV 中解释来源。

## 本地开发

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

运行基础检查：

```bash
venv/bin/python -m py_compile stock_engine.py dragon_tiger.py backtest.py risk_control.py theme_strength.py ai_berkshire_gate.py tests/test_signal_modules.py
venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.test_signal_modules import (
    test_ai_berkshire_candidate_export,
    test_enrich_with_dragon_tiger_marks_positive_and_negative_matches,
    test_normalize_code_keeps_six_digits,
    test_risk_controls_veto_st_and_retired_names,
    test_theme_strength_scores_group_activity,
)

test_normalize_code_keeps_six_digits()
test_enrich_with_dragon_tiger_marks_positive_and_negative_matches()
test_risk_controls_veto_st_and_retired_names()
test_theme_strength_scores_group_activity()
with TemporaryDirectory() as d:
    test_ai_berkshire_candidate_export(Path(d))
print("logic tests passed")
PY
```

## 提交前检查

提交前请确认：

- 没有提交 `venv/`
- 没有提交 `logs/`
- 没有提交 `data/`
- README 与实际能力一致
- 如果改了信号规则，更新 `docs/ARCHITECTURE.md`
- 如果改了运行方式，更新 `docs/INSTALLATION.md` 和 `docs/OPERATIONS.md`

## Pull Request 说明建议

请说明：

- 改了什么
- 为什么改
- 用什么数据验证
- 是否影响 BUY / HOLD / AVOID 规则
- 是否影响 cron 自动任务
- 是否影响风控、题材强度、AI Berkshire 候选导出
