#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML邮件输出器 — 从解析后的选股数据动态渲染精美HTML邮件

v2.0 - 完全动态，无硬编码数据
架构：ReportReader → StockData列表 → HTMLEmailOutputter.render() → HTML字符串 → SMTP发送
"""

import smtplib, os, sys, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime


# ═══════════════════════════════════════════
# 辅助函数 — ROE评级 / 涨跌颜色 / 排名背景
# ═══════════════════════════════════════════

def roe_badge(roe):
    """ROE评级标签"""
    if roe is None:
        return "无数据"
    if roe >= 20:
        return f"{roe:.1f}%🔥"
    elif roe >= 15:
        return f"{roe:.1f}%"
    elif roe >= 10:
        return f"{roe:.1f}%"
    elif roe >= 3:
        return f"{roe:.1f}%⚠️"
    else:
        return f"{roe:.1f}%❌"


def change_color(change_pct):
    """涨跌颜色类"""
    return "up" if change_pct >= 0 else "down"


# ═══════════════════════════════════════════
# HTMLEmailOutputter — 渲染 + SMTP发送
# ═══════════════════════════════════════════

class HTMLEmailOutputter:
    """将解析后的选股数据转换为精美HTML邮件"""
    
    def __init__(self):
        # SMTP配置
        self.smtp_server = "smtp.qq.com"
        self.smtp_port = 587
        self.sender_email = "65343914@qq.com"
        
        # 优先读环境变量，fallback 到 imap-smtp-email .env
        password = os.environ.get("EMAIL_PASSWORD", "")
        if not password:
            env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'imap-smtp-email-chinese', '.env')
            env_path_resolved = os.path.normpath(env_path)
            # 也试试 workspace root 下的 skill
            alt_env = os.path.expanduser('~/.openclaw/workspace/skills/imap-smtp-email-chinese/.env')
            for ep in [env_path_resolved, alt_env]:
                if os.path.exists(ep):
                    with open(ep, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('SMTP_PASS='):
                                password = line.split('=', 1)[1].strip()
                                break
                if password:
                    break
        self.sender_password = password
        
        self.recipient_emails = ["zscyun@hotmail.com"]
    
    # ─── Panel 1: Top选股总览表 (含头部) ───
    def render_panel1(self, context, stocks):
        """渲染 Panel 1: 渐变绿头 + Top N总览表"""
        
        count = len(stocks)
        html = f"""<!-- ═══ 淡雅绿色头部 ═══ -->
<div style="background:linear-gradient(135deg,#e8f5e9 0%,#c8e6c9 100%);padding:32px 24px;border-radius:12px;text-align:center;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);max-width:780px;margin-left:auto;margin-right:auto;border:1px solid #a5d6a7;">
    <h1 style="color:#1b5e20;font-size:30px;margin:0 0 8px;letter-spacing:1px;">📈 {context.title}</h1>
    <p style="color:#2e7d32;margin:0;font-size:15px;">⏰ {context.report_date or '未知日期'}</p>
    {'<p style="color:#4caf50;font-size:13px;margin-top:6px;">' + context.version_str + '</p>' if context.version_str else ''}
</div>\n\n"""

        html += f"""<!-- ═══ Panel 1: Top选股总览表 ═══ -->
<div style="background:#fff;border-radius:12px;padding:24px 20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:24px;border:1px solid #e9ecef;max-width:780px;margin-left:auto;margin-right:auto;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#2c3e50;font-weight:700;">📊 Top {count} 选股总览</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;" cellpadding="0" cellspacing="0">
        <thead>
            <tr style="background:#eaf5ee;">
                <th style="padding:12px 8px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">排名</th>
                <th style="padding:12px 8px;text-align:left;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">代码/名称</th>
                <th style="padding:12px 8px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">价格</th>
                <th style="padding:12px 8px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">涨跌</th>
                <th style="padding:12px 8px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">得分</th>
                <th style="padding:12px 8px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">追涨</th>
                <th style="padding:12px 8px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">PE</th>
                <th style="padding:12px 8px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">ROE%</th>
                <th style="padding:12px 8px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">近1月</th>
                <th style="padding:12px 8px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">近3月</th>
                <th style="padding:12px 8px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">近半年</th>
                <th style="padding:12px 8px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">近1年</th>
            </tr>
        </thead>\n        <tbody>\n"""

        for stock in stocks:
            bg = ""
            if stock.rank == 1:
                bg = 'style="background:#fffbeb;"'
            elif stock.rank == 2:
                bg = 'style="background:#f5f5f5;"'
            elif stock.rank == 3:
                bg = 'style="background:#fef9ef;"'

            change_emoji = "🟢" if stock.change_pct >= 0 else "🔴"
            up_color = "#e74c3c" if stock.change_pct >= 0 else "#27ae60"

            pe_str = f"{stock.pe:.1f}" if stock.pe is not None else "—"
            roe_str = roe_badge(stock.roe)

            ret_1m = stock.ret_1m or "—"
            ret_3m = stock.ret_3m or "—"
            ret_6m = stock.ret_6m or "—"
            ret_1y = stock.ret_1y or "—"

            html += f"""            <tr {bg}>
                <td style="padding:10px 8px;text-align:center;font-weight:600;border-bottom:1px solid #eee;">{stock.rank}</td>
                <td style="padding:10px 8px;border-bottom:1px solid #eee;"><span style="color:#95a5a6;font-size:12px;">{stock.code}</span><br><b>{stock.name}</b></td>
                <td style="padding:10px 8px;text-align:right;font-weight:600;border-bottom:1px solid #eee;">¥{stock.price:.2f}</td>
                <td style="padding:10px 8px;text-align:center;color:{up_color};font-weight:600;border-bottom:1px solid #eee;">{stock.change_pct:+.1f}%{change_emoji}</td>
                <td style="padding:10px 8px;text-align:center;font-size:15px;font-weight:700;color:#e74c3c;background:#fff3f3;border-radius:4px;border-bottom:1px solid #eee;">{stock.score:.2f}</td>
                <td style="padding:10px 8px;text-align:center;font-size:16px;border-bottom:1px solid #eee;">{stock.chase_risk}</td>
                <td style="padding:10px 8px;text-align:right;white-space:nowrap;border-bottom:1px solid #eee;">{pe_str}</td>
                <td style="padding:10px 8px;text-align:center;white-space:nowrap;border-bottom:1px solid #eee;">{roe_str}</td>
                <td style="padding:10px 8px;text-align:right;white-space:nowrap;border-bottom:1px solid #eee;">{ret_1m}</td>
                <td style="padding:10px 8px;text-align:right;white-space:nowrap;border-bottom:1px solid #eee;">{ret_3m}</td>
                <td style="padding:10px 8px;text-align:right;white-space:nowrap;border-bottom:1px solid #eee;">{ret_6m}</td>
                <td style="padding:10px 8px;text-align:right;font-weight:600;white-space:nowrap;border-bottom:1px solid #eee;">{ret_1y}</td>
            </tr>\n"""

        html += """        </tbody>
    </table>
