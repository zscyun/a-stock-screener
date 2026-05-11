#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股综合分析CLI - TuShare + AkShare 组合技能
============================================
结合两个数据源的互补优势：
- TuShare → 实时行情（免费、秒回）  
- AkShare(THS) → 财务数据、估值指标

Usage:
    python a_stock_cli.py run --text "分析贵州茅台"
    python a_stock_cli.py fetch-realtime --code "600519"
    python a_stock_cli.py fetch-financials --code "300750"
    python a_stock_cli.py analyze --code "600519" --type "估值+趋势"
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd


def safe_serializable(obj: Any) -> Any:
    """将Pandas/NumPy对象转换为JSON可序列化格式"""
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        return obj.to_dict('records') if hasattr(obj, 'to_dict') else str(obj)
    elif isinstance(obj, dict):
        return {k: safe_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_serializable(i) for i in obj]
    return obj


# ─── TuShare 实时行情（免费无需token）───────────────────────────────
def get_realtime_quote(code: str) -> Optional[Dict[str, Any]]:
    """获取实时行情 - TuSource免费接口"""
    try:
        import tushare as ts
        df = ts.get_realtime_quotes(code)
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        price = float(row['price'])
        pre_close = float(row['pre_close'])

        return {
            'code': code,
            'name': str(row.get('name', '')),
            'price': price,
            'change': round(price - pre_close, 2),
            'change_pct': round((price / pre_close - 1) * 100, 2),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'volume': int(row['volume']),
            'amount': float(row['amount']),
            'bid': float(row['bid']),
            'ask': float(row['ask']),
            'time': str(row.get('time', '')),
            'source': 'tushare'
        }
    except Exception as e:
        print(f"⚠️ TuShare实时行情失败: {e}", file=sys.stderr)
        return None


