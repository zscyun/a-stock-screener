#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 Panel 1 - Top选股总览表渲染函数"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_core_models import StockData, ReportContext


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
    """涨跌颜色"""
    return "up" if change_pct >= 0 else "down"


def render_panel1(context, stocks):
    """渲染 Panel 1: Top选股总览表 (含头部)"""
    
    # ── 头部 ──
    html = f"""<!-- ═══ 渐变绿色头部 ═══ -->
<div style="background:linear-gradient(135deg,#27ae60 0%,#2ecc71 100%);padding:30px;border-radius:12px;text-align:center;margin-bottom:24px;">
    <h1 style="color:#fff;font-size:28px;margin:0 0 8px;">📈 {context.title}</h1>
    <p style="color:rgba(255,255,255,0.9);margin:0;">⏰ {context.report_date or '未知日期'}</p>
    {'<p style="color:rgba(255,255,255,0.8);font-size:13px;margin-top:4px;">' + context.version_str + '</p>' if context.version_str else ''}
</div>\n\n"""

    # ── Panel 1 标题 ──
    count = len(stocks)
    html += f"""<!-- ═══ Panel 1: Top选股总览表 ═══ -->
<div style="background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:24px;">
    <h2 style="margin:0 0 12px;font-size:18px;color:#2c3e50;">📊 Top {count} 选股总览</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;" cellpadding="0" cellspacing="0">
        <thead>
            <tr style="background:#f8f9fa;">
                <th style="padding:10px 8px;text-align:center;border-bottom:2px solid #dee2e6;">排名</th>
                <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #dee2e6;">代码/名称</th>
                <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #dee2e6;">价格</th>
                <th style="padding:10px 8px;text-align:center;border-bottom:2px solid #dee2e6;">涨跌</th>
                <th style="padding:10px 8px;text-align:center;border-bottom:2px solid #dee2e6;">得分</th>
                <th style="padding:10px 8px;text-align:center;border-bottom:2px solid #dee2e6;">追涨</th>
                <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #dee2e6;">PE</th>
                <th style="padding:10px 8px;text-align:center;border-bottom:2px solid #dee2e6;">ROE%</th>
                <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #dee2e6;">近1月</th>
                <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #dee2e6;">近3月</th>
                <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #dee2e6;">近半年</th>
                <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #dee2e6;">近1年</th>
            </tr>
        </thead>\n        <tbody>\n"""

    # ── 数据行 (斑马纹 + Top3特殊背景) ──
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


# ─── 测试：用真实报告数据验证 ───
if __name__ == "__main__":
    from email_core_models import ReportReader
    
    # 找今天的报告
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'reports')
    today_file = os.path.join(reports_dir, "daily-report-2026-05-13.txt")
    
    if not os.path.exists(today_file):
        print(f"❌ 未找到报告: {today_file}")
        sys.exit(1)
    
    # 解析报告
    reader = ReportReader()
    context, stocks = reader.parse_report(today_file)
    
    print(f"[test] 解析完成: {len(stocks)} 只股票")
    print(f"[test] 日期: {context.report_date}")
    
    # 渲染 Panel 1
    panel_html = render_panel1(context, stocks)
    
    # 保存测试 HTML
    test_file = os.path.join(reports_dir, "panel1-test.html")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("<!DOCTYPE html>\n<html><head><meta charset='UTF-8'></head><body style='margin:0;padding:20px;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;'>")
        f.write(panel_html)
        f.write("</body></html>")
    
    print(f"✅ Panel 1 HTML 已生成: {test_file}")
    print(f"[info] Top3:")
    for s in stocks[:3]:
        print(f"  #{s.rank} {s.code} {s.name} ¥{s.price:.2f} ({s.change_pct:+.1f}%) score={s.score} pe={s.pe}")