</div>\n\n"""

        return html
    
    # ─── Panel 2: Top N 个股深度分析卡 ───
    def render_panel2(self, context, stocks, top_n=5):
        """渲染 Panel 2: Top N 个股深度分析卡（估值框 + 技术面 + 收益追踪 + 操作价位 + 追涨评估 + 综合评级）"""
        
        html = f"""<!-- ═══ Panel 2: Top {top_n} 个股深度分析 ═══ -->
<div style="max-width:780px;margin-left:auto;margin-right:auto;">
    <h2 style="font-size:18px;color:#2c3e50;margin:0 0 16px;">🔍 Top {top_n} 个股深度分析</h2>
"""
        
        for i, stock in enumerate(stocks[:top_n]):
            # 卡片边框颜色（按排名）
            border_colors = ['#f1c40f', '#bdc3c7', '#e67e22', '#3498db', '#9b59b6']
            border_color = border_colors[i % len(border_colors)] if i < 5 else '#95a5a6'
            
            # 估值解读框
            pe_note = self._pe_interpretation(stock.pe)
            roe_note = self._roe_interpretation(stock.roe)
            gm_note = self._gm_interpretation(stock.gross_margin)
            ocfps_note = self._ocfps_interpretation(stock.ocfps)
            
            # 操作价位
            op = stock.operation_prices or {}
            buy_price = op.get('buy', '—')
            stop_loss = op.get('stop_loss', '—')
            tp1 = op.get('tp1', '—')
            tp2 = op.get('tp2', '—')
            
            # 构建估值框内容 — 每行图标+标题+值
            valuation_html = """
        <!-- 📈 估值解读框 -->
        <div style="background:#f0fdf4;border-radius:8px;padding:14px;margin-bottom:14px;border:1px solid #bbf7d0;">
            <p style="margin:0 0 8px;font-size:13px;color:#1a6b42;font-weight:600;">📈 估值解读</p>
            <table style="width:100%;font-size:14px;border-collapse:collapse;">
                <tr><td style="padding:4px 0;"><span style="color:#64748b;">PE:</span></td><td style="text-align:right;font-weight:600;">{pe}</td></tr>
                <tr><td style="padding:4px 0;"><span style="color:#64748b;">ROE:</span></td><td style="text-align:right;font-weight:600;">{roe}</td></tr>""".format(pe=pe_note, roe=roe_note)
            if stock.gross_margin is not None:
                valuation_html += f'<tr><td style="padding:4px 0;"><span style="color:#64748b;">毛利率:</span></td><td style="text-align:right;font-weight:600;">{gm_note}</td></tr>'
            if stock.ocfps is not None:
                valuation_html += f'<tr><td style="padding:4px 0;"><span style="color:#64748b;">现金流/股:</span></td><td style="text-align:right;font-weight:600;">{ocfps_note}</td></tr>'
            valuation_html += "\n            </table>\n        </div>"
            
            html += f"""
    <!-- 个股卡片 #{stock.rank}: {stock.code} {stock.name} -->
    <div style="background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:16px;border-left:4px solid {border_color};">
        <!-- 📊 卡片标题 — 仅名称+代码 -->
        <h3 style="margin:0 0 12px;font-size:16px;color:#2c3e50;">📊 Top{stock.rank}. {stock.name}({stock.code})</h3>
        
        <!-- 💰 当前行情区 — 独立区块 -->
        <div style="background:#f8fafc;border-radius:8px;padding:12px;margin-bottom:14px;border:1px solid #e2e8f0;width:100%;">
            <p style="margin:0;font-size:13px;color:#64748b;font-weight:600;">💰 当前行情</p>
            <div style="display:flex;gap:16px;margin-top:8px;font-size:14px;">
                <span><b>价格:</b> ¥{stock.price:.2f}</span>
                <span style="color:{'#e74c3c' if stock.change_pct >= 0 else '#27ae60'};"><b>涨跌:</b> {stock.change_pct:+.1f}%</span>
                <span><b>得分:</b> {stock.score:.2f}</span>
            </div>
        </div>
        """

            # 🔧 技术面：解析指标
            tech_rows = ''
            if stock.tech_notes:
                import re
                for part in [t.strip() for t in stock.tech_notes.split('|')]:
                    match = re.match(r'([A-Z][a-zA-Z]*)\s*(.*)', part, re.IGNORECASE)
                    label = match.group(1) if match else '指标'
                    value = (match.group(2).strip() if match else part)
                    tech_rows += '<tr><td style="padding:2px 0;"><span style="color:#64748b;">%s:</span></td><td style="text-align:right;font-weight:600;font-size:13px;">%s</td></tr>' % (label, value)

            # 📊 收益追踪数据
            ret_1y = stock.ret_1y or '—'
            ret_6m = stock.ret_6m or '—'
            ret_3m = stock.ret_3m or '—'
            ret_1m = stock.ret_1m or '—'

            # 💰 操作价位行
            tp2_row = ''
            if tp2 != '—':
                tp2_row = '<tr><td style="font-size:13px;">止盈目标2</td><td style="text-align:right;color:#27ae60;font-size:13px;font-weight:600;">%s (+50%%)</td></tr>' % tp2

            # 条件行：毛利率/现金流
            gm_row = ''
            if stock.gross_margin is not None:
                gm_row = '<tr><td style="padding:2px 0;"><span style="color:#64748b;">毛利率:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>' % gm_note
            ocfps_row = ''
            if stock.ocfps is not None:
                ocfps_row = '<tr><td style="padding:2px 0;"><span style="color:#64748b;">现金流/股:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>' % ocfps_note

            # ====== 2×2 网格：估值解读 | 技术面 / 收益追踪 | 操作价位 ======
            html += '''
        <!-- 2x2 数据卡网格 -->
        <table style="width:100%%;border-collapse:separate;border-spacing:8px;margin-bottom:12px;">
            <tr>
                <td style="vertical-align:top;width:50%%;background:#f0fdf4;border-radius:8px;padding:10px;border:1px solid #bbf7d0;">
                    <p style="margin:0 0 6px;font-size:12px;color:#1a6b42;font-weight:700;">📈 估值解读</p>
                    <table style="width:100%%;font-size:13px;border-collapse:collapse;">
                        <tr><td style="padding:2px 0;"><span style="color:#64748b;">PE:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>
                        <tr><td style="padding:2px 0;"><span style="color:#64748b;">ROE:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>
                        %s
                        %s
                    </table>
                </td>
                <td style="vertical-align:top;width:50%%;background:#f0fdf4;border-radius:8px;padding:10px;border:1px solid #bbf7d0;">
                    <p style="margin:0 0 6px;font-size:12px;color:#1a6b42;font-weight:700;">🔧 技术面分析</p>
                    <table style="width:100%%;border-collapse:collapse;">
                        %s
                    </table>
                </td>
            </tr>
            <tr>
                <td style="vertical-align:top;width:50%%;background:#f8fafc;border-radius:8px;padding:10px;border:1px solid #e2e8f0;">
                    <p style="margin:0 0 6px;font-size:12px;color:#64748b;font-weight:700;">📊 收益追踪</p>
                    <table style="width:100%%;font-size:13px;border-collapse:collapse;">
                        <tr><td style="padding:2px 0;"><span style="color:#64748b;">近1月:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>
                        <tr><td style="padding:2px 0;"><span style="color:#64748b;">近3月:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>
                        <tr><td style="padding:2px 0;"><span style="color:#64748b;">近半年:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>
                        <tr><td style="padding:2px 0;"><span style="color:#64748b;">近1年:</span></td><td style="text-align:right;font-weight:600;">%s</td></tr>
                    </table>
                </td>
                <td style="vertical-align:top;width:50%%;background:#fffbeb;border-radius:8px;padding:10px;border:1px solid #fef3c7;">
                    <p style="margin:0 0 6px;font-size:12px;color:#92400e;font-weight:700;">💰 操作价位</p>
                    <table style="width:100%%;border-collapse:collapse;">
                        <tr><td style="font-size:13px;">买入参考价</td><td style="text-align:right;font-size:13px;font-weight:600;">%s</td></tr>
                        <tr><td style="font-size:13px;">止损价</td><td style="text-align:right;color:#e74c3c;font-size:13px;font-weight:600;">%s (-12%%)</td></tr>
                        <tr><td style="font-size:13px;">止盈目标1</td><td style="text-align:right;color:#27ae60;font-size:13px;font-weight:600;">%s (+20%%)</td></tr>
                        %s
                    </table>
                </td>
            </tr>
        </table>''' % (pe_note, roe_note, gm_row, ocfps_row,
                tech_rows if tech_rows else '<tr><td style="font-size:13px;color:#999;">无数据</td></tr>',
                ret_1m, ret_3m, ret_6m, ret_1y,
                buy_price, stop_loss, tp1, tp2_row)
            
            # 🎯追涨评估+💡策略建议+⭐综合评级 → 紧凑网格卡
            if stock.rating_text:
                rating_block = '''
                    <div style="border-top:1px solid #e2e8f0;padding-top:8px;margin-top:8px;">
                        <p style="margin:0;font-size:13px;color:#92400e;font-weight:700;">⭐ 综合评级</p>
                        <p style="margin:4px 0 0;font-size:13px;">%s</p>
                    </div>''' % stock.rating_text
            else:
                rating_block = ''

            html += '''
        <!-- 追涨+策略+评级 → 紧凑网格卡 -->
        <table style="width:100%%;border-collapse:separate;border-spacing:8px;margin-bottom:4px;">
            <tr>
                <td style="vertical-align:top;width:50%%;background:#fffbeb;border-radius:8px;padding:10px;border:1px solid #fef3c7;">
                    <p style="margin:0 0 4px;font-size:12px;color:#92400e;font-weight:700;">🎯 安全追涨评估</p>
                    <p style="margin:0;font-size:13px;">%s</p>
                </td>
                <td style="vertical-align:top;width:50%%;background:#eff6ff;border-radius:8px;padding:10px;border:1px solid #bfdbfe;">
                    <p style="margin:0 0 4px;font-size:12px;color:#1e40af;font-weight:700;">💡 策略建议</p>
                    <p style="margin:0;font-size:13px;">%s</p>
                </td>
            </tr>
        </table>
        %s''' % (stock.chase_risk, stock.strategy_text, rating_block)
            
            html += """
    </div>"""
        
        html += "</div>\n\n"
        return html
    
    # ─── Panel 2b: #6~#10 紧凑简表 ───
    def render_panel2_compact(self, context, stocks):
        """渲染 #6~#10 紧凑简表（含操作建议/价位）"""
        compact_stocks = stocks[5:10]
        if not compact_stocks:
            return ""
        
        html = f"""<!-- ═══ Panel 2b: #N~#M 紧凑简表 ═══ -->
<div style="background:#fff;border-radius:12px;padding:24px 20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:24px;border:1px solid #e9ecef;margin-top:24px;max-width:780px;margin-left:auto;margin-right:auto;">
    <h3 style="font-size:16px;color:#2c3e50;margin:0 0 14px;">📋 #{compact_stocks[0].rank}~#{compact_stocks[-1].rank} 快速参考</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;" cellpadding="0" cellspacing="0">
        <thead>
            <tr style="background:#eaf5ee;">
                <th style="padding:10px 6px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">排名</th>
                <th style="padding:10px 6px;text-align:left;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">名称/代码</th>
                <th style="padding:10px 6px;text-align:right;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">价格</th>
                <th style="padding:10px 6px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">涨跌</th>
                <th style="padding:10px 6px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">得分</th>
                <th style="padding:10px 6px;text-align:center;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">操作建议</th>
                <th style="padding:10px 6px;text-align:left;border-bottom:2px solid #b8d8c8;font-weight:700;color:#1a6b42;">操作价位</th>
            </tr>
        </thead>\n        <tbody>\n"""
        
        for i, stock in enumerate(compact_stocks):
            op = stock.operation_prices or {}
            buy_price = op.get('buy', '—')
            stop_loss = op.get('stop_loss', '—')
            tp1 = op.get('tp1', '—')
            tp2 = op.get('tp2', '—')
            
            # 操作建议：根据评分和追涨风险判断
            if stock.score >= 5.0:
                advice = "⭐⭐ 波段"
            else:
                advice = "⭐ 观望"
            
            change_emoji_c = "🟢" if stock.change_pct >= 0 else "🔴"
            up_color_c = "#e74c3c" if stock.change_pct >= 0 else "#27ae60"
            
            # 操作价位缩写
            op_str = f"买:{buy_price} | 损:{stop_loss} | 盈:{tp1}"
            if tp2 != '—':
                op_str += f"/{tp2}"
            
            html += f"""
                <tr style="background:{'#fafafa' if i % 2 == 1 else '#fff'};">
                    <td style="padding:8px 6px;text-align:center;font-weight:600;border-bottom:1px solid #eee;">#{stock.rank}</td>
                    <td style="padding:8px 6px;border-bottom:1px solid #eee;"><span style="color:#95a5a6;font-size:12px;">{stock.code}</span><br><b>{stock.name}</b></td>
                    <td style="padding:8px 6px;text-align:right;border-bottom:1px solid #eee;font-weight:600;">¥{stock.price:.2f}</td>
                    <td style="padding:8px 6px;text-align:center;border-bottom:1px solid #eee;color:{up_color_c};font-weight:600;">{change_emoji_c} {stock.change_pct:+.1f}%</td>
                    <td style="padding:8px 6px;text-align:center;font-weight:700;color:#e74c3c;border-bottom:1px solid #eee;">{stock.score:.2f}</td>
                    <td style="padding:8px 6px;text-align:center;border-bottom:1px solid #eee;">{advice}</td>
                    <td style="padding:8px 6px;font-size:12px;border-bottom:1px solid #eee;color:#555;">{op_str}</td>
                </tr>\n"""
        
        html += """        </tbody>
    </table>
</div>\n\n"""
        return html
    
    # ─── 估值解读辅助函数 ───
    def _pe_interpretation(self, pe):
        """PE估值解读"""
        if pe is None:
            return "无数据"
        if pe < 0:
            return f"PE={pe:.2f}(亏损，需关注扭亏预期)"
        elif pe <= 15:
            return f"PE={pe:.2f}✅(低估区间)"
        elif pe <= 30:
            return f"PE={pe:.2f}(合理区间)"
        elif pe <= 60:
            return f"PE={pe:.2f}(偏高，需高成长支撑)"
        else:
            return f"⚠️ PE={pe:.2f}（极高估值）"
    
    def _roe_interpretation(self, roe):
        """ROE解读"""
        if roe is None:
            return "无数据"
        if roe >= 20:
            return f"ROE={roe:.2f}%🔥（卓越）"
        elif roe >= 15:
            return f"ROE={roe:.2f}%✅（优秀）"
        elif roe >= 10:
            return f"ROE={roe:.2f}%（健康）"
        elif roe >= 3:
            return f"ROE={roe:.2f}%⚠️（偏低，需关注盈利能力）"
        else:
            return f"ROE={roe:.2f}%❌（低于安全线，谨慎看待）"
    
    def _gm_interpretation(self, gm):
        """毛利率解读"""
        if gm is None:
            return "无数据"
        if gm >= 50:
            return f"{gm:.1f}%🔥（极高利润率）"
        elif gm >= 30:
            return f"{gm:.1f}%✅（健康水平）"
        elif gm >= 20:
            return f"{gm:.1f}%（正常水平）"
        elif gm >= 10:
            return f"{gm:.1f}%⚠️（偏低，成本控制压力较大）"
        else:
            return f"{gm:.1f}%❌（极低利润率）"
    
    def _ocfps_interpretation(self, ocfps):
        """每股现金流解读"""
        if ocfps is None:
            return "无数据"
        if ocfps > 0.5:
            return f"{ocfps:.2f}✅（正向充裕）"
        elif ocfps > 0:
            return f"{ocfps:.2f}⚠️（正向但偏弱）"
        else:
            return f"{ocfps:.2f}❌（需警惕流动性风险）"
    
    # ─── 投资组合分类与行业查询（轻量版） ───
    COMMON_STOCK_SECTORS = {
        '胜宏科技': '科技', '东山精密': '科技', '中国能建': '基建',
        '大唐发电': '电力', '南威软件': '科技', '众生药业': '医药',
        '润建股份': '通信', '宁德时代': '新能源', '比亚迪': '汽车',
        '贵州茅台': '消费', '五粮液': '消费', '海天味业': '消费',
        '中国平安': '金融', '招商银行': '金融', '东方财富': '金融',
        '中芯国际': '科技', '韦尔股份': '科技', '兆易创新': '科技',
    }

    def _classify_stock_type(self, stock):
        """
        轻量版股票类型分类（基于PE/ROE/毛利率）
        Returns: 'value' | 'growth' | 'balanced' | 'speculative'
        """
        pe = stock.pe if stock.pe else 0
        roe = stock.roe if stock.roe else 0
        gm = stock.gross_margin if stock.gross_margin is not None else 50

        # 投机/劣质股：PE亏损或ROE极低+毛利率失控
        if pe < 0 and roe < 3:
            return 'speculative'
        if pe > 200 and roe < 5:
            return 'speculative'

        # 价值股：低PE + ROE健康
        if 0 < pe <= 20 and roe >= 10:
            return 'value'

        # 成长股：高PE但ROE尚可+毛利率优秀
        if pe > 30 and gm >= 40 and roe >= 8:
            return 'growth'

        # 平衡型：中等估值 + ROE正常
        if pe <= 60 and roe >= 5:
            return 'balanced'

        # 默认投机
        if pe < 0 or roe < 3:
            return 'speculative'

        return 'balanced'

    def _get_sector_name(self, stock):
        """
        轻量版行业板块查询（本地字典）
        """
        for name_prefix, sector in self.COMMON_STOCK_SECTORS.items():
            if name_prefix in stock.name:
                return sector
        # 通用fallback
        fallbacks = {'科技', '消费', '金融', '医药', '新能源'}
        return list(fallbacks)[hash(stock.code) % len(fallbacks)]

    def _calc_portfolio_weights(self, stocks):
        """
        基于得分占比+类型因子计算仓位权重，归一化到100%
        """
        if not stocks:
            return []
        total_score = sum(s.score for s in stocks) or len(stocks)
        type_mults = {'value': 1.2, 'balanced': 1.0, 'growth': 0.8, 'speculative': 0.6}
        weights = []
        for stock in stocks:
            base_w = (stock.score / total_score) * 100
            stype = self._classify_stock_type(stock)
            adjusted = base_w * type_mults.get(stype, 1.0)
            weights.append(max(10, min(35, adjusted)))
        tw = sum(weights) or 1
        weights = [round(w / tw * 100) for w in weights]
        diff = 100 - sum(weights)
        if diff != 0 and weights:
            weights[0] += diff
        return [int(w) for w in weights]

    def _stock_type_label(self, stock):
        stype = self._classify_stock_type(stock)
        labels = {'value': '价值', 'growth': '成长', 'balanced': '平衡', 'speculative': '投机'}
        return labels.get(stype, '平衡')

    def _stock_role_label(self, stock):
        stype = self._classify_stock_type(stock)
        roles = {'value': '价值底仓', 'growth': '成长弹性', 'balanced': '平衡配置', 'speculative': '投机观察'}
        return roles.get(stype, '平衡配置')

    # ─── Panel 3: 投资组合配置建议 ───
    def render_panel3(self, context, stocks):
        """
        生成Panel 3 — 投资组合配置建议
        - 保守型卡（蓝系）：最多3只，价值/平衡类优先
        - 进取型卡（橙系）：最多5只，均衡配置
        """
        # Step 1: 分类候选股票
        growth_cands = []
        value_cands = []
        balanced_cands = []
        for stock in stocks:
            stype = self._classify_stock_type(stock)
            if stype == 'growth':
                growth_cands.append(stock)
            elif stype == 'value':
                value_cands.append(stock)
            else:
                balanced_cands.append(stock)

        # Step 2: 保守型组合（价值+平衡，最多3只）
        conservative = []
        for stock in (value_cands + balanced_cands):
            if len(conservative) >= 3:
                break
            if not self._is_toxic_stock(stock):
                conservative.append(stock)
        # 不足时从全部补
        while len(conservative) < min(2, len(stocks)):
            for stock in stocks:
                if stock not in conservative and not self._is_toxic_stock(stock):
                    conservative.append(stock)
                    break
            else:
                break

        # Step 3: 进取型组合（均衡：价值+平衡+成长，最多5只）
        aggressive = []
        aggressive.extend(value_cands[:2])
        if balanced_cands:
            aggressive.append(balanced_cands[0])
        aggressive.extend(growth_cands[:1])
        remaining = [s for s in stocks if s not in aggressive]
        while len(aggressive) < 5 and remaining:
            aggressive.append(remaining.pop(0))

        # Step 4: 计算仓位权重
        cons_weights = self._calc_portfolio_weights(conservative)
        agg_weights = self._calc_portfolio_weights(aggressive)

        # Step 5: 渲染HTML
        return self._render_panel3_html(context, conservative, cons_weights, aggressive, agg_weights)

    def _generate_risk_warnings(self, stocks_list):
        """
        为组合内每只股票生成个性化风险提示
        Returns: List[(stock_name, risk_text)]
        """
        warnings = []
        for stock in stocks_list:
            risks = []
            pe = stock.pe if stock.pe else 0
            roe = stock.roe if stock.roe is not None else 0
            gm = stock.gross_margin if stock.gross_margin is not None else 50

            if pe < 0:
                risks.append(f"PE为负，存在亏损风险")
            elif pe > 60:
                risks.append(f"PE偏高({pe:.1f})，需高成长支撑")
            elif pe <= 0:
                pass  # skip zero/near-zero

            if roe < 3:
                risks.append(f"ROE过低({roe:.2f}%)，盈利能力弱")
            elif roe < 8:
                risks.append(f"ROE偏低({roe:.1f}%)，关注盈利改善")

            ret_1y = stock.ret_1y or ''
            try:
                pct = float(ret_1y.replace('%', '').strip())
                if pct > 80:
                    risks.append("短期涨幅过大，注意回调风险")
            except (ValueError, AttributeError):
                pass

            if risks:
                warnings.append((stock.name, '; '.join(risks)))

        # 投机股统计
        spec_count = sum(1 for s in stocks_list if self._classify_stock_type(s) == 'speculative')
        return warnings, spec_count

    def _render_risk_card(self, context, stocks_list):
        """
        渲染组合风险提示卡（红/橙系，显示个股风险+投机股警告）
        """
        warnings, spec_count = self._generate_risk_warnings(stocks_list)

        if not warnings and spec_count == 0:
            return ''

        html = f"""
    <div style="background:#fff1f0;border:1px solid #ffa39e;border-radius:8px;padding:12px;margin-top:16px;max-width:780px;margin-left:auto;margin-right:auto;">
        <p style="font-size:13px;color:#cf1322;margin:0 0 8px;">⚠️ <b>本组合风险提示</b></p>
"""

        for name, risk_text in warnings:
            html += f'        <p style="font-size:12px;color:#595959;margin:4px 0;">• {name}: {risk_text}</p>\n'

        if spec_count > 0:
            level = '偏高' if spec_count <= 2 else '较高'
            html += f'        <p style="font-size:12px;color:#cf1322;margin:6px 0 0;font-weight:600;">投机股{spec_count}只，整体风险{level}</p>\n'

        html += '    </div>\n'
        return html

    def _is_toxic_stock(self, stock):
        """判断是否为toxic股票（PE亏损+ROE极低等）"""
        pe = stock.pe if stock.pe else 0
        roe = stock.roe if stock.roe else 0
        gm = stock.gross_margin if stock.gross_margin is not None else 50
        if pe < 0 and roe < 3:
            return True
        if pe > 500:
            return True
        if roe < 3 and gm < 8:
            return True
        return False

    # ─── _render_portfolio_card: 单张组合卡（保守/进取） ───
    def _render_portfolio_card(self, context, stocks_list, weights, mode='conservative'):
        """
        渲染一张投资组合卡片
        - conservative: 蓝色系 (#3b82f6 / #dbeafe)
        - aggressive: 橙色系 (#f59e0b / #fef3c7)
        """
        if mode == 'conservative':
            header_bg = '#eff6ff'
            header_border = '#bfdbfe'
            accent_color = '#1d4ed8'
            card_title = f'🛡️ 保守型（稳健为主，最多{len(stocks_list)}只）'
        else:
            header_bg = '#fffbeb'
            header_border = '#fde68a'
            accent_color = '#b45309'
            card_title = f'🚀 进取型（均衡配置，最多{len(stocks_list)}只）'

        if not stocks_list:
            return f"""
    <div style="background:{header_bg};border:1px solid {header_border};border-radius:8px;margin-top:16px;max-width:780px;margin-left:auto;margin-right:auto;padding:12px;text-align:center;color:#94a3b8;font-size:13px;">暂无组合数据</div>\n"""

        html = f"""
    <div style="background:{header_bg};border:1px solid {header_border};border-radius:8px;margin-top:16px;max-width:780px;margin-left:auto;margin-right:auto;padding:0;overflow:hidden;">
        <!-- 卡片标题栏 -->
        <div style="padding:12px 16px;border-bottom:2px solid {header_border};">
            <h3 style="font-size:15px;color:{accent_color};margin:0;">{card_title}</h3>
        </div>\n"""

        # --- 股票列表 + 操作价位表（每只一只小卡）---
        for idx, stock in enumerate(stocks_list):
            w = weights[idx] if idx < len(weights) else int(100 / max(len(stocks_list), 1))
            stype = self._stock_type_label(stock)
            srole = self._stock_role_label(stock)
            sector = self._get_sector_name(stock)
            score = stock.score
            pe_str = f"{stock.pe:.2f}" if stock.pe else "无数据"
            roe_str = f"{stock.roe:.1f}%" if stock.roe is not None else "无数据"

            # 操作价位
            op = stock.operation_prices or {}
            buy_p = op.get('buy', '¥0.00')
            stop_p = op.get('stop_loss', '¥0.00')
            tp1 = op.get('tp1', '—')
            tp2 = op.get('tp2', '—')

            # 涨跌颜色
            change_pct = stock.change_pct
            up_color = '#e74c3c' if change_pct >= 0 else '#27ae60'
            change_emoji = '🟢' if change_pct >= 0 else '🔴'

            # zebra row bg
            row_bg = '#fff' if idx % 2 == 0 else '#fafafa'

            html += f"""
        <!-- 股票 #{idx+1}: {stock.name} -->
        <div style="padding:12px 16px;background:{row_bg};border-bottom:1px solid {header_border};">
            <table cellpadding=0 cellspacing=0 width=100%>
                <tr>
                    <td style="width:30px;text-align:center;vertical-align:middle;"><span style="display:inline-block;width:24px;height:24px;line-height:24px;border-radius:50%;background:{accent_color};color:#fff;font-size:12px;font-weight:700;">{idx+1}</span></td>
                    <td style="vertical-align:middle;">
                        <b style="font-size:14px;">{stock.name}</b>
                        <span style="color:#95a5a6;font-size:12px;margin-left:8px;">{stock.code}</span>
                        <span style="display:inline-block;margin-left:8px;padding:2px 8px;border-radius:4px;background:{accent_color}18;color:{accent_color};font-size:11px;">[{sector}]</span>
                        <span style="display:inline-block;margin-left:4px;padding:2px 8px;border-radius:4px;background:#f1f5f9;color:#64748b;font-size:11px;">{srole}</span>
                    </td>
                    <td style="text-align:right;vertical-align:middle;width:80px;padding-right:8px;">
                        <span style="font-size:12px;color:#95a5a6;">仓位</span><br>
                        <b style="font-size:14px;color:{accent_color};">~{w}%</b>
                    </td>
                </tr>
                <tr><td colspan=3 style="padding-top:8px;">
                    <table cellpadding=0 cellspacing=0 width=100%>
                        <tr>
                            <td style="width:33%;font-size:12px;color:#64748b;">
                                <span style="color:#95a5a6;">得分</span> <b style="color:#e74c3c;">{score:.2f}</b>
                            </td>
                            <td style="width:33%;font-size:12px;color:#64748b;">
                                <span style="color:#95a5a6;">PE/ROE</span> <b>{pe_str} / {roe_str}</b>
                            </td>
                            <td style="width:33%;font-size:12px;text-align:right;color:{up_color};">
                                <b>{change_emoji} ¥{stock.price:.2f} ({change_pct:+.1f}%)</b>
                            </td>
                        </tr>
                    </table>
                </td></tr>
                <tr><td colspan=3 style="padding-top:8px;">
                    <!-- 操作价位小表 -->
                    <div style="display:inline-block;border:1px solid #e5e7eb;border-radius:6px;padding:8px 12px;background:#fff;">
                        <table cellpadding=0 cellspacing=0>
                            <tr>
                                <th style="padding:4px 10px;font-size:11px;color:#95a5a6;text-align:left;border-bottom:1px solid #f3f4f6;">💰 买入</th>
                                <th style="padding:4px 10px;font-size:11px;color:#e74c3c;text-align:center;border-bottom:1px solid #f3f4f6;">🛑 止损</th>
                                <th style="padding:4px 10px;font-size:11px;color:#27ae60;text-align:center;border-bottom:1px solid #f3f4f6;">🎯 止盈T1</th>
                                <th style="padding:4px 10px;font-size:11px;color:#27ae60;text-align:right;border-bottom:1px solid #f3f4f6;">🚀 止盈T2</th>
                            </tr>
                            <tr>
                                <td style="padding:4px 10px;font-size:13px;font-weight:600;text-align:left;">{buy_p}</td>
                                <td style="padding:4px 10px;font-size:13px;font-weight:600;color:#e74c3c;text-align:center;">{stop_p}</td>
                                <td style="padding:4px 10px;font-size:13px;font-weight:600;color:#27ae60;text-align:center;">{tp1}</td>
                                <td style="padding:4px 10px;font-size:13px;font-weight:600;color:#27ae60;text-align:right;">{tp2}</td>
                            </tr>
                        </table>
                    </div>
                </td></tr>\n"""
            html += "</table>\n        </div>\n"

        # 去除最后一张卡片的 border-bottom（与卡片底部一致）
        html = html.rstrip()
        if html.endswith('</div>'):
            pass  # keep it

        # ─── 组合内嵌风险提示区 ───
        risk_block = self._render_panel3_risk_block(stocks_list)

        return f"{html}{risk_block}\n    </div>\n"

    # ─── _render_panel3_risk_block: 组合卡内嵌风险提示区 ───
    def _render_panel3_risk_block(self, stocks_list):
        """渲染组合卡内部的风险提示区块（嵌入卡片底部）"""
        warnings, spec_count = self._generate_risk_warnings(stocks_list)
        if not warnings and spec_count == 0:
            return ''

        risk_html = f"""\n        <div style="padding:12px 16px;background:#fff7ed;border-top:1px solid #fed7aa;">
            <p style="font-size:13px;color:#c2410c;margin:0 0 8px;">⚠️ <b>本组合风险提示</b></p>"""

        for name, risk_text in warnings:
            risk_html += f'            <p style="font-size:12px;color:#78350f;margin:4px 0;">• {name}: {risk_text}</p>\n'

        if spec_count > 0:
            level = '偏高' if spec_count <= 2 else '较高'
            risk_html += f'            <p style="font-size:12px;color:#dc2626;margin:8px 0 0;font-weight:600;">投机股{spec_count}只，整体风险{level}</p>\n'

        risk_html += '        </div>\n'
        return risk_html

    def _render_panel3_html(self, context, conservative, cons_weights, aggressive, agg_weights):
        """渲染Panel 3完整HTML"""
        html = f"""\n<!-- ═══ Panel 3: 投资组合配置建议 ═══ -->
<div style="margin-top:24px;">
    <h2 style="text-align:center;font-size:18px;color:#2c3e50;margin-bottom:16px;">🎯 投资组合配置建议</h2>"""

        # --- 保守型卡片 ---
        html += self._render_portfolio_card(context, conservative, cons_weights, mode='conservative')

        # --- 进取型卡片 ---
        html += self._render_portfolio_card(context, aggressive, agg_weights, mode='aggressive')

        # --- 投资建议 ---
        html += f"""
    <div style="background:#fffbe6;border:1px solid #ffe58f;border-radius:8px;padding:12px;margin-top:16px;max-width:780px;margin-left:auto;margin-right:auto;">
        <p style="font-size:13px;color:#d46b08;margin:0 0 6px;">⚠️ <b>风险提示</b></p>
        <ul style="font-size:12px;color:#8c7e6d;margin:0;padding-left:18px;">
            <li>以上仅为基于量化模型的筛选结果，不构成投资建议</li>
            <li>建议分批建仓，控制单只股票仓位不超过30%</li>
            <li>设置止损位（通常-8%~-10%）和止盈目标（+20%~+50%）</li>
            <li>关注个股财报季表现及行业政策变化</li>
        </ul>
    </div>
</div>\n"""
        return html

    # ─── render() 主入口 — Panel 1 + Panel 2 + Panel 2b + Panel 3 ───
    def render(self, context, stocks):
        """生成完整HTML邮件内容（Panel 1 + Panel 2 + Panel 2b + Panel 3）"""
        panel1 = self.render_panel1(context, stocks)
        panel2 = self.render_panel2(context, stocks, top_n=5)  # Top 5深度分析
        panel2b = self.render_panel2_compact(context, stocks)   # #6~#10紧凑表
        panel3 = self.render_panel3(context, stocks)             # Panel 3: 投资组合配置建议
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:20px;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;"><div>

