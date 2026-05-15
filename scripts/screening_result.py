#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ScreeningResult & ScreeningStock — screener 产出的标准化数据结构

设计目标：
  - 替代所有中间文本报告，screener 直接产出结构化数据对象
  - 不依赖任何输出格式（CLI/HTML/JSON 都是下游消费者）
  - 包含单只股票的全部行情、估值、财务、技术面信息
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date, datetime


# ═══════════════════════════════════════════
# ScreeningStock — 单只股票的完整数据快照
# ═══════════════════════════════════════════

@dataclass
class ScreeningStock:
    """单只股票的所有 screener 产出信息"""

    # ── 基本信息 ──
    code: str = ''                    # 股票代码 (6位)
    name: str = ''                    # 股票名称
    price: float = 0.0               # 当前价格
    change: float = 0.0              # 涨跌额
    change_pct: float = 0.0          # 涨跌幅(%)
    open_price: float = 0.0          # 今日开盘
    high: float = 0.0                # 今日最高
    low: float = 0.0                 # 今日最低
    volume: int = 0                  # 成交量
    amount: float = 0.0              # 成交额

    # ── K线历史 (用于技术指标计算) ──
    kline_closes: List[float] = field(default_factory=list)   # 收盘价序列
    kline_volumes: List[float] = field(default_factory=list)  # 成交量序列
    recent_days: int = 0             # K线数据天数

    # ── 均线 ──
    ma5: Optional[float] = None      # 5日均线
    ma10: Optional[float] = None     # 10日均线
    ma20: Optional[float] = None     # 20日均线

    # ── 期间收益率 ──
    ret_1m: Optional[str] = None     # 近1月收益 (如 "+5.2%")
    ret_3m: Optional[str] = None     # 近3月收益
    ret_6m: Optional[str] = None     # 近半年收益
    ret_1y: Optional[str] = None     # 近1年收益
    ret_ytd: Optional[str] = None    # 年初至今

    # ── 估值指标 (akshare stock_value_em) ──
    pe_ttm: Optional[float] = None   # PE(TTM)
    pe_static: Optional[float] = None # PE(静)
    pb: Optional[float] = None       # PB
    peg: Optional[float] = None      # PEG
    pcf: Optional[float] = None      # PCF (市现率)
    ps: Optional[float] = None       # PS (市销率)

    # ── 财务摘要 (akshare stock_financial_abstract_ths) ──
    roe: Optional[float] = None           # ROE (%)
    gross_margin: Optional[float] = None  # 毛利率 (%)
    net_margin: Optional[float] = None    # 净利率 (%)
    debt_ratio: Optional[float] = None    # 资产负债率 (%)
    eps: Optional[float] = None           # EPS
    bvps: Optional[float] = None          # BVPS
    ocfps: Optional[float] = None         # OCFPS (每股经营现金流)
    current_ratio: Optional[float] = None # 流动比率
    quick_ratio: Optional[float] = None   # 速动比率

    # ── 技术指标 (本地计算) ──
    rsi14: Optional[float] = None         # RSI(14)
    macd_dif: Optional[float] = None      # MACD DIF
    macd_dea: Optional[float] = None      # MACD DEA
    macd_bar: Optional[float] = None      # MACD 柱
    boll_upper: Optional[float] = None    # BOLL 上轨
    boll_mid: Optional[float] = None      # BOLL 中轨
    boll_lower: Optional[float] = None    # BOLL 下轨
    boll_bw: Optional[float] = None       # BOLL BW

    # ── screener 打分 ──
    screen_score: float = 0.0             # 综合得分
    chase_info: Optional[Dict[str, Any]] = field(default=None)  # 追涨安全评估 (chase_mode时)

    # ── 组合配置元数据 (供 Panel 3 使用，可由渲染器或 screener 填充) ──
    portfolio_sector: str = ''            # 所属行业/板块
    portfolio_type: str = ''              # 价值/成长/平衡/投机
    portfolio_role: str = ''              # 核心/卫星/交易
    portfolio_weight: float = 0.0         # 建议仓位权重(%)
    in_conservative: bool = False         # 是否入选保守组合

    # ── 操作价位 (由 screener 计算或渲染器回填) ──
    operation_prices: Optional[Dict[str, str]] = field(default=None)
        # {'buy': '¥X.XX', 'stop_loss': '¥X.XX', 'tp1': '¥X.XX', 'tp2': '¥X.XX'}

    # ── 原始数据 (兜底，存放无法映射到上述字段的额外信息) ──
    raw: Dict[str, Any] = field(default_factory=dict)

    # ════════ 辅助方法 ════════

    @property
    def pe(self) -> Optional[float]:
        """优先返回 PE(TTM)，兜底静态PE"""
        return self.pe_ttm or self.pe_static

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScreeningStock':
        """从 screener 产出的 dict 创建 ScreeningStock 对象"""
        stock = cls()

        # ── 基本信息 (直接映射) ──
        direct_fields = [
            'code', 'name', 'price', 'change', 'change_pct',
            'open', 'high', 'low', 'volume', 'amount',
            'recent_days', 'ma5', 'ma10', 'screen_score', 'chase_info',
        ]
        field_map = {
            'open': 'open_price',
        }
        for f in direct_fields:
            if f in data:
                setattr(stock, field_map.get(f, f), data[f])

        # ── K线历史 ──
        stock.kline_closes = data.get('_kline_closes', []) or []
        stock.kline_volumes = data.get('_kline_volumes', []) or []

        # ── 期间收益率 (嵌套字典) ──
        pr = data.get('period_returns', {}) or {}
        stock.ret_1m = pr.get('近1月')
        stock.ret_3m = pr.get('近3月')
        stock.ret_6m = pr.get('近半年')
        stock.ret_1y = pr.get('近1年')
        stock.ret_ytd = pr.get('年初至今')

        # ── 估值指标 (直接映射) ──
        valuation_fields = ['pe_ttm', 'pe_static', 'pb', 'peg', 'pcf', 'ps']
        for f in valuation_fields:
            if f in data:
                setattr(stock, f, data[f])

        # ── 财务摘要 (直接映射) ──
        fa_fields = ['roe', 'gross_margin', 'net_margin', 'debt_ratio',
                     'eps', 'bvps', 'ocfps', 'current_ratio', 'quick_ratio']
        for f in fa_fields:
            if f in data:
                setattr(stock, f, data[f])

        # ── 技术指标 (直接映射) ──
        tech_fields = ['rsi14', 'macd_dif', 'macd_dea', 'macd_bar',
                       'boll_upper', 'boll_mid', 'boll_lower', 'boll_bw']
        for f in tech_fields:
            if f in data:
                setattr(stock, f, data[f])

        # ── 操作价位 (直接映射) ──
        stock.operation_prices = data.get('operation_prices')

        # ── 剩余字段放入 raw ──
        mapped_keys = set()
        for f in direct_fields + valuation_fields + fa_fields + tech_fields:
            mapped_keys.add(f)
        mapped_keys.update(['_kline_closes', '_kline_volumes', 'period_returns', 'operation_prices'])

        for k, v in data.items():
            if k not in mapped_keys:
                stock.raw[k] = v

        return stock


