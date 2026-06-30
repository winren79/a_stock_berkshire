# 安装说明

## 环境要求

推荐环境：

- macOS
- Python 3.10+
- Git
- 网络可访问 AkShare 依赖的数据源

验证：

```bash
python3 --version
git --version
```

## 克隆项目

```bash
git clone <your-repo-url>
cd a_stock_berkshire
```

## 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

## 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 首次运行

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

## 验证输出

```bash
tail -n 80 logs/cron.log
sed -n '1,120p' logs/$(date '+%Y-%m-%d').md
ls -lh data/
```

成功运行后，应看到：

- `logs/YYYY-MM-DD.md`
- `logs/YYYY-MM-DD.log`
- `logs/cron.log`
- `data/signals_YYYY-MM-DD.csv`
- `data/backtest_YYYY-MM-DD.csv`，有历史可测信号时生成
- `data/backtest_groups_YYYY-MM-DD.csv`，有历史可测信号时生成
- `data/ai_berkshire_candidates_YYYY-MM-DD.csv`

注意：`data/` 和 `logs/` 是本地运行产物，默认不应提交到 GitHub。

## 常见问题

### AkShare 返回空表

涨停池接口可能为空。系统会回退到全市场实时行情。报告中的数据源会显示：

```text
akshare.stock_zh_a_spot_em(fallback: stock_zt_pool_em empty/unavailable)
```

### 当前没有回测胜率

当天信号没有未来收益，`backtest_tested_rows = 0` 是正常现象。只有积累历史信号后，回测才有意义。

### CSV 股票代码前导零消失

这是表格软件自动识别数字导致。原始 CSV 文件中的代码是 6 位字符串；使用 Pandas 读取时建议指定：

```python
pd.read_csv("data/signals_YYYY-MM-DD.csv", dtype={"代码": str})
```