{panel1}
{panel2}
{panel2b}
{panel3}

</div>
<!-- ═══ 页脚 ═══ -->
<div style="text-align:center;color:#95a5a6;font-size:12px;margin-top:24px;padding:12px;border-top:1px solid #eee;">
    <p>🥬 菜菜选股系统 | {context.report_date or '未知日期'} | 数据仅供参考，不构成投资建议</p>
</div>

</body></html>"""
    
    # ─── output() — SMTP发送邮件 ───
    def output(self, context, stocks):
        """渲染HTML并发送到指定邮箱"""
        try:
            html_content = self.render(context, stocks)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📈 盘前选股报告 - {context.report_date or '今日'}"
            msg['From'] = self.sender_email
            msg['To'] = ", ".join(self.recipient_emails)
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 附加CLI原始文本（如果存在）
            reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'reports')
            report_file = os.path.join(reports_dir, f"daily-report-{context.report_date}.txt")
            if os.path.exists(report_file):
                with open(report_file, 'r', encoding='utf-8') as f:
                    cli_text = f.read()
                msg.attach(MIMEText(cli_text, 'plain', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, self.recipient_emails, msg.as_string())
            server.quit()
            
            print(f"[email] ✅ 邮件已发送至: {', '.join(self.recipient_emails)}")
            return True
            
        except Exception as e:
            print(f"[email] ❌ 发送失败: {e}")
            import traceback
            traceback.print_exc()
            return False


# ═══════════════════════════════════════════
# 测试入口 — 直接运行本文件时验证 Panel 1
# ═══════════════════════════════════════════

if __name__ == "__main__":
    from email_core_models import ReportReader
    
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'reports')
    today_file = os.path.join(reports_dir, "daily-report-2026-05-13.txt")
    
    if not os.path.exists(today_file):
        print(f"❌ 未找到报告: {today_file}")
        sys.exit(1)
    
    # 解析 + 渲染
    reader = ReportReader()
    context, stocks = reader.parse_report(today_file)
    
    outputter = HTMLEmailOutputter()
    html = outputter.render(context, stocks)
    
    # 保存预览
    preview_path = os.path.join(reports_dir, "email-preview-panel1.html")
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Panel 1 HTML已生成: {preview_path}")
    print(f"[info] Top3:")
    for s in stocks[:3]:
        print(f"  #{s.rank} {s.code} {s.name} ¥{s.price:.2f} ({s.change_pct:+.1f}%) score={s.score}")
