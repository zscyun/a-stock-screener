---
name: a-stock-combo
description: 综合A股分析技能，结合TuShare实时行情 + AkShare多源数据，提供快速且深度的个股分析能力。支持快速模式和深度联动模式（+Exa新闻 + web_fetch财报）。适用于A股查询、财报拆解、估值分析和交易观察等场景。
version: 0.9.0
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

## 🎯 选股推荐（轻量版）⭐ NEW

基于预定义30只各板块龙头股的实时数据做快速筛选，支持多因子打分排序。

### 用法

```bash
# 从热门股池筛选 Top N
python scripts/stock_screen.py screen --limit 8

# 🔥 先通过 Exa 动态发现新标的再筛选（突破30只限制）
python scripts/stock_screen.py screen --limit 10 --discover

# 纯发现模式：只看 Exa 发现了什么新热门股
python scripts/stock_screen.py discover --max-discover 15

# 按涨幅范围筛选（默认 -2% ~ 15%）
python scripts/stock_screen.py screen --limit 5 --min-change 2.0 --max-change 7.0

# 分析指定股票代码列表
python scripts/stock_screen.py analyze --codes "600519,300750,688256"

# JSON 输出（给 LLM 用）
python scripts/stock_screen.py screen --limit 5 --format json
```

### 🔍 Exa 动态发现（NEW v1.3）
- `--discover` 标志：在筛选前先调用 Exa 搜索近期 A 股热门榜单，自动提取名称+代码对并入池
- `discover` 子命令：纯发现模式，直接输出新发现的标的列表
- 解析策略：从财经资讯原文中提取"股票名+6位代码"格式（如 "圣阳股份002580"），无需额外网络请求

### 筛选因子
| 因子 | 默认值 | 说明 |
|------|--------|------|
| 涨幅范围 | 2%~7% | 强势但不追高 |
| PE上限 | <50 | 排除极端估值（数据可用时） |
| 成交额 | >5亿 | 流动性筛选 |
| 综合打分 | - | 涨幅适中+PE低+成交活跃 → 高分优先 |

### 预定义热门股池（30只，覆盖7大板块）
- **科技/AI/芯片**: 中芯国际、寒武纪-U、立讯精密、北方华创
- **新能源/电池**: 宁德时代、比亚迪、隆基绿能
- **消费/白酒**: 贵州茅台、五粮液、山西汾酒
- **金融**: 中国平安、招商银行、中国建筑
- **医药/生物**: 恒瑞医药、迈瑞医疗、药明康德
- **高端制造**: 紫金矿业、荣盛石化、海螺水泥

### ⚠️ 局限
- 默认覆盖30只预定义标的，**使用 `--discover` 可动态扩展至40+只**
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

# ── 选股筛选 v4 — 混合打分模型 ──
# 默认混合模式 (价值6:趋势4)
python scripts/stock_screen.py screen --limit 8
python scripts/stock_screen.py analyze --codes "600519,300750"

# 自定义比例（如5:5均势、7:3偏价值）
python scripts/stock_screen.py screen --mode hybrid --ratio "5:5" --limit 8
python scripts/stock_screen.py screen --mode hybrid --ratio "7:3" --limit 8

# 纯价值模式（适合长期投资筛选）
python scripts/stock_screen.py screen --mode value --limit 8

# 纯趋势模式（适合短线交易观察）
python scripts/stock_screen.py screen --mode trend --limit 8

# Exa动态发现 + 合并池筛选
python scripts/stock_screen.py discover --max-discover 10
python scripts/stock_screen.py screen --discover --limit 12
```

## 局限性

- TuShare免费接口标注"即将停止更新"，但当前仍可用
- AkShare东方财富源部分不通，依赖新浪/THS备用源  
- 不支持港股/美股 → 用 `china-stock-analysis` + Exa web抓取
- 理杏仁/同花顺等网站有反爬限制，web_fetch可能失败

---

## v4.0 Changelog (2026-05-07)

### 🔀 混合打分模型（核心升级）
- **三种模式**：`hybrid`（默认）、`value`、`trend`
- **可调比例**：通过 `--ratio "6:4"` 自定义价值/趋势权重（如 5:5、7:3）
- **负面新闻惩罚**：Exa搜索公司近期新闻，检测到造假/处罚/立案等严重事件时大幅扣分

### 📊 新增 5 个趋势因子
| 因子 | 说明 | 满分 |
|------|------|------|
| consec_up_days | K线连续上涨天数（3-5天最佳） | 1分 |
| volume_surge | 今日量 vs 20日均量（温和放量最佳） | 1分 |
| ma_alignment | MA多头排列程度（MA5>MA10>MA20） | 1分 |
| sector_heat | 板块热度（Exa搜索，预留扩展） | 1分 |

### 💎 价值因子组（7个，v3保留增强）
PE(TTM)、PB、PEG、ROE、毛利率+净利率、现金流、财务健康度

### ⚠️ Bug修复
- 负面新闻检查不再误判搜索关键词回显（改为先搜公司名+年份，再检查结果中是否有负面词）
