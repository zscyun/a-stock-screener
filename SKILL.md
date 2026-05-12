---
name: a-stock-combo
description: 综合A股分析技能，结合TuShare实时行情 + AkShare多源数据，提供快速且深度的个股分析能力。支持快速模式和深度联动模式（+Exa新闻 + web_fetch财报）。适用于A股查询、财报拆解、估值分析和交易观察等场景。
version: 1.0.3
metadata:
  openclaw:
    emoji: "📈"
    requires:
      bins:
        - python3
      pythonPackages:
        - tushare
        - akshare
        - pandas
---

# A股综合分析技能 (TuShare + AkShare + Exa联动)

## Prerequisites

| 依赖 | 必须？ | 说明 |
|------|--------|------|
| **Python 3.8+** | ✅ 必须 | Python 运行环境 |
| **tushare + akshare + pandas** | ✅ 必须 | pip install，OpenClaw 自动处理 |
| **TuShare Token** | ✅ 必须 | 免费注册获取（见下方） |
| **mcporter / Exa** | ⚠️ 可选 | 深度联动分析需要，无则降级为纯本地模式 |

### TuShare Token 设置（必做！）

```bash
# 1. 注册账号：https://tushare.pro/register
# 2. 获取个人 token（个人中心 → 接口TOKEN）
# 3. 设置环境变量或写入代码
echo 'export TUSHARE_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

> ⚠️ **没有 Token 会报错**：`Tushare Error: Invalid token`。注册免费，获取后设一次即可永久使用。

## Installation

### 方式一：ClawHub 一键安装（推荐）
```bash
clawhub install a-stock-combo --version 0.9.0
# OpenClaw 自动处理 python3 + pip install tushare akshare pandas
```

### 方式二：从 GitHub Clone
```bash
cd ~/.openclaw/workspace/skills/
git clone https://github.com/zscyun/a-stock-screener.git a-stock-combo
cd a-stock-combo && pip install -r requirements.txt
# 然后设置 TuShare Token（见上方 Prerequisites）
```

### 验证安装
```bash
python scripts/stock_screen.py analyze --codes "600519"
# 看到茅台的实时行情 + 技术指标 = ✅ 安装成功
```

## 快速开始

```bash
# 快速模式：实时行情 + K线 + 技术指标 + 财务摘要
python scripts/a_stock_cli.py analyze --code "600519"

# 自然语言查询（自动识别股票）
python scripts/a_stock_cli.py run --text "看看宁德时代估值"
```

## A股深度联动分析工作流 🚀 (25+指标全维度)

当用户请求A股深度分析时，按以下流程执行：

### Step 1: a-stock-combo CLI — 获取行情+技术面（秒回）

```bash
python scripts/a_stock_cli.py analyze --code "600519"
```

**输出**：实时行情 + K线数据(60日) + RSI/MACD/BOLL/KDJ/MA + THS财务摘要(102条)

### Step 2: Exa (agent-reach) — 多主题搜索（并行）

```bash
# Q1财报/最新业绩
mcporter call 'exa.web_search_exa' "query=XX股份 Q1 2026 财报"

# 主力资金 + 北向资金  
mcporter call 'exa.web_search_exa' "query=XX股份 主力资金 北向资金"

# 估值 + 股东结构
mcporter call 'exa.web_search_exa' "query=XX股份 PE PB 估值 前十大股东"

# 行业分析 + 竞争格局
mcporter call 'exa.web_search_exa' "query=XX股份 行业前景 竞争"

# 最新消息 / 风险因素
mcporter call 'exa.web_search_exa' "query=XX股份 风险 预警 减持"
```

### Step 3: web_fetch — 抓取财报详情/深度数据（如适用）

- 上海证券报/Q1报告 → 营收、利润、毛利率、现金流拆解
- 理杏仁/雪球 → 估值指标补充（PE/PB/PS/WACC）

### Step 4: 综合输出 — 25+指标结构化深度分析报告

**完整模板如下：**

```markdown
## 📊 {股票名称}({代码}) 综合分析

### 📈 实时行情 (TuShare)
| 指标 | 数值 | 变化 |
|------|------|------|
| 现价/收盘价 | ¥XXX.XX | +XX.XX (+X.XX%) 🔴/🟢 |
| 最高/最低 | XX / XX | - |
| 成交量/额 | XX万手 / XX亿 | - |

### 📊 技术指标 (本地计算) — 6项完整
- **均线系统**：MA5=XX, MA10=XX, MA20=XX → {多头/空头排列}
- **RSI(14)**：XX → {超买>70 / 正常30-70 / 超卖<30}
- **MACD**：DIF=XX, DEA=XX, HIST=XX → {金叉/死叉/收敛}
- **布林带**：上轨=XX, 中轨=XX, 下轨=XX → {位置判断}
- **KDJ_RSV**：XX → {超买>80 / 正常20-80 / 超卖<20}

