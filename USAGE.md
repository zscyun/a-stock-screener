# 📈 菜菜选股器 v1.0.5 — 使用手册

> A股智能筛选工具 | 混合打分模型 + 安全追涨模式  
> 安装即用，零配置（依赖已内置）

---

## 🔧 五大核心功能

| 子命令 | 用途 | 一句话说明 |
|--------|------|-----------|
| `screen` | **盘前选股** | 从动态热门池筛选 Top N 优质标的（默认） |
| `analyze` | **个股深度分析** | 指定代码，输出估值+技术面+收益追踪+综合评级 |
| `backtest` | **历史回测** | 验证打分模型信号的历史表现（夏普/回撤/胜率） |
| `discover` | **动态发现新标的** | 通过 akshare 三源实时抓取热门股更新池子 |
| `maintain` | **池子健康度维护** | 体检+清理低活标的+报告（v5.0） |

---

## 📊 场景化使用指南

### 1️⃣ 每日盘前选股（最常用）

```bash
# 基础用法 — 筛选 Top 15 + 完整分析卡
python3 stock_screen.py screen --limit 15

# 🔥 安全追涨模式 — 标注🟢🟡🔴风险等级，避免追高
python3 stock_screen.py screen --limit 15 --chase-mode

# 📈 趋势优先（捕捉动量股）— 价值:趋势=3:7
python3 stock_screen.py screen --limit 10 --ratio "3:7"

# 💰 深度价值挖掘 — 价值:趋势=7:3
python3 stock_screen.py screen --limit 10 --ratio "7:3"

# 📄 保存报告到文件（同时输出控制台）
python3 stock_screen.py screen --limit 15 -o reports/daily-report.txt
```

### 2️⃣ 个股深度分析

```bash
# 🔍 分析单只股票
python3 stock_screen.py analyze --codes 600519

# 📋 批量分析多只（逗号分隔）
python3 stock_screen.py analyze --codes 600519,002594,300750

# 🔍 启用 Exa 板块热度搜索（更准确但稍慢）
python3 stock_screen.py analyze --codes 600519 --enable-exa

# ⚡ 跳过估值查询（更快，仅技术面+实时行情）
python3 stock_screen.py analyze --codes 600519,002594 --no-valuation
```

### 3️⃣ 历史回测验证

```bash
# 📊 默认回测近一年、阈值6分触发买入信号
python3 stock_screen.py backtest --codes 600519

# ⏱️ 自定义天数+阈值
python3 stock_screen.py backtest --codes 600519,300750 --days 180 --threshold 4.0

# 📤 JSON 格式输出（适合程序处理）
python3 stock_screen.py backtest --codes 600519 --format json
```

### 4️⃣ 池子维护与发现

```bash
# 🔍 手动触发动态发现（刷新热门股池）
python3 stock_screen.py discover --max-discover 20

# 🏥 池子健康度体检 + 清理低活标的
python3 stock_screen.py maintain --force-refresh
```

---

## 🎨 输出模式对比

| 参数 | 说明 | 适用场景 |
|------|------|---------|
| （默认） | 控制台打印精美表格+分析卡 | 日常查看 |
| `--format json` | JSON 结构化输出 | API/程序对接 |
| `-o reports/file.txt` | 同时保存文件+控制台 | 存档/发邮件 |

---

## ⚙️ 高级参数（按需使用）

### `--ratio "VALUE:TREND"` — 动态权重调节

```bash
# 📈 趋势优先（高成长、动量股排名上升，PE容忍度提高）
python3 stock_screen.py screen --limit 10 --ratio "3:7"

# 💰 价值优先（深度价值挖掘，低估值+高ROE优先）
python3 stock_screen.py screen --limit 10 --ratio "7:3"
```

### `--weights '{"因子":权重}'` — 自定义因子权重

```bash
# 🛡️ 提高 PE 权重、降低 PEG 权重（保守型）
python3 stock_screen.py screen --weights '{"valuation_pe":2.5,"peg":0.5}'
```

### `--enable-exa` — 启用板块热度搜索

```bash
# 🔍 默认关闭保性能，开启后板块热度因子更准确
python3 stock_screen.py analyze --codes 600519 --enable-exa
```

---

## 📈 打分模型速查

### 价值因子组 (7个) — 评估基本面质量

