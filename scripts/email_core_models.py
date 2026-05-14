#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screener Email Dispatch - Core Data Models

分层架构核心模块：数据类 + 报告解析器
按爸比的设计：数据源 → [读取器] → [数据对象] → [输出器]
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ──────────────────────────────────────────────
# 1. StockData — 单只股票的所有信息
# ──────────────────────────────────────────────
@dataclass
class StockData:
    """一只股票的完整数据"""
    rank: int = 0
    code: str = ""
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    score: float = 0.0

    # 估值指标
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None  # 毛利率%
    ocfps: Optional[float] = None         # 每股现金流

    # 收益率追踪
    ret_1m: Optional[str] = None   # 保持原始字符串如 "+58.6%"
    ret_3m: Optional[str] = None
    ret_6m: Optional[str] = None
    ret_1y: Optional[str] = None

    # 追涨模式
    chase_risk: str = "🟢"        # 🟢/🟡/🔴
    strategy_text: str = ""       # 突破买入/分批建仓 / 等回踩MA5再介入

    # 深度分析卡字段（Panel 2）
    valuation_notes: str = ""     # PE解读+ROE+毛利率+现金流
    tech_notes: str = ""          # MA5偏离/RSI/MACD/BOLL
    operation_prices: dict = field(default_factory=dict)  # {buy, stop_loss, tp1, tp2}
    notes: str = ""               # 综合提示
    rating_text: str = ""         # ⭐⭐⭐ 综合评级

    # Panel 3: 投资组合配置字段
    portfolio_sector: str = ""      # 行业板块
    portfolio_type: str = "平衡"     # 价值/成长/平衡/投机
    portfolio_role: str = ""        # 角色标签：价值底仓/成长弹性等
    portfolio_weight: Optional[int] = None  # 建议仓位百分比
    in_conservative: bool = False   # 是否在保守型组合中

    @property
    def price_str(self) -> str:
        return f"¥{self.price:.2f}" if self.price else "¥0.00"

    @property
    def change_color_class(self) -> str:
        """涨跌颜色类"""
        return "up" if self.change_pct >= 0 else "down"


# ──────────────────────────────────────────────
# 2. ReportContext — 报告级别元数据
# ──────────────────────────────────────────────
@dataclass
class ReportContext:
    """报告的元信息"""
    report_date: str = ""          # "2026-05-13"
    version_str: str = ""         # "v1.0.2-8-g8e4128a"
    pool_size: int = 0            # 动态池大小
    title: str = "盘前选股分析报告"