### 📋 Q1/最新财报数据 — 8+核心指标
| 指标 | 本期 | 上期 | 同比变化 |
|------|------|------|---------|
| 营收 | XX亿 | XX亿 | +XX% |
| 归母净利润 | XX万/亿 | XX万/亿 | +XX%/扭亏 |
| 扣非净利润 | XX万 | — | — |
| 毛利率 | XX.XX% | XX.XX% | +XX个百分点 |
| ROE | X.XX% | X.XX% | — |
| EPS | ¥X.XX | ¥X.XX | — |

### 💰 估值指标 — 4项
| 指标 | 数值 | 行业对比 |
|------|------|---------|
| PE(TTM) | XXX倍 | {偏高/合理/偏低} |
| PB(LF) | X.XX倍 | - |
| PS(TTM) | X.XX倍 | - |
| PEG | X.XX (如可得) | — |

### 💸 现金流与负债 — 4项关键信号
| 指标 | 数值 | 变化 |
|------|------|------|
| 经营现金流净额 | XX亿(+/-) | {改善/恶化} |
| 投资现金流净额 | XX亿(-通常正常) | - |
| 资产负债率 | XX.XX% | +XX个百分点 |
| 短期借款变动 | ±XX% | {暴增/稳定/下降} |

### 🏢 股东结构 — 3项
- **前十大股东持股比例**：XX.XX% → {集中度高/适中/偏低}
- **股东户数**：X.XX万户（{增加=散户进场 / 减少=筹码集中}）
- **机构持仓动态**：{增持/减持/新进/退出}

### 📰 市场情绪与资金流向 — Exa新闻整合
#### ✅ 利好因素
| 事项 | 详情 |
|------|------|
| ... | ... |

#### ⚠️ 风险因素  
| 事项 | 详情 |
|------|------|
| ... | ... |

### 📊 行业分析 — (Exa补充)
- **所属行业**：XX板块/细分赛道
- **景气度**：{上行/震荡/下行} + 理由
- **竞争格局**：市场地位 + 主要对手

### 💡 AI投资建议
**建议：买入 / 持有 / 观望 / 卖出**
- 理由：...
- 操作策略：...（含止损位、目标价参考）  
- 风险提示：...
- 关键跟踪指标/时间节点：...
```

## 数据源分工

| 能力 | 快速模式 | 深度联动(25+) |
|------|---------|-------------|
| 实时行情（TuShare） | ✅ | ✅ |
| K线历史（新浪/AkShare） | ✅ | ✅ |  
| 技术指标（RSI/MACD/BOLL/KDJ/MA） | ✅ | ✅ |
| THS财务摘要(102条) | ✅ | ✅ |
| Exa新闻搜索（业绩/资金/估值） | ❌ | ✅ |
| web_fetch财报详情 | ❌ | ✅ |
| 分析师共识/评级补充 | ❌ | ✅ (Exa+web) |

## 🎯 选股推荐（轻量版）

基于全动态池的实时数据做快速筛选，支持多因子打分排序。无硬编码池子，每次运行自动发现优质候选。

### 用法

```bash
# 从热门股池筛选 Top N（默认混合模式：价值6:趋势4）
python scripts/stock_screen.py screen --limit 8

# 按涨幅范围筛选（默认 -2% ~ 15%）
python scripts/stock_screen.py screen --limit 5 --min-change 2.0 --max-change 7.0

# 分析指定股票代码列表
python scripts/stock_screen.py analyze --codes "600519,300750,688256"

# JSON 输出（给 LLM 用）
python scripts/stock_screen.py screen --limit 5 --format json
```

### 🔍 动态池子（v6+ 零硬编码）
- **三层发现源**：stock_hot_rank_em(热度) + stock_zt_pool_em(涨停) + stock_zh_a_spot_em(高涨幅兜底)
- **持久化记忆**：`hot_pool_state.json` 保存上次发现的优质池子，保证连续性
- **缓存机制**：估值+财务数据自动缓存（<1h），避免重复查询

### 筛选因子
| 因子 | 默认值 | 说明 |
|------|--------|------|
| 涨幅范围 | 2%~7% | 强势但不追高 |
| PE上限 | <50 | 排除极端估值（数据可用时） |
| 成交额 | >5亿 | 流动性筛选 |
| 综合打分 | - | 涨幅适中+PE低+成交活跃 → 高分优先 |

### ⚠️ 局限
- TuShare免费接口不返回PE/PB，需AkShare补充（当前部分不通）
- Exa搜索依赖 mcporter + 网络环境，断开时自动降级为纯本地筛选
- 推荐结果仅供参考，不构成投资建议

港股和美股**不经过此技能**，统一使用 `china-stock-analysis` workflow：
- Exa搜索 → web_fetch StockAnalysis.com → Barron's/TipRanks  
- 25+指标深度拆解（估值/现金流/股东结构/分析师共识）
- AI投资建议 + 风险提示

## CLI用法参考

```bash
# 实时行情（TuShare免费接口）  
python scripts/a_stock_cli.py fetch-realtime --code "600519"

