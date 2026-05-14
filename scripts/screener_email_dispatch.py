#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screener Email Dispatch - 主入口 (v2.0)

分层架构整合版：
数据源 → [ReportReader] → [StockData对象] → [HTMLEmailOutputter] → SMTP发送

不再硬编码任何股票数据，完全动态从当天报告解析。
按爸比的设计重写。
"""

import os, sys, subprocess, argparse
from datetime import date

# 确保脚本目录在 PATH 上以便导入模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from email_core_models import ReportReader, ReportContext, StockData
from email_html_outputter import HTMLEmailOutputter


# ─── 路径配置 ──────────────────────────────────────────────
WORKSPACE_ROOT = os.path.join(SCRIPT_DIR, '..', '..', '..')
REPORTS_DIR = os.path.join(WORKSPACE_ROOT, 'reports')
SCREENER_CLI = os.path.join(SCRIPT_DIR, 'stock_screen.py')


def find_today_report():
    """找到今天的报告文件，不存在则返回 None"""
    today_file = os.path.join(REPORTS_DIR, f"daily-report-{date.today().isoformat()}.txt")
    if os.path.exists(today_file):
        return today_file
    # fallback: 找最新 .txt
    try:
        txt_files = sorted([f for f in os.listdir(REPORTS_DIR) 
                           if f.startswith('daily-report-') and f.endswith('.txt')], reverse=True)
        if txt_files:
            return os.path.join(REPORTS_DIR, txt_files[0])
    except OSError:
        pass
    return None


def run_screener_cli(chase_mode=False):
    """运行 screener CLI 生成当天报告"""
    print(f"[dispatch] 运行 screener CLI...")
    cmd = [sys.executable, SCREENER_CLI, 'screen']
    
    if chase_mode:
        cmd.append('--chase-mode')
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[dispatch] ❌ screener CLI 失败 (exit {result.returncode})")
        print(result.stderr[-500:])  # 打印最后500字符的错误信息
        return False
    
    print("[dispatch] ✅ screener 完成")
    return True


def main():
    parser = argparse.ArgumentParser(description='Screener Email Dispatch v2.0')
    parser.add_argument('--no-run', action='store_true', 
                       help='不自动运行 screener，只用现有报告')
    parser.add_argument('--chase-mode', action='store_true',
                       help='以追涨模式运行 screener')
    parser.add_argument('--dry-run', action='store_true',
                       help='只渲染HTML预览，不发邮件')
    args = parser.parse_args()

    # ── Step 1: 确保报告存在 ───────────────────────────────
    report_path = find_today_report()
    
    if not report_path and not args.no_run:
        print(f"[dispatch] 今日报告不存在，自动运行 screener...")
        run_screener_cli(chase_mode=args.chase_mode)
        report_path = find_today_report()
    
    if not report_path:
        print("[dispatch] ❌ 无可用报告")
        sys.exit(1)
    
    print(f"[dispatch] 使用报告: {report_path}")

    # ── Step 2: ReportReader 解析 ──────────────────────────
    reader = ReportReader()
    context, stocks = reader.parse_report(report_path)
    
    if not stocks:
        print("[dispatch] ❌ 未能从报告中提取股票数据")
        sys.exit(1)
    
    print(f"[dispatch] ✅ 解析完成: {len(stocks)} 只股票")

    # ── Step 3: HTMLEmailOutputter 渲染 + 发送 ─────────────
    outputter = HTMLEmailOutputter()
    
    if args.dry_run:
        html = outputter.render(context, stocks)
        preview_path = os.path.join(REPORTS_DIR, 'email-preview.html')
        with open(preview_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"[dispatch] ✅ HTML预览已生成: {preview_path}")
    else:
        success = outputter.output(context, stocks)
        if success:
            print("[dispatch] 🎉 邮件发送成功！")
        else:
            print("[dispatch] ❌ 邮件发送失败")
            sys.exit(1)


if __name__ == "__main__":
    main()