# ─── AkShare THS源 - 财务数据 & 估值指标─────────────────────────────
def get_financials(code: str, days: int = 60) -> Dict[str, Any]:
    """获取财务数据与估值指标 - AkShare THS源"""
    results: Dict[str, Any] = {}

    # ── 1. 历史K线（尝试多源，AkShare新浪源最稳）───────────────
    kline_df = None
    
    try:
        import akshare as ak
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 尝试新浪源（最稳定）→ 东财源 → web fallback
        for source_name, fetch_fn in [
            ('sina', lambda: ak.stock_zh_a_daily(symbol=f"{'sh' if code.startswith('6') else 'sz'}{code}")),
            ('eastmoney', lambda: ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')),
        ]:
            try:
                kline_df = fetch_fn()
                if source_name == 'sina' and not kline_df.empty:
                    # 新浪源返回大量数据，取最近N天
                    kline_df = kline_df.tail(days)
                break
            except Exception as e_source:
                print(f"   ⚠️ K线({source_name})失败: {e_source}", file=sys.stderr)
        else:
            # 所有源都失败，用web fallback
            kline_df = _fetch_kline_web(code, days)

        if kline_df is not None and not kline_df.empty:
            results['kline'] = {
                'count': len(kline_df),
                'data': safe_serializable(kline_df.tail(10)),  # 只存最近10条
                'full_for_technicals': safe_serializable(kline_df)  # 保留完整数据给技术计算
            }
    except ImportError:
        pass

    # ── 2. 财务摘要（同花顺）───────────────
    try:
        import akshare as ak
        fin = ak.stock_financial_abstract_ths(
            symbol=code, 
            indicator='按报告期'
        )
        if not fin.empty:
            results['financials'] = {
                'count': len(fin),
                'columns': list(fin.columns[:10]),
                'data': safe_serializable(fin.head(4))
            }
    except Exception as e_fin:
        print(f"   ⚠️ 财务摘要获取失败: {e_fin}", file=sys.stderr)

    return results


def _fetch_kline_web(code: str, days: int = 60) -> Optional[pd.DataFrame]:
    """Web fallback: 通过腾讯API获取K线数据"""
    try:
        import urllib.request
        
        prefix = 'sh' if code.startswith('6') else 'sz'
        url = (f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
               f"param={prefix}{code},day,,,,{days},qfq")

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        if 'data' in data and code in data['data']:
            day_data = data['data'][code].get('day', [])
            if day_data:
                df = pd.DataFrame(day_data, columns=['time', 'open', 'close', 
                                                     'high', 'low', 'volume'])
                for col in ['open', 'close', 'high', 'low']:
                    df[col] = df[col].astype(float)
                df['volume'] = df['volume'].astype(int)
                return df

    except Exception as e:
        print(f"   ⚠️ K线Web fallback也失败: {e}", file=sys.stderr)
    
    return None


# ─── 技术指标计算（本地Pandas）─────────────────────────────────────
def calc_technicals(close_prices: List[float]) -> Dict[str, Any]:
    """基于价格序列计算常用技术指标"""
    tech: Dict[str, Any] = {}
    close = pd.Series(close_prices)

    try:
        # ── 均线系统（MA5/10/20）───────────────
        for window in [5, 10, 20]:
            if len(close) >= window:
                tech[f'MA{window}'] = round(float(close.rolling(window).mean().iloc[-1]), 2)

        # ── RSI（相对强弱指标，14日）───────────────
        if len(close) >= 15:
            delta = close.diff()
            gain = delta[delta > 0].rolling(14).mean().iloc[-1] if (delta > 0).any() else 0
            loss = (-delta[delta < 0]).rolling(14).mean().iloc[-1] if (delta < 0).any() else 0.01
            rs = float(gain) / max(float(loss), 0.01)
            rsi = round(100 - (100 / (1 + rs)), 2)
            tech['RSI_14'] = min(max(rsi, 0), 100)

        # ── MACD（指数平滑移动平均线）───────────────
        if len(close) >= 35:
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            dif_series = ema12 - ema26
            dea_series = dif_series.ewm(span=9).mean()
            tech['MACD'] = {
                'DIF': round(float(dif_series.iloc[-1]), 3),
                'DEA': round(float(dea_series.iloc[-1]), 3),
                'HIST': round(2 * float((dif_series - dea_series).iloc[-1]), 3)
            }

        # ── 布林带（BOLL，20日）───────────────
        if len(close) >= 20:
            ma20 = float(close.rolling(20).mean().iloc[-1])
            std20 = float(close.rolling(20).std().iloc[-1])
            tech['BOLL'] = {
                'upper': round(ma20 + 2 * std20, 2),
                'mid': round(ma20, 2),
                'lower': round(ma20 - 2 * std20, 2)
            }

        # ── KDJ（随机指标）───────────────  
        if len(close) >= 9:
            low_9 = float(close.rolling(9).min().iloc[-1])
            high_9 = float(close.rolling(9).max().iloc[-1])
            rsv = (float(close.iloc[-1]) - low_9) / max(high_9 - low_9, 0.01) * 100
            tech['KDJ_RSV'] = round(rsv, 2)

    except Exception as e:
        print(f"   ⚠️ 技术指标计算警告: {e}", file=sys.stderr)

    return tech


# ─── 综合分析报告生成───────────────────────────────────────────────
def generate_report(code: str, analysis_type: str = "full") -> Dict[str, Any]:
    """生成完整的个股分析报告"""
    report: Dict[str, Any] = {
        'code': code,
        'timestamp': datetime.now().isoformat(),
        'analysis_type': analysis_type,
    }

    # ── 1. 实时行情───────────────
    print(f"\n📊 正在获取实时行情...", file=sys.stderr)
    quote = get_realtime_quote(code)

    if not quote:
        report['error'] = '无法获取实时行情'
        return report

    report['realtime'] = quote

    # ── 2. 财务数据 & K线───────────────
    print(f"📊 正在获取财务与K线数据...", file=sys.stderr)
    fin_data = get_financials(code, days=60)

    if 'kline' in fin_data and fin_data['kline']['data']:
        # 用完整数据计算技术指标（不是只取10条）
        klines_full = fin_data['kline'].get('full_for_technicals', fin_data['kline']['data'])
        klines_df = pd.DataFrame(klines_full)
        
        # 查找收盘价列（兼容不同数据源）
        close_col = None
        for col in ['close', 'Close', '收盘', '收盘价', 'c']:
            if col in klines_df.columns:
                close_col = col
                break
        
        if close_col:
            techs = calc_technicals(klines_df[close_col].astype(float).tolist())
            report['technicals'] = techs

    # ── 3. 财务摘要───────────────
    if 'financials' in fin_data and fin_data['financials']['data']:
        report['financials_summary'] = {
            'total_reports': fin_data['financials']['count'],
            'latest_quarters': safe_serializable(fin_data['financials']['data'])
        }

    return report


# ─── CLI入口────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='A股综合分析CLI - TuShare + AkShare组合',
        formatter_class=argparse.RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command')

    # ── 1. run (自然语言查询)───────────────
    p_run = subparsers.add_parser('run', help='自然语言个股分析')
    p_run.add_argument('--text', '-t', type=str, required=True, 
                      help='分析请求，如"分析贵州茅台"或"看看宁德时代估值"')

    # ── 2. fetch-realtime (实时行情)───────────────
    p_rt = subparsers.add_parser('fetch-realtime', help='获取实时行情')
    p_rt.add_argument('--code', '-c', type=str, required=True,
                     help='股票代码，如600519、300750')

    # ── 3. fetch-financials (财务数据)───────────────  
    p_fin = subparsers.add_parser('fetch-financials', help='获取财务与K线数据')
    p_fin.add_argument('--code', '-c', type=str, required=True,
                      help='股票代码，如600519、300750')

    # ── 4. analyze (综合分析)───────────────
    p_analyze = subparsers.add_parser('analyze', help='综合分析报告')
    p_analyze.add_argument('--code', '-c', type=str, required=True,
                          help='股票代码，如600519、300750')
    p_analyze.add_argument('--type', default='full',
                          choices=['full', '估值', '趋势', '技术'],
                          help='分析类型（默认full全量）')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # ─── 简单名称→代码映射表───────────────
    name_to_code = {
        '贵州茅台': '600519', '茅台': '600519',
        '平安银行': '000001', '平安': '000001',
        '宁德时代': '300750', '宁德': '300750', 
        '五粮液': '000858',
        '招商银行': '600036', '招行': '600036',
        '比亚迪': '002594',
    }

    def resolve_code(text: str) -> Optional[str]:
        """从自然语言中提取股票代码"""
        for name, code in name_to_code.items():
            if name in text:
                return code
        
        # 尝试提取6位数字
        import re
        match = re.search(r'(\d{6})', text)
        if match:
            return match.group(1)

        return None

    # ─── 执行───────────────
    
    if args.command == 'run':
        code = resolve_code(args.text)
        if not code:
            print(f"❌ 无法识别股票，请提供代码或名称", file=sys.stderr)
            sys.exit(1)

        report = generate_report(code)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=safe_serializable))

    elif args.command == 'fetch-realtime':
        quote = get_realtime_quote(args.code)
        if not quote:
            print(f"❌ 获取失败", file=sys.stderr)
            sys.exit(1)

        print(json.dumps(quote, ensure_ascii=False, indent=2))

    elif args.command == 'fetch-financials':
        data = get_financials(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2, default=safe_serializable))

    elif args.command == 'analyze':
        report = generate_report(args.code, analysis_type=args.type)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=safe_serializable))


if __name__ == '__main__':
    main()