# 财务+K线数据（AkShare新浪/THS源）
python scripts/a_stock_cli.py fetch-financials --code "300750"

# 综合报告（默认全量）
python scripts/a_stock_cli.py analyze --code "600519" --type full

# ── 选股筛选 v1.0.3 — Staleness 自动刷新 + Python 兼容修复 ──
# 基本用法
python scripts/stock_screen.py screen --limit 10
python scripts/stock_screen.py analyze --codes "600519,300750"

# 🆕 --ratio: 动态调整价值/趋势权重比（默认~6成价值/~3成趋势）
python scripts/stock_screen.py screen --limit 10 --ratio "3:7"   # 趋势优先
python scripts/stock_screen.py screen --limit 10 --ratio "7:3"   # 价值优先
python scripts/stock_screen.py analyze --codes "600519,300750" --ratio "1:2"  # 成长股友好

# 🆕 v5.0: 池子健康度维护（体检+清理+报告）
python scripts/stock_screen.py maintain                    # 基础体检
python scripts/stock_screen.py maintain --force-refresh   # 过时池子自动完整发现

# 启用Exa板块热度搜索（需mcporter配置，两种模式统一规则）
python scripts/stock_screen.py screen --enable-exa --limit 10
python scripts/stock_screen.py analyze --codes "600519" --enable-exa

# 跳过估值查询（更快，适合快速筛选）
python scripts/stock_screen.py screen --no-valuation --limit 10

# 自定义权重调整
python scripts/stock_screen.py screen --weights '{"valuation_pe":2.0}' --limit 8

