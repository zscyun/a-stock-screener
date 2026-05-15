# Screener 新架构设计文档 v2.0

## 🏗️ 核心问题

当前架构有个致命缺陷：**数据以文本文件形式在模块间流转**。
每次扩展新的输出方式，都要重新读一遍 `.txt` 报告再解析——这是典型的"数据在字符串里流转"反模式。

```
旧架构:
  screener → format_output() → TXT报告文件
                                ↓
  screener_email_dispatch.py → ReportReader.parse_report(TXT) → StockData列表 → HTMLEmailOutputter.render()
                                ↑ 每次新输出都要重新解析文本！数据有损！
```

## 🎯 目标架构

### 核心思想：**数据类直传 + 渲染器多态**

```
                    ┌──────────────────────────────┐
                    │      screener data layer       │
                    │                               │
                    │  get_stock_data()              │
                    │  compute_score()               │
                    │  screen_hot_pool()             │
                    │                               │
                    │     ↓ 产出结构化数据            │
                    └──────────┬─────────────────────┘
                               │
                     ScreeningResult (纯数据对象)
                          + List[ScreeningStock]
                               │
                               ▼
                  ┌─────────────────────────────┐
                  │   StockOutputRenderer (ABC)  │
                  │                             │
                  │ render_header(result) → str  │
                  │ render_body(result)   → str  │
                  │ render_footer(result) → str  │
                  │ render(result)       → str   │
                  └──┬─────────┬──────┬───────┬──┘
                     │         │      │       │
              ┌──────┘    ┌────┘  ┌───┘   ┌──┘
              ▼           ▼      ▼        ▼
         TextCLI     HTMLEmail  JSON    Markdown
         Exporter    Exporter  Exporter Exporter ...
```

### 数据流向

```
screener main():
    │
    ├─ Step 1: screen_hot_pool() → List[ScreeningStock]
    │              (直接产出结构化对象，不再走 Dict)
    │
    ├─ Step 2: 包装为 ScreeningResult
    │
    └─ Step 3: renderer = create_renderer(args.format)   # 'text' | 'html' | 'json' ...
                renderer.export(result, filepath=args.output)
```

## 📦 核心文件结构

```
scripts/
├── screening_result.py          ← ScreeningStock + ScreeningResult (数据层)
├── output_renderer_base.py      ← StockOutputRenderer ABC + 注册表工厂
├── renderer_text_cli.py         ← TextCLIExporter (终端文本报告，替代现format_output等)
├── renderer_html_email.py       ← HTMLEmailExporter (邮件HTML，从email_html_outputter迁移)
│
├── stock_screen.py              ← screener 主程序 (数据生产 + 渲染器调用)
│   └── main() → screen_hot_pool() → ScreeningResult → renderer.render()
```

## 📐 类设计细节

### ScreeningStock (dataclass)
单只股票的完整快照，包含所有字段：
- **基本信息**: code, name, price, change_pct, volume...
- **K线历史**: closes, volumes, recent_days
- **估值指标**: pe_ttm, pb, peg, pcf, ps
- **财务摘要**: roe, gross_margin, net_margin, debt_ratio, eps...
- **技术指标**: rsi14, macd_*, boll_*
- **打分**: screen_score, chase_info
- **组合元数据**: portfolio_sector, portfolio_type, portfolio_role, portfolio_weight
- **操作价位**: operation_prices

### ScreeningResult (dataclass)
一次筛选的完整结果集：
- metadata: timestamp, chase_mode, pool_size...
- stocks: List[ScreeningStock] (按得分降序)
- helper methods: top_stocks, summary_text()

### StockOutputRenderer (ABC)
抽象基类，定义输出协议：
```python
class StockOutputRenderer(ABC):
    FORMAT_ID: str = 'base'          # 格式标识符
    
    @abstractmethod
    def render_header(result) → str  # 标题/时间戳
    @abstractmethod  
    def render_body(result) → str    # 主体内容
    @abstractmethod
    def render_footer(result) → str  # 风险提示
    
    def render(result) → str         # 组合以上三者
    def export(result, filepath)     # 保存到文件

@register_renderer
class TextCLIExporter(StockOutputRenderer):
    FORMAT_ID = 'text'
    ...

@register_renderer  
class HTMLEmailExporter(StockOutputRenderer):
    FORMAT_ID = 'html'
    ...
```

## 🔄 迁移计划

### Phase 1 (当前): 数据类 + 抽象基类 ✅
- [x] `screening_result.py` — ScreeningStock + ScreeningResult
- [x] `output_renderer_base.py` — StockOutputRenderer ABC + 注册表工厂

### Phase 2: screener main() 适配
- [ ] screen_hot_pool() 返回 List[ScreeningStock] (替代 Dict)
- [ ] get_stock_data() → ScreeningStock.from_dict(data) 
- [ ] main() 中接入 renderer 选择逻辑: `--format text|html`

### Phase 3: 迁移现有输出到渲染器体系
- [ ] TextCLIExporter — 把 format_output/format_report_header 等迁入
- [ ] HTMLEmailExporter — 从 email_html_outputter.py 适配 (已有完整功能)

### Phase 4: 清理旧代码
- [ ] screener_email_dispatch.py → 简化为 "运行screener + html渲染" 的薄壳
- [ ] ReportReader + StockData → 废弃（数据不再走文本中间态）
- [ ] email_html_outputter/email_core_models → 合并入 renderer_html_email

### Phase 5: 扩展新输出格式 (按需)
- [ ] JSONExporter — API对接
- [ ] MarkdownRenderer — 文档导出
- [ ] CSVExporter — 数据分析导入

## ⚡ 关键设计决策

1. **数据类直传** — screener 直接产出 `ScreeningResult`，不再经过文本文件中转
2. **渲染器多态** — CLI参数 `--format text|html|json` 动态选择渲染器
3. **注册表工厂** — 新增格式只需写一个子类 + `@register_renderer`，无需改 main()
4. **零耦合** — screener 不关心输出长什么样；renderer 只读数据，不改数据