# ═══════════════════════════════════════════
# ScreeningResult — 一次筛选的完整结果集
# ═══════════════════════════════════════════

@dataclass
class ScreeningResult:
    """一次 screener 运行的完整产出"""

    # ── 元数据 ──
    timestamp: datetime = field(default_factory=datetime.now)
    chase_mode: bool = False           # 是否为安全追涨模式
    pool_size: int = 0                 # 动态池总大小
    persistent_count: int = 0          # 持久化池数量
    fresh_discovered: int = 0          # 本次新发现数量

    # ── 筛选参数 ──
    limit: int = 15                   # 返回上限
    min_change_pct: float = -2.0       # 最小涨跌幅
    max_change_pct: float = 15.0       # 最大涨跌幅
    use_exa: bool = False              # 是否启用Exa
    include_valuation: bool = True      # 是否包含估值

    # ── 股票列表 (按得分降序排列) ──
    stocks: List[ScreeningStock] = field(default_factory=list)

    # ── Exa 状态 ──
    exa_failed: bool = False           # Exa调用是否失败
    exa_failure_reason: str = ''       # 失败原因描述

    # ════════ 辅助方法 ════════

    @property
    def top_stocks(self) -> List[ScreeningStock]:
        """返回 Top N (N=limit)"""
        return self.stocks[:self.limit]

    @property
    def total_count(self) -> int:
        return len(self.stocks)

    def summary_text(self) -> str:
        """生成简要摘要文本"""
        return (f"筛选结果: {len(self.stocks)}只标的 | "
                f"池子: {self.pool_size}只(持久化{self.persistent_count}+新发现{self.fresh_discovered}) | "
                f"模式: {'追涨' if self.chase_mode else '标准'}")