# 💾 报告保存到文件（同时输出到控制台）
python scripts/stock_screen.py screen --limit 15 -o /reports/daily-report.txt
python scripts/stock_screen.py analyze --codes "600519,300750" -o /tmp/analysis.json --format json
```

## 局限性

- TuShare免费接口标注"即将停止更新"，但当前仍可用
- AkShare东方财富源部分不通，依赖新浪/THS备用源
- 不支持港股/美股 → 用 `china-stock-analysis` + Exa web抓取
- 理杏仁/同花顺等网站有反爬限制，web_fetch可能失败

## Troubleshooting

### ❌ `Tushare Error: Invalid token` / `token not found`
- **原因**：TuShare Token 未设置或过期
- **解决**：重新获取 Token → 更新环境变量 `TUSHARE_TOKEN`

### ❌ `ImportError: No module named 'akshare'` 等 pip 报错
```bash
cd ~/.openclaw/workspace/skills/a-stock-combo
pip install -r requirements.txt --upgrade
```

### ❌ AkShare 东方财富源网络不通（`stock_zh_a_spot_em` 超时）
- **原因**：部分地区的网络环境无法直接访问东方财富 API
- **解决**：代码已内置新浪/THS 备用源，会自动 fallback。如仍失败，检查防火墙或代理设置

### ❌ `pandas KeyError` / 负索引报错
- **原因**：旧版 pandas（<2.0）不支持 `.iloc[]`
- **解决**：`pip install 'pandas>=2.0.0' --upgrade`

### ❌ Exa/mcporter 调用失败
- **原因**：mcporter 未配置或 Exa API Key 无效
- **影响**：仅深度联动分析（Step 2）不可用，基本筛选功能正常
- **解决**：检查 `~/.openclaw/workspace/config/mcporter.json` 配置

### ❌ screener 结果全为"⚠️亏损/流动性风险"
- **原因**：L1 预筛缓存未建立（首次运行）
- **解决**：跑一次完整筛选后，FA_CACHE 会自动建立，后续质量提升

---

---

## 🆕 v1.0.3 Changelog (2026-05-12)

### 核心升级
| # | 功能 | 说明 |
|---|------|------|
| 1 | Staleness 自动刷新 | `screen_hot_pool` 增加池子老化检测，超阈值自动静默刷新（默认 24h） |
| 2 | Python 3.10 兼容修复 | tushare_compat.py f-string 转义符语法修正 |
| 3 | TODO/FIXME/HACK 清理 | 所有历史开发标记替换为版本注释 (v0.9+/v1.0.3+) |

### Bug Fix
- `tushare_compat.py`: f-string 内 `\n` 转义符在 Python<3.12 报错 → 提取为独立函数修复
- 注释中的 TODO #2/#3 标记全部清理，避免新用户困惑

---

## v0.9 Changelog (2026-05-11)

### 🎯 选股筛选（核心升级链）
| 版本 | 日期 | 功能 |
|------|------|------|
| v4.0 | 05-07 | 混合打分模型(hybrid/value/trend) + 可调比例 |
| v4.3 | 05-07 | 期间收益率集成打分（近1月/3月/半年/1年） |
| v6 | 05-08 | 全动态池子+零Exa依赖+三层发现源 |
| v8 | 05-08 | 收益率补齐+tushare静默+三面板输出 |
| **v0.9** | 05-09→11 | P1-P5全面升级（见下方） |

### ✅ P1-P5 全部完成

| # | 优先级 | 任务 | 说明 |
|---|--------|------|------|
| P1 | L1筛选 | 基本面预筛（排除亏损/高负债/低毛利） | 缓存驱动，渐进式生效 |
| P2 | Bug修复 | 毛利率"无数据"bug修复 + 键名对齐 | `gm_val` 引用修正 |
| P3 | 组合建议 | _classify_stock_type + _get_sector_name + 行业分散 | 保守型满3只+价值类筛选 |
| P4 | 技术面 | RSI/MACD/BOLL指标加入Panel + ROE阈值校准 | format_output双路径渲染 |
| P5 | backtest | 回测引擎（连续评分+MA排列+RSI因子，阈值可调） | `--threshold` CLI参数 |

### 📊 新增 4 个趋势因子
| 因子 | 说明 | 满分 |
|------|------|------|
| consec_up_days | K线连续上涨天数（3-5天最佳） | 1分 |
| volume_surge | 今日量 vs 20日均量（温和放量最佳） | 1分 |
| ma_alignment | MA多头排列程度（MA5>MA10>MA20） | 1分 |
| sector_heat | 板块热度（Exa搜索，预留扩展） | 1分 |

### 💎 价值因子组（7个，v3保留增强）
PE(TTM)、PB、PEG、ROE、毛利率+净利率、现金流、财务健康度

### ⚠️ Bug修复教训
- pandas Series 不支持原生负索引，必须用 `.iloc[]`
- import datetime 需在被引用的地方之前执行
- 打分阈值与因子权重必须匹配校准，否则信号全不触发

---

## 📊 盘前报告模板 v1.0 (2026-05-11)

### 标准输出格式（固化到代码）
每次 `screen` 命令自动输出以下三栏式报告：

**① 报告头部** — `format_report_header()`
- 时间戳 + git tag版本信息
- 筛选参数说明

**② Top列表** — `format_summary_table()`
| 列 | 内容 |
|---|------|
| PE/PB/ROE% | 核心估值指标 |
| 近1月/3月/半年/年 | 四个期间收益率（全部显示，不再只有"近一年"） |

**③ 深度分析卡** — `format_detailed_analysis(results, limit=10)`
- 📊 每只股票：估值解读框（PE/ROE/毛利率/现金流）+ 🔧技术面 + 📈收益追踪 + ⭐综合评级

### CLI输出示例
```
================================================================================
📈 盘前选股分析报告
⏰ 2026-05-11 20:28 | git describe --tags
================================================================================

#       代码 名称            价格    涨跌   得分 |    PE   PB  ROE% |    近1月    近3月    近半年    近1年
--------------------------------------------------------------------------------
1   601991 大唐发电     ¥  6.09 🟢 9.9% 6.88 |  14.0 3.06   7.3 | +58.6% +63.3% +60.9% +87.2%
...

🔍 Top N 个股深度分析 (估值解读框 + 🔧技术面 + 📈收益追踪 + ⭐综合评级)
```

### 📧 邮件报告分发 (v1.0.0)

**脚本**: `scripts/screener_email_dispatch.py`

**功能**: 将 screener 选股报告以精美HTML邮件形式发送到指定邮箱

**使用方式**:
```bash
# 直接运行发送盘前报告
python3 scripts/screener_email_dispatch.py

# 或结合 screener 命令（先筛选再发邮件）
python3 stock_screen.py screen --limit 15 && python3 scripts/screener_email_dispatch.py
```

**邮件模板设计**:
- 🟢 渐变绿色头部 - 大标题 + 日期/版本信息
- 📊 Panel 1: Top N总览表（斑马纹行、涨跌红绿配色、Top3金/银/铜背景）
- 🔍 Panel 2: 深度分析卡（彩色左边框、估值/技术面/收益追踪分色区块）
- 🎯 Panel 3: 组合建议表（保守型蓝色系 + 进取型橙色系）

**配置**:
- SMTP: smtp.qq.com:587 (TLS)
- 发件人/收件人在脚本中可配置
- HTML正文大小: ~48KB，附件: CLI原始输出文本(~22KB)

**扩展计划**: 
- [ ] 支持命令行参数指定报告类型（盘前/收盘/异动预警）
- [ ] 支持多收件人列表
- [ ] 支持自定义邮件主题模板