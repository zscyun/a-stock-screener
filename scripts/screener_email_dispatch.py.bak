#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screener Email Dispatch Module - 菜菜 v1.0.0

本模块是 a-stock-combo screener skill 的一部分，负责将选股报告以精美HTML邮件形式发送。
后续扩展：支持多种报告类型（盘前/收盘/异动预警等）的邮件分发。
"""

import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# 报告目录（自动定位到 workspace 根目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.join(SCRIPT_DIR, '..', '..', '..')
REPORTS_DIR = os.path.join(WORKSPACE_ROOT, 'reports')
report_dir = REPORTS_DIR
with open(os.path.join(report_dir, 'daily-report-2026-05-12.txt'), 'rb') as f:
    cli_output = f.read()

# ─── Top 15 data ───────────────────────────────────────────────
TOP15 = [
    {'r':'🥇','c':'601991','n':'大唐发电','p':'¥6.70','ch':'+10.0%🟢','s':'7.09','pe':'14.0','roe':'7.35%','m1':'+58.6%📈','m6':'+60.9%📈','y1':'+90.1%📈','bg':'#fffbeb'},
    {'r':'🥈','c':'000720','n':'新能泰山','p':'¥5.89','ch':'+1.0%🟢','s':'5.99','pe':'-14.7❌','roe':'-1.2%⛔','m1':'-13.0%📉','m6':'+45.8%📈','y1':'+56.7%📈','bg':'#f5f5f5'},
    {'r':'🥉','c':'601868','n':'中国能建','p':'¥3.30','ch':'+1.5%🟢','s':'5.89','pe':'25.3','roe':'1.25%⚠️','m1':'+15.7%📈','m6':'+34.5%📈','y1':'+50.5%📈','bg':'#fef9ef'},
    {'r':'4','c':'600522','n':'中天科技','p':'¥43.87','ch':'0.0%🟢','s':'5.70','pe':'46.9','roe':'2.43%⚠️','m1':'+42.9%📈','m6':'+150.3%📈','y1':'+219.9%📈'},
    {'r':'5','c':'300476','n':'胜宏科技','p':'¥374.95','ch':'-0.9%🔴','s':'5.47','pe':'79.4','roe':'7.62%','m1':'+33.2%📈','m6':'+20.4%📈','y1':'+147.2%📈'},
    {'r':'6','c':'600396','n':'华电辽能','p':'¥14.63','ch':'+6.9%🟢','s':'5.16','pe':'496.8⚠️','roe':'10.87%','m1':'+78.1%📈','m6':'+320.9%📈','y1':'+263.8%📈'},
    {'r':'7','c':'002081','n':'金螳螂','p':'¥7.64','ch':'+5.4%🟢','s':'5.14','pe':'47.5','roe':'1.27%⚠️','m1':'+112.6%📈','m6':'+112.0%📈','y1':'+98.1%📈'},
    {'r':'8','c':'603636','n':'南威软件','p':'¥11.10','ch':'+0.5%🟢','s':'4.99','pe':'-13.9❌','roe':'-2.7%⛔','m1':'+17.8%📈','m6':'-10.4%📉','y1':'-18.9%📉'},
    {'r':'9','c':'002929','n':'润建股份','p':'¥77.41','ch':'-0.3%🔴','s':'4.96','pe':'-1173❌','roe':'0.2%⚠️','m1':'+48.9%📈','m6':'+78.8%📈','y1':'+62.8%📈'},
    {'r':'10','c':'603459','n':'红板科技','p':'¥98.08','ch':'+10.0%🟢','s':'4.69','pe':'121.0⚠️','roe':'5.2%⚠️','m1':'+54.5%📈','m6':'+54.5%📈','y1':'+54.5%📈'},
    {'r':'11','c':'600726','n':'华电能源','p':'¥7.74','ch':'-0.8%🔴','s':'4.51','pe':'189.9⚠️','roe':'13.2%✅','m1':'+61.2%📈','m6':'+188.8%📈','y1':'+203.5%📈'},
    {'r':'12','c':'603618','n':'杭电股份','p':'¥41.03','ch':'+10.0%🟢','s':'4.49','pe':'-107.8❌','roe':'2.9%⚠️','m1':'+43.6%📈','m6':'+335.8%📈','y1':'+438.2%📈'},
    {'r':'13','c':'002580','n':'圣阳股份','p':'¥35.47','ch':'+3.5%🟢','s':'4.48','pe':'83.5⚠️','roe':'2.6%⚠️','m1':'+118.6%📈','m6':'+140.0%📈','y1':'+146.9%📈'},
    {'r':'14','c':'603738','n':'泰晶科技','p':'¥52.84','ch':'+2.2%🟢','s':'4.38','pe':'299.7⚠️','roe':'1.3%⚠️','m1':'+97.4%📈','m6':'+242.4%📈','y1':'+265.7%📈'},
    {'r':'15','c':'002491','n':'通鼎互联','p':'¥25.00','ch':'+10.0%🟢','s':'4.34','pe':'-178❌','roe':'2.1%⚠️','m1':'+49.5%📈','m6':'+324.1%📈','y1':'+360.1%📈'},
]

# ─── Build Top 15 table rows ──────────────────────────────────
def row(d, bg=None):
    cc = '#e74c3c' if d['ch'].startswith('+') else '#27ae60'
    bgs = f"background:{bg};" if bg else ""
    return (f'<tr style="{bgs}"><td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{d["r"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;"><span style="color:#95a5a6;font-size:12px;">{d["c"]}</span><br><b>{d["n"]}</b></td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-weight:600;">{d["p"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;color:{cc};font-weight:600;">{d["ch"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-size:15px;font-weight:700;color:#e74c3c;background:#fff3f3;border-radius:4px;">{d["s"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap;">{d["pe"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;white-space:nowrap;">{d["roe"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap;">{d["m1"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap;">{d["m6"]}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-weight:600;white-space:nowrap;">{d["y1"]}</td></tr>')

t15_rows = ""
for i, d in enumerate(TOP15):
    bg = d.get('bg') or ('#fafbfc' if i%2==0 else '#ffffff')
    t15_rows += row(d, bg) + "\n"

# ─── Build depth analysis cards ────────────────────────────────
CARDS = [
  {"rc":"🥇","rn":"1","nm":"大唐发电","cd":"601991","pr":"¥6.70","cp":"+10.0%涨停","sc":"7.09 ⭐⭐⭐ 强烈推荐",
   "vc":"PE=14.02 ✅ 估值偏低，安全边际充足<br>ROE=7.35% ⚠️ 偏低，需关注盈利能力<br>毛利率=19.66% 正常水平<br>现金流/股=0.46 正向但偏弱",
   "tc":"MA5偏离+31.9%⚠️ | RSI=89.36🔴超买 | MACD金叉📈 | 布林上轨⚠️",
   "rc2":"近1年 +90.1%🔥 | 近半年 +60.9% | 近3月 +63.3% | 近1月 +58.6%",
   "ap":"买入 <b>¥4.35</b> | 止损 ¥3.83(-12%) | 止盈T1 ¥5.22(+20%) / T2 ¥6.52(+50%)",
   "nt":"RSI超买，建议等回调回踩BOLL中轨附近","bc":"#f39c12"},
  {"rc":"🥈","rn":"2","nm":"新能泰山","cd":"000720","pr":"¥5.89","cp":"+1.0%","sc":"5.99 ⭐⭐ 保持关注",
   "vc":"PE=-14.73 ❌ 亏损中，需关注扭亏预期<br>ROE=-1.18% ⛔ 低于安全线<br>毛利率=0.34% 🔴 极低，成本压力大<br>现金流/股=0.13 正向但偏弱",
   "tc":"MA5偏离+13.5%⚠️ | RSI=66.41 | MACD金叉📈 | 布林上轨⚠️",
   "rc2":"近1年 +56.7% | 近半年 +45.8% | 近3月 +60.2% | 近1月 -13.0%📉",
   "ap":"买入 <b>¥5.89</b> | 止损 ¥5.18(-12%) | 止盈T1 ¥7.07(+20%) / T2 ¥8.83(+50%)",
   "nt":"当前价位可考虑介入","bc":"#3498db"},
  {"rc":"🥉","rn":"3","nm":"中国能建","cd":"601868","pr":"¥3.30","cp":"+1.5%","sc":"5.89 ⭐⭐ 保持关注",
   "vc":"PE=25.3 ✅ 合理区间<br>ROE=1.25% ⚠️ 偏低<br>毛利率=10.8%⚠️ 偏低<br>现金流/股=-0.54 ❌ 需警惕流动性风险",
   "tc":"MA5上方+4.8%📈 | RSI=72.22偏强 | MACD金叉📈 | 布林上轨⚠️",
   "rc2":"近1年 +50.5% | 近半年 +34.5% | 近3月 +37.9% | 近1月 +15.7%",
   "ap":"买入 <b>¥3.30</b> | 止损 ¥2.90(-12%) | 止盈T1 ¥3.96(+20%) / T2 ¥4.95(+50%)",
   "nt":"当前价位可考虑介入","bc":"#3498db"},
  {"rc":"","rn":"4","nm":"中天科技","cd":"600522","pr":"¥43.87","cp":"持平","sc":"5.70 ⭐⭐ 保持关注",
   "vc":"PE=46.9⚠️偏高<br>ROE=2.43%⚠️低<br>毛利率15.58%正常<br>现金流-0.57❌",
   "tc":"MA5偏离+14.8%⚠️ | RSI=82.5🔴超买 | MACD金叉📈",
   "rc2":"近1年 +219.9%🔥 | 近半年 +150.3% | 近3月 +104.6% | 近1月 +42.9%",
   "ap":"买入 <b>¥33.85</b> | 止损 ¥29.79(-12%) | 止盈T1 ¥40.62 / T2 ¥50.78",
   "nt":"RSI超买，建议等回踩BOLL中轨附近","bc":"#3498db"},
  {"rc":"","rn":"5","nm":"胜宏科技","cd":"300476","pr":"¥374.95","cp":"-0.9%","sc":"5.47 ⭐⭐ 保持关注",
   "vc":"PE=79.4⚠️偏高<br>ROE=7.62%偏低<br><b>毛利率34.46%✅高毛利竞争力强</b><br>现金流/股=2.43✅造血强",
   "tc":"MA5上方+8.4%📈 | RSI=71.0偏强 | MACD金叉📈",
   "rc2":"近1年 +147.2% | 近半年 +20.4% | 近3月 +42.4% | 近1月 +33.2%",
   "ap":"买入 <b>¥374.95</b> | 止损 ¥329.96(-12%) | 止盈T1 ¥449.94 / T2 ¥562.42",
   "nt":"当前价位可考虑介入","bc":"#3498db"},
]

def card(c):
    chg = '#e74c3c' if '+' in c['cp'] else ('#27ae60' if '-' in c['cp'] else '#555')
    return (f'<div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-left:5px solid {c["bc"]};">'
            f'<h3 style="margin:0 0 16px;font-size:17px;color:#2c3e50;">{c["rc"]} #{c["rn"]} {c["nm"]} ({c["cd"]})</h3>'
            f'<div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">'
            f'<span style="background:#f8f9fa;border-radius:8px;padding:8px 14px;font-size:13px;"><b>价格:</b> {c["pr"]} <span style="color:{chg};">({c["cp"]})</span></span>'
            f'<span style="background:#fff3f3;border-radius:8px;padding:8px 14px;font-size:13px;color:#e74c3c;"><b>得分:</b> {c["sc"]}</span></div>'
            f'<div style="background:#f0faf0;border-radius:8px;padding:14px;margin-bottom:12px;">'
            f'<h4 style="margin:0 0 8px;font-size:13px;color:#27ae60;">💎 估值解读</h4>'
            f'<div style="font-size:13px;line-height:1.8;color:#555;">{c["vc"]}</div></div>'
            f'<div style="background:#fff8e1;border-radius:8px;padding:14px;margin-bottom:12px;">'
            f'<h4 style="margin:0 0 8px;font-size:13px;color:#f39c12;">📐 技术面</h4>'
            f'<div style="font-size:13px;line-height:1.8;color:#555;">{c["tc"]}</div></div>'
            f'<div style="background:#eef6ff;border-radius:8px;padding:14px;margin-bottom:12px;">'
            f'<h4 style="margin:0 0 8px;font-size:13px;color:#3498db;">📈 收益追踪</h4>'
            f'<div style="font-size:13px;line-height:1.8;color:#555;">{c["rc2"]}</div></div>'
            f'<div style="background:#fdf2f0;border-radius:8px;padding:14px;margin-bottom:12px;">'
            f'<h4 style="margin:0 0 8px;font-size:13px;color:#e74c3c;">💰 操作价位</h4>'
            f'<div style="font-size:13px;line-height:1.8;color:#555;">{c["ap"]}</div></div>'
            f'<p style="margin:0;padding:8px 12px;background:#f9f9f9;border-radius:6px;font-size:13px;color:#777;">📝 {c["nt"]}</p></div>')

card_html = "\n".join(card(c) for c in CARDS)

# ─── #6-#10 summary rows ──────────────────────────────────────
S6_10 = [
  ('#6','华电辽能 (600396)','5.16','⭐⭐ 波段','¥9.46','¥8.32(-12%)','¥11.35 / ¥14.19'),
  ('#7','金螳螂 (002081)','5.14','⭐⭐ 波段','¥7.64','¥6.72(-12%)','¥9.17 / ¥11.46'),
  ('#8','南威软件 (603636)','4.99','⭐ 观望','¥11.10','¥9.77(-12%)','¥13.32 / ¥16.65'),
  ('#9','润建股份 (002929)','4.96','⭐ 观望','¥77.41','¥68.12(-12%)','¥92.89 / ¥116.11'),
  ('#10','红板科技 (603459)','4.69','⭐ 观望','¥98.08','¥88.27(-10%)','¥117.70 / ¥147.12'),
]
s6_rows = ""
for i,r in enumerate(S6_10):
    bg='#fafbfc' if i%2==0 else '#ffffff'
    s6_rows += (f'<tr style="background:{bg};"><td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{r[0]}</td>'
                f'<td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>{r[1]}</b></td>'
                f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:700;color:#e74c3c;">{r[2]}</td>'
                f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;">{r[3]}</td>'
                f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-weight:600;">{r[4]}</td>'
                f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;color:#e74c3c;">{r[5]}</td>'
                f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap;">{r[6]}</td></tr>\n')

# ─── Conservative portfolio rows ──────────────────────────────
CONSV = [
  ('1','大唐发电 (601991)','[电力] 成长弹性','~33%','7.09','14.0','7.35%','¥4.35 / ¥3.83 / ¥5.22 / ¥6.52'),
  ('2','中天科技 (600522)','[科技] 投机观察','~33%','5.70','46.9','2.43%','¥33.85 / ¥29.79 / ¥40.62 / ¥50.78'),
  ('3','胜宏科技 (300476)','[科技] 成长弹性','~33%','5.47','79.4','7.62%','¥374.95 / ¥329.96 / ¥449.94 / ¥562.42'),
]
consv_rows = ""
for i,r in enumerate(CONSV):
    bg='#f7fbff' if i%2==0 else '#ffffff'
    consv_rows += (f'<tr style="background:{bg};"><td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{r[0]}</td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>{r[1]}</b></td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;">{r[2]}</td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{r[3]}</td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-size:14px;font-weight:700;color:#e74c3c;">{r[4]}</td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;">{r[5]}</td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;">{r[6]}</td>'
                   f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-size:12px;white-space:nowrap;">{r[7]}</td></tr>\n')

# ─── Aggressive portfolio rows ────────────────────────────────
AGGRS = [
  ('1','大唐发电 (601991)','成长','~28%','7.09','+90%🔥','¥4.35 / ¥3.83 / ¥5.22 / ¥6.52'),
  ('2','新能泰山 (000720)','投机','~17%','5.99','+57%📈','¥5.89 / ¥5.18 / ¥7.07 / ¥8.83'),
  ('3','中国能建 (601868)','投机','~17%','5.89','+50%📈','¥3.30 / ¥2.90 / ¥3.96 / ¥4.95'),
  ('4','中天科技 (600522)','投机','~17%','5.70','+220%🔥','¥33.85 / ¥29.79 / ¥40.62 / ¥50.78'),
  ('5','胜宏科技 (300476)','成长','~21%','5.47','+147%🔥','¥374.95 / ¥329.96 / ¥449.94 / ¥562.42'),
]
aggr_rows = ""
for i,r in enumerate(AGGRS):
    bg='#fffbf5' if i%2==0 else '#ffffff'
    aggr_rows += (f'<tr style="background:{bg};"><td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{r[0]}</td>'
                  f'<td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>{r[1]}</b></td>'
                  f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;">{r[2]}</td>'
                  f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{r[3]}</td>'
                  f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-size:14px;font-weight:700;color:#e74c3c;">{r[4]}</td>'
                  f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-weight:600;white-space:nowrap;">{r[5]}</td>'
                  f'<td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-size:12px;white-space:nowrap;">{r[6]}</td></tr>\n')

# ─── Final HTML assembly ──────────────────────────────────────
html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:24px;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#333;">

<div style="max-width:800px;margin:0 auto;background:linear-gradient(135deg,#27ae60 0%,#2ecc71 50%,#1abc9c 100%);border-radius:16px;padding:40px 32px;text-align:center;box-shadow:0 8px 24px rgba(39,174,96,0.3);">
  <h1 style="margin:0;font-size:32px;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,0.15);">📈 盘前选股分析报告</h1>
  <p style="margin:12px 0 0;color:rgba(255,255,255,0.9);font-size:14px;">⏰ 2026-05-12 11:01 &nbsp;|&nbsp; v0.9.4 统一打分规则 &nbsp;|&nbsp; 基于动态池34只实时数据</p>
  <div style="margin-top:16px;display:inline-block;background:rgba(255,255,255,0.2);border-radius:20px;padding:6px 18px;font-size:13px;color:#fff;">🥬 菜菜的量化世界</div>
</div>

<div style="max-width:800px;margin:24px auto 0;background:#fff;border-radius:16px;padding:28px;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
  <h2 style="margin:0 0 20px;font-size:20px;color:#2c3e50;border-left:4px solid #27ae60;padding-left:14px;">📊 Panel 1 · Top 15 选股总览</h2>
  <div style="overflow-x:auto;">
  <table style="width:100%;border-collapse:separate;border-spacing:0;font-size:13px;">
    <thead><tr>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:center;color:#495057;white-space:nowrap;">#</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:left;color:#495057;white-space:nowrap;">代码/名称</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:right;color:#495057;white-space:nowrap;">价格</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:center;color:#495057;white-space:nowrap;">涨跌</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:center;color:#495057;white-space:nowrap;">得分</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:right;color:#495057;white-space:nowrap;">PE</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:center;color:#495057;white-space:nowrap;">ROE%</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:right;color:#495057;white-space:nowrap;">近1月</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:right;color:#495057;white-space:nowrap;">近半年</th>
      <th style="background:#f8f9fa;padding:12px 8px;border-bottom:2px solid #dee2e6;text-align:right;color:#495057;white-space:nowrap;">近1年</th>
    </tr></thead><tbody>
{t15_rows}
    </tbody></table></div></div>

<div style="max-width:800px;margin:24px auto 0;">
  <h2 style="font-size:20px;color:#2c3e50;border-left:4px solid #3498db;padding-left:14px;margin-bottom:20px;">🔍 Panel 2 · Top 10 个股深度分析</h2>
{card_html}

  <div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <h3 style="margin:0 0 16px;font-size:17px;color:#2c3e50;">#6 ~ #10 简表</h3>
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:separate;border-spacing:0;font-size:13px;">
      <thead><tr>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:center;color:#495057;border-bottom:2px solid #dee2e6;">排名</th>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:left;color:#495057;border-bottom:2px solid #dee2e6;">股票</th>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:center;color:#495057;border-bottom:2px solid #dee2e6;">得分</th>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:center;color:#495057;border-bottom:2px solid #dee2e6;">操作建议</th>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:right;color:#495057;border-bottom:2px solid #dee2e6;">买入价</th>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:center;color:#495057;border-bottom:2px solid #dee2e6;">止损</th>
        <th style="background:#f8f9fa;padding:10px 8px;text-align:right;color:#495057;border-bottom:2px solid #dee2e6;white-space:nowrap;">止盈T1/T2</th>
      </tr></thead><tbody>
{s6_rows}
      </tbody></table></div></div></div>

<div style="max-width:800px;margin:24px auto 0;">
  <h2 style="font-size:20px;color:#2c3e50;border-left:4px solid #9b59b6;padding-left:14px;margin-bottom:20px;">🎯 Panel 3 · 投资组合配置建议</h2>

  <div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-top:4px solid #3498db;margin-bottom:20px;">
    <h3 style="margin:0 0 16px;font-size:17px;color:#3498db;">📦 保守型（最多3只，稳健为主）</h3>
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:separate;border-spacing:0;font-size:13px;">
      <thead><tr>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:center;color:#2471a3;border-bottom:2px solid #aed6f1;">#</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:left;color:#2471a3;border-bottom:2px solid #aed6f1;">股票</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:center;color:#2471a3;border-bottom:2px solid #aed6f1;">类型</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:center;color:#2471a3;border-bottom:2px solid #aed6f1;">仓位</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:center;color:#2471a3;border-bottom:2px solid #aed6f1;">得分</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:right;color:#2471a3;border-bottom:2px solid #aed6f1;">PE</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:center;color:#2471a3;border-bottom:2px solid #aed6f1;">ROE</th>
        <th style="background:#ebf5fb;padding:10px 8px;text-align:right;color:#2471a3;border-bottom:2px solid #aed6f1;white-space:nowrap;">💰 买入/止损/T1/T2</th>
      </tr></thead><tbody>
{consv_rows}
      </tbody></table></div></div>

  <div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-top:4px solid #e67e22;margin-bottom:20px;">
    <h3 style="margin:0 0 16px;font-size:17px;color:#e67e22;">📦 进取型（最多5只，均衡配置）</h3>
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:separate;border-spacing:0;font-size:13px;">
      <thead><tr>
        <th style="background:#fef5e7;padding:10px 8px;text-align:center;color:#ca6f1e;border-bottom:2px solid #fad7a0;">#</th>
        <th style="background:#fef5e7;padding:10px 8px;text-align:left;color:#ca6f1e;border-bottom:2px solid #fad7a0;">股票</th>
        <th style="background:#fef5e7;padding:10px 8px;text-align:center;color:#ca6f1e;border-bottom:2px solid #fad7a0;">类型</th>
        <th style="background:#fef5e7;padding:10px 8px;text-align:center;color:#ca6f1e;border-bottom:2px solid #fad7a0;">仓位</th>
        <th style="background:#fef5e7;padding:10px 8px;text-align:center;color:#ca6f1e;border-bottom:2px solid #fad7a0;">得分</th>
        <th style="background:#fef5e7;padding:10px 8px;text-align:right;color:#ca6f1e;border-bottom:2px solid #fad7a0;white-space:nowrap;">近1年涨幅</th>
        <th style="background:#fef5e7;padding:10px 8px;text-align:right;color:#ca6f1e;border-bottom:2px solid #fad7a0;white-space:nowrap;">💰 买入/止损/T1/T2</th>
      </tr></thead><tbody>
{aggr_rows}
      </tbody></table></div></div>

  <div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-left:5px solid #e74c3c;margin-bottom:20px;">
    <h3 style="margin:0 0 16px;font-size:17px;color:#e74c3c;">⚠️ 风险提示</h3>
    <table style="width:100%;border-collapse:separate;border-spacing:0;font-size:13px;">
      <thead><tr>
        <th style="background:#fdedec;padding:10px 8px;text-align:left;color:#c0392b;border-bottom:2px solid #f5b7b1;">股票</th>
        <th style="background:#fdedec;padding:10px 8px;text-align:left;color:#c0392b;border-bottom:2px solid #f5b7b1;">风险项</th>
      </tr></thead><tbody>
        <tr><td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>🏆 大唐发电</b></td><td style="padding:10px 8px;border-bottom:1px solid #eee;">ROE偏低(7.35%)，关注盈利改善</td></tr>
        <tr style="background:#fafafa;"><td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>🔥 新能泰山</b></td><td style="padding:10px 8px;border-bottom:1px solid #eee;">PE为负存在亏损风险; ROE过低(-1.18%)</td></tr>
        <tr><td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>📊 中国能建</b></td><td style="padding:10px 8px;border-bottom:1px solid #eee;">ROE过低(1.25%)，盈利能力弱</td></tr>
        <tr style="background:#fafafa;"><td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>💡 中天科技</b></td><td style="padding:10px 8px;border-bottom:1px solid #eee;">ROE过低(2.43%); 短期涨幅过大注意回调</td></tr>
        <tr><td style="padding:10px 8px;border-bottom:1px solid #eee;"><b>🔧 胜宏科技</b></td><td style="padding:10px 8px;border-bottom:1px solid #eee;">PE偏高(79.43)需高成长支撑; ROE偏低</td></tr>
      </tbody></table>
    <p style="margin:16px 0 0;padding:10px 14px;background:#fff3f3;border-radius:8px;font-size:14px;color:#e74c3c;font-weight:600;">⚠️ 投机股3只，整体风险偏高</p>
  </div>

  <div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-left:5px solid #f39c12;">
    <h3 style="margin:0 0 16px;font-size:17px;color:#f39c12;">💡 投资建议</h3>
    <ol style="font-size:14px;line-height:2;color:#555;padding-left:20px;margin:0;">
      <li>以上仅为基于量化模型的筛选结果，<b style="color:#e74c3c;">不构成投资建议</b></li>
      <li>建议分批建仓，控制单只股票仓位不超过 <b>30%</b></li>
      <li>设置止损位（通常 <b>-8% ~ -12%</b>）和止盈目标（<b>+20% ~ +50%</b>）</li>
      <li>关注个股财报季表现及行业政策变化</li>
    </ol>
  </div>
</div>

<div style="max-width:800px;margin:24px auto 0;text-align:center;padding:20px;background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
  <p style="margin:0;font-size:13px;color:#95a5a6;">📋 本报告由<b>菜菜选股器 v0.9.4</b>自动生成 &nbsp;|&nbsp; 基于动态池34只实时数据</p>
  <p style="margin:8px 0 0;font-size:12px;color:#bbb;">🥬 菜菜的量化世界，仅供参考，投资有风险 &nbsp;|&nbsp; Generated at 2026-05-12 11:59</p>
</div>

</body></html>'''

# ─── Send email ──────────────────────────────────────────────
msg = MIMEMultipart('alternative')
msg['From'] = '65343914@qq.com'
msg['To'] = 'zscyun@hotmail.com'
msg['Subject'] = '📈 盘前选股分析报告 - 2026-05-12 (菜菜 v0.9.4)'

msg.attach(MIMEText(html_content, 'html', 'utf-8'))

part = MIMEBase('text', 'plain')
part.set_payload(cli_output)
encoders.encode_base64(part)
part.add_header('Content-Disposition', 'attachment', filename='daily-report-cli-output.txt')
msg.attach(part)

print("📧 正在发送邮件...")
server = smtplib.SMTP('smtp.qq.com', 587)
server.ehlo()
server.starttls()
server.login('65343914@qq.com', 'oltvejfivexzbhca')
server.sendmail('65343914@qq.com', ['zscyun@hotmail.com'], msg.as_string())
server.quit()

print("✅ 邮件发送成功！🥬")
print(f"   📎 附件: daily-report-cli-output.txt ({len(cli_output)} bytes)")
print(f"   📊 HTML正文: {len(html_content)} chars")