# ──────────────────────────────────────────────
# 3. ReportReader — 从CLI文本报告解析数据
# ──────────────────────────────────────────────
class ReportReader:
    """
    读取器：从 screener CLI 输出的 .txt 报告中提取结构化数据。

    使用正则表达式逐行/逐块匹配，容错设计确保部分解析失败不崩溃。
    """

    def __init__(self):
        # Panel 1 总览表行正则 — 匹配:
        # 1   601868 中国能建     ¥  3.53 🟢 6.3% 6.81 | 🟢可追    突破买入/分批建仓    |  25.8 1.23   1.2 | +16.1% +38.3% +35.0% +46.6%
        self.summary_line_re = re.compile(
            r'^\s*([0-9]+)\s+'           # rank
            r'([0-9]{6})\s+'             # code
            r'([\u4e00-\u9fff\s]{2,8})\s+'  # name (中文字+空格)
            r'¥\s*([0-9.]+)\s*'          # price
            r'[🟢🔴]?\s*([+-]?[0-9.]+)%\s*'  # change_pct
            r'([0-9.]+)\s*\|'            # score
            r'\s*(🟢|🟡|🔴)([\u4e00-\u9fff]*)\s+'  # chase_risk + label
            r'(.+?)\s*\|\s*'            # strategy_text
            r'([0-9.\-]+)\s+([0-9.\-]+)\s+([0-9.\-]+)'  # PE PB ROE
        )
        
        # 收益率正则 — 匹配行尾的 +16.1% +38.3% +35.0% +46.6%
        self.ret_re = re.compile(
            r'\|\s*([+-]?[\d.]+%)\s+([+-]?[\d.]+%)\s+([+-]?[\d.]+%)\s+([+-]?[\d.]+%)'
        )

        # Report header — 提取日期和版本
        self.header_date_re = re.compile(r'([0-9]{4}-[0-9]{2}-[0-9]{2})')
        self.header_version_re = re.compile(r'\|(.*?)统一打分规则', re.DOTALL)
        self.pool_size_re = re.compile(r'动态池([0-9]+)只')

    def parse_report(self, filepath: str) -> tuple:
        """
        解析报告文件，返回 (ReportContext, List[StockData])

        Args:
            filepath: .txt 报告文件路径
        Returns:
            (ReportContext, [StockData, ...])
        """
        print(f"[ReportReader] 读取报告: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # ── Step 1: 提取 ReportContext ──
        context = self._parse_context(content)

        # ── Step 2: 逐行解析 Panel 1 (总览表) ──
        stocks = self._parse_summary_lines(content)

        if not stocks:
            print("[ReportReader] ⚠️ 未能从总览表中提取股票数据")

        # ── Step 3: 尝试解析 Panel 2 (深度分析卡) 补充字段 ──
        if stocks:
            self._enrich_from_detail_cards(content, stocks)

        print(f"[ReportReader] ✅ 解析完成: {len(stocks)} 只股票")
        return context, stocks

    def _parse_context(self, content: str) -> ReportContext:
        """提取报告元数据"""
        ctx = ReportContext()

        # 日期
        date_match = self.header_date_re.search(content)
        if date_match:
            ctx.report_date = date_match.group(1)

        # 版本 (尝试从 header 区域提取)
        version_block = content[:500]  # 只在头部找
        vmatch = re.search(r'(v[\d.\w-]+?)\s*统一打分', version_block)
        if vmatch:
            ctx.version_str = vmatch.group(1)

        # 池子大小
        pool_match = self.pool_size_re.search(content)
        if pool_match:
            try:
                ctx.pool_size = int(pool_match.group(1))
            except ValueError:
                pass

        return ctx

    def _parse_summary_lines(self, content: str) -> List[StockData]:
        """从 Panel 1 总览表逐行提取股票数据"""
        stocks = []

        for line in content.split('\n'):
            m = self.summary_line_re.match(line)
            if not m:
                continue

            try:
                stock = StockData(
                    rank=int(m.group(1)),
                    code=m.group(2),
                    name=m.group(3).strip(),
                    price=float(m.group(4)),
                    change_pct=float(m.group(5)),
                    score=float(m.group(6)),
                    chase_risk=m.group(7),
                )

                # 追涨标签文本 (可追/谨慎/别碰)
                chase_label = m.group(8).strip()
                if chase_label:
                    stock.strategy_text = chase_label

                # 策略文本
                strategy_raw = m.group(9).strip()
                if strategy_raw and not stock.strategy_text:
                    stock.strategy_text = strategy_raw

                # PE/PB/ROE
                try:
                    stock.pe = float(m.group(10))
                except (ValueError, IndexError):
                    pass
                try:
                    stock.pb = float(m.group(11))
                except (ValueError, IndexError):
                    pass
                try:
                    stock.roe = float(m.group(12))
                except (ValueError, IndexError):
                    pass

                # 收益率追踪 — 从行尾提取 +16.1% +38.3% +35.0% +46.6%
                ret_match = self.ret_re.search(line)
                if ret_match:
                    stock.ret_1m = ret_match.group(1)
                    stock.ret_3m = ret_match.group(2)
                    stock.ret_6m = ret_match.group(3)
                    stock.ret_1y = ret_match.group(4)

                stocks.append(stock)

            except Exception as e:
                print(f"[ReportReader] ⚠️ 行解析失败: {line[:50]}... ({e})")
                continue

        return stocks

    def _enrich_from_detail_cards(self, content: str, stocks: List[StockData]):
        """从 Panel 2 深度分析卡中提取估值/技术面/操作价位等补充字段"""
        # 按股票代码分割卡片区域
        for stock in stocks:
            card_block = self._extract_card_for_code(content, stock.code)
            if not card_block:
                continue

            # 提取技术面行
            tech_match = re.search(r'🔧\s*技术[^\n:]*:\s*(.+)', card_block)
            if tech_match:
                stock.tech_notes = tech_match.group(1).strip()

            # 提取操作价位
            buy_match = re.search(r'买入参考[价]?:\s*[¥￥]\s*([\d.]+)', card_block)
            stop_match = re.search(r'止损[价]?:\s*[¥￥]\s*([\d.]+)', card_block)
            tp1_match = re.search(r'止盈目标[一1]:?\s*[¥￥]\s*([\d.]+)', card_block)
            tp2_match = re.search(r'止盈目标[二2]:?\s*[¥￥]\s*([\d.]+)', card_block)

            if buy_match:
                stock.operation_prices['buy'] = f"¥{buy_match.group(1)}"
            if stop_match:
                stock.operation_prices['stop_loss'] = f"¥{stop_match.group(1)}"
            if tp1_match:
                stock.operation_prices['tp1'] = f"¥{tp1_match.group(1)}"
            if tp2_match:
                stock.operation_prices['tp2'] = f"¥{tp2_match.group(1)}"

            # 提取综合评级
            rating_match = re.search(r'(⭐+.*?)\s*$', card_block, re.MULTILINE)
            if rating_match:
                stock.rating_text = rating_match.group(1).strip()

            # 提取毛利率
            gm_match = re.search(r'毛利率[=:](.+?)%', card_block)
            if gm_match:
                try:
                    stock.gross_margin = float(gm_match.group(1))
                except ValueError:
                    pass

            # 提取每股现金流
            ocfps_match = re.search(r'每股现金流[=:]([+-]?[\d.]+)', card_block)
            if ocfps_match:
                try:
                    stock.ocfps = float(ocfps_match.group(1))
                except ValueError:
                    pass

    def _extract_card_for_code(self, content: str, code: str) -> Optional[str]:
        """提取某只股票对应的深度分析卡文本块
        
        修复：之前正则会匹配到第一张卡片就停止，现在精确匹配目标代码的标题行。
        """
        # 精确匹配包含该代码的卡片标题行
        title_pattern = rf'📊\s*Top\d+\.\s*.+?\({code}\)\s*\|'
        m = re.search(title_pattern, content)
        if not m:
            return None
        start = m.start()
        # 找到下一个卡片标题或报告结尾
        next_card = re.search(rf'\n📊\s*Top\d+\.\s*', content[start+1:])
        end = start + 1 + next_card.start() if next_card else len(content)
        return content[start:end].strip()


# ──────────────────────────────────────────────
# 快速测试：直接运行本文件时解析今天的报告
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys

    # 自动定位 reports 目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.join(script_dir, '..', '..', '..')
    reports_dir = os.path.join(workspace_root, 'reports')

    # 找今天的报告
    from datetime import date
    today_file = os.path.join(reports_dir, f"daily-report-{date.today()}.txt")

    if not os.path.exists(today_file):
        print(f"[test] 未找到今天的报告: {today_file}")
        sys.exit(1)

    reader = ReportReader()
    context, stocks = reader.parse_report(today_file)

    # 打印摘要
    print(f"\n=== 解析结果 ===")
    print(f"日期: {context.report_date}")
    print(f"版本: {context.version_str}")
    print(f"池子大小: {context.pool_size}")
    print(f"股票数量: {len(stocks)}")

    for s in stocks[:5]:
        print(f"  #{s.rank} {s.code} {s.name} ¥{s.price:.2f} ({s.change_pct:+.1f}%) "
              f"score={s.score} chase={s.chase_risk} pe={s.pe}")