| 因子 | 默认权重 | 说明 |
|------|---------|------|
| `valuation_pe` | 1.5 | PE(TTM) 合理区间得分 |
| `valuation_pb` | 1.0 | PB 估值水平 |
| `peg` | 1.0 | PEG < 1 加分（成长性价比） |
| `roe` | 1.5 | ROE 越高越好 |
| `margins` | 1.0 | 毛利率 + 净利率综合 |
| `cashflow` | 0.8 | 每股经营现金流为正 |
| `health` | 0.7 | 负债率健康、流动/速动比率好 |

### 趋势因子组 (6个) — 评估动量与上车空间

| 因子 | 默认权重 | 说明 |
|------|---------|------|
| `consec_up_days` | 1.2 | K线连续上涨天数(3-5天最佳) |
| `volume_surge` | 1.0 | 今日量 vs 20日均量(温和放量最佳) |
| `ma_alignment` | 1.2 | MA多头排列程度 |
| `sector_heat` | 0.8 | 板块热度(Exa搜索新闻情绪) |
| `limit_up_risk` | 1.5 | 🆕 v1.0.4: 涨停风险因子（连续涨停扣分） |
| `buyability` | 1.2 | 🆕 v1.0.4: 可买入性因子（建仓空间评估） |

### ⚠️ v1.0.5 升级 (2026-05-12)
- **保守型组合自动排除🔴标的** — 只选🟢可追
- **进取型优先排🟢、降权🔴** — `_chase_sort_key` 排序
- **_is_toxic 门槛收紧** — ROE从2%→3%, PE>500壳股排除, 毛利率从5%→8%
- **策略文案差异化** — 🟡/🔴不再全是"突破买入"

---

## 🔍 安全追涨模式详解 (`--chase-mode`)

### 5维风险评估

| 维度 | 🟢加分条件 | 🔴扣分条件 |
|------|-----------|-----------|
| **连续涨停次数** | ≤1板（首次启动）→ +0.2 | ≥3板（高潮期）→ -0.4 |
| **RSI超买程度** | <60（未超买）→ +0.15 | >85（极端情绪）→ -0.2 |
| **成交量健康度** | 1.2-3.5x均量 → +0.15 | >5x爆量 → -0.2 |
| **MACD状态** | 金叉延续中 → +0.1 | 死叉 → -0.2 |
| **K线形态** | 三连阳（趋势健康）→ +0.05 | 冲高回落（短顶信号）→ -0.1 |

### 三级判定标准

```
风险分 ≥ 0.6 → 🟢可追     （突破买入/回踩MA5介入）
0.3 ≤ 风险分 < 0.6 → 🟡谨慎  （等RSI回调至75以下 / 等回踩均线）
风险分 < 0.3 → 🔴别碰    （高潮期，建议换标的）
```

### 输出示例

```
#       代码 名称            价格    涨跌   得分 | 追涨     策略           | ...
--------------------------------------------------------------------------------
1   601868 中国能建     ¥  3.32 🟢 2.1% 6.64 | 🟢可追    突破买入/回踩MA5   | ...
2   601991 大唐发电     ¥  6.70 🟢10.0% 6.03 | 🔴别碰    高潮期，建议换标的   | ...
```

---

## ⏰ 日常使用流程推荐

```
⏰ 每日盘前（约8:30-9:15）
│
├─ ① python3 stock_screen.py screen --limit 15 --chase-mode
│   → 查看 Top 列表 + 🟢🟡🔴追涨评级
│   → 🟢标的可直接上车，🔴的等回调或换标的
│
├─ ② python3 stock_screen.py analyze --codes [看好的2-3只]
│   → 深度分析估值+技术面+操作价位
│
└─ ③ (可选) backtest --codes [候选股] --days 90
    → 验证近三个月回测信号，确认模型有效性
```

---

## 📁 文件结构

```
a-stock-combo/
├── SKILL.md              # Skill 定义（OpenClaw 自动加载）
├── USAGE.md              # ← 本使用手册
├── scripts/
│   ├── stock_screen.py   # 主程序（筛选+分析+回测+维护）
│   └── tushare_compat.py # TuShare 兼容层
├── reports/              # 生成的报告文件（不纳入 git）
└── hot_pool_state.json   # 池子状态持久化（不纳入 git）
```

---

## 🔗 相关链接

- **GitHub**: https://github.com/zscyun/a-stock-screener
- **OpenClaw Skill Registry**: https://clawhub.ai
- **依赖说明**: TuShare（实时行情+K线） + AkShare（热门池发现+估值数据）

---

*菜菜选股器 v1.0.5 | 🥬 楹楹校校家的电子精灵维护*
