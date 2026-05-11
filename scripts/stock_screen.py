#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量版股票筛选器 v0.9 - 混合源方案
=====================================
采用akshare多源数据 + Exa可选增强:
1. akshare三源发现热门标的 (stock_hot_rank_em/zt_pool_em/全量扫描)
2. TuShare/AkShare 个股分析确认 (估值+财务+K线)
3. Exa搜索近期新闻情绪 (可选，需mcporter配置)

Usage:
    # 快速模式:直接分析指定股票池
    python stock_screen.py analyze --codes "600519,300750,601318"

    # 筛选模式:根据条件过滤预定义热门股
    python stock_screen.py screen --limit 5

    # 搜索模式:从近期强势板块入手
    python stock_screen.py sectors

    # JSON 输出(给 LLM 用)
    python stock_screen.py analyze --codes "600519" --format json
"""

import argparse
import json
import subprocess
import sys
import time
from typing import Dict, List, Optional, Any, Tuple
try:
    from urllib.request import urlopen
except ImportError:
    pass

# Pandas for backtest (optional)
try:
    import pandas as pd
except ImportError:
    pd = None
from pathlib import Path
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
import io as _io_module
from contextlib import redirect_stdout as _redirect_stdout

# ═══════════════════════════════════════════════
# 动态池管理 (v7) — 零硬编码，三层漏斗筛选  
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
# 动态池管理 (v7) — 零硬编码，三层漏斗筛选
# ═══════════════════════════════════════════════

POOL_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hot_pool_state.json')

# L1 快速初筛阈值
L1_MIN_MARKET_CAP = 5_000_000_000       # 市值>50亿 (排除壳股)
L1_MAX_TURN_RATE = 20.0                  # 换手率<20% (排除异常波动)

# P1: L1 基本面预筛阈值 (利用缓存财务数据快速过滤)
L1_MIN_GROSS_MARGIN = 10.0              # 毛利率>10% (制造业底线)
L1_MAX_DEBT_RATIO = 85.0                 # 负债率<85% (排除高风险)
L1_LOSS_YEARS_LIMIT = 2                  # 连续亏损年数<=2

# L2 候选池大小  
L2_CANDIDATE_COUNT = 80                  # K线分析后保留80只

# L3 最终入池大小
POOL_MIN_SIZE = 25                       # 最少25只(保证覆盖面)
POOL_MAX_SIZE = 35                       # 最多35只(控制财务查询耗时)

# 活动分数系统 (v7)
ACTIVITY_NEW_ENTRY = 2                   # 新入库初始分
ACTIVITY_MAX = 5                           # 活动分数上限
ACTIVITY_DISCOVERED_BONUS = 1            # 本次发现+1
ACTIVITY_NOT_FOUND_PENALTY = 1          # 未发现-1  
ACTIVITY_OBSERVE_THRESHOLD = 1           # ≤1标记观察区
ACTIVITY_REMOVE_THRESHOLD = 0            # =0直接剔除

# 缓存过期时间 (秒)
CACHE_TTL_L1L2 = 3600                    # L1/L2缓存1小时
CACHE_TTL_L3 = 18000                     # L3财务数据半天

# 估值/财务API结果缓存（避免重复查询）
VALUATION_CACHE: Dict[str, Any] = {}
FA_CACHE: Dict[str, Any] = {}

# ─── 本地持久化缓存（方案A：akshare不可达时读JSON缓存） ───
_VAL_FILE = Path(__file__).parent / "_valuation_state.json"
_FA_FILE = Path(__file__).parent / "_financial_abstract_state.json"
_CACHE_TTL_SECONDS = 5 * 86400  # 5天有效期

def _load_persistent_cache(json_file: Path) -> Dict:
    """从JSON文件加载持久化缓存"""
    try:
        if json_file.exists():
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ 读取缓存文件失败: {e}", file=sys.stderr)
    return {}

def _save_persistent_cache(json_file: Path, cache_data: Dict):
    """保存缓存到JSON文件"""
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存缓存文件失败: {e}", file=sys.stderr)




def _discover_l1_candidates() -> List[Dict[str, Any]]:
    """
    L1 快速初筛：全量扫描A股，过滤出300-500只候选
    
    数据源: akshare stock_zh_a_spot_em (一次性返回全部~5000只)
    耗时: ~2秒（纯内存计算）
    
    Returns: [{code, name, price, change_pct, market_cap, ...}, ...]
    """
    try:
        import akshare as ak
        
        # 获取全量实时行情 (~5000行)
        df = ak.stock_zh_a_spot_em()
        
        if df is None or df.empty:
            print("⚠️ L1: 获取A股实时数据失败", file=sys.stderr)
            return []
        
        candidates = []
        for _, row in df.iterrows():
            try:
                code = str(row.get('代码', ''))
                if not code.isdigit() or len(code) != 6:
                    continue
                    
                name = str(row.get('名称', '')).strip()
                
                # ST股直接过滤
                if 'st' in name.lower() or '*st' in name.lower():
                    continue
                
                price_str = row.get('最新价', '0')
                try:
                    price = float(price_str)
                except:
                    continue
                    
                change_pct_str = row.get('涨跌幅', '0')
                try:
                    change_pct = float(change_pct_str)
                except:
                    change_pct = 0
                
                # 市值过滤 (单位:元)
                mc_str = str(row.get('总市值', '0'))
                try:
                    market_cap = float(mc_str.replace(',', '').replace('%', '')) if mc_str != '--' else 0
                except:
                    market_cap = 0
                
                # 换手率过滤
                tr_str = row.get('换手率', '0')  
                try:
                    turn_rate = float(tr_str) if tr_str and str(tr_str) != '--' else 0
                except:
                    turn_rate = 0
                
                # L1 筛选条件
                if market_cap < L1_MIN_MARKET_CAP:
                    continue
                if turn_rate > L1_MAX_TURN_RATE:
                    continue
                
                # P1: L1 基本面预筛 (有缓存财务数据时才执行)
                fa = FA_CACHE.get(code, None)
                if fa is not None:
                    gross_margin = fa.get('gross_margin', None)
                    debt_ratio = fa.get('debt_ratio', None)
                    net_profit_margin = fa.get('net_profit_margin', None)
                    
                    # 连续两年亏损 → 排除
                    if gross_margin is not None and net_profit_margin is not None:
                        if net_profit_margin < -10:  # 净利润率<-10%视为严重亏损
                            continue
                    # 毛利率太低 → 排除 (制造业底线)
                    if gross_margin is not None and gross_margin < L1_MIN_GROSS_MARGIN:
                        continue
                    # 负债率太高 → 排除
                    if debt_ratio is not None and debt_ratio > L1_MAX_DEBT_RATIO:
                        continue
                    
                candidates.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'change_pct': change_pct,
                    'market_cap': market_cap,
                    'turn_rate': turn_rate,
                    'volume': row.get('成交量', 0),
                })
                
            except Exception as e:
                continue
                
        print(f"✅ L1完成: {len(candidates)}只候选(市值>{L1_MIN_MARKET_CAP/1e8:.0f}亿)", file=sys.stderr)
        return candidates
        
    except Exception as e:
        print(f"❌ L1失败: {e}", file=sys.stderr)
        return []


def _discover_l2_ranking(candidates: List[Dict]) -> List[Dict]:
    """
    L2 热度+动量筛选：交叉验证热门榜 + K线技术分析
    
    - akshare stock_hot_rank_em (百度/新浪/东财热度排行)
    - K线均线多头排列检测  
    - 成交量异动加分
    
    Returns: Top ~80只精选候选(含热度分数)
    """
    print(f"📊 L2开始: {len(candidates)}只 → 目标{L2_CANDIDATE_COUNT}只", file=sys.stderr)
    
    # Step A: 获取热门榜交叉验证
    hot_scores = {}  # code → heat_score (0-1.0)
    try:
        import akshare as ak
        hot_rank_df = ak.stock_hot_rank_em()
        
        if hot_rank_df is not None and not hot_rank_df.empty:
            # 热门榜排名越靠前，分数越高
            for idx, row in hot_rank_df.iterrows():
                code = str(row.get('代码', ''))[:6]  
                if code.isdigit():
                    rank_score = max(0.1, 1.0 - (idx / len(hot_rank_df)))
                    hot_scores[code] = max(hot_scores.get(code, 0), rank_score)
                    
    except Exception as e:
        print(f"⚠️ L2-热度榜获取失败: {e}", file=sys.stderr)
    
    # Step B: K线动量分析 (有缓存命中就跳过)
    scored = []
    cache_kline = {}  # code → recent closes
    
    for cand in candidates:
        code = cand['code']
        
        try:
            import akshare as ak
            
            hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if hist is None or hist.empty or len(hist) < 5:
                continue
                
            closes = hist['收盘'].values.astype(float)
            volumes = hist['成交量'].values.astype(float)
            
            # MA排列得分 (0-1)
            ma5 = closes[-5:].mean() if len(closes) >= 5 else 0
            ma10 = closes[-10:].mean() if len(closes) >= 10 else 0  
            ma20 = closes[-20:].mean() if len(closes) >= 20 else 0
            
            ma_score = 0.3  # 基础分
            if ma5 > 0 and ma10 > 0 and ma20 > 0:
                if ma5 > ma10 > ma20:
                    ma_score += 0.4   # 完美多头排列
                elif ma5 > ma10 or ma10 > ma20:
                    ma_score += 0.2   # 部分多头
                    
            # 近20日涨幅得分 (温和上涨最佳)
            if len(closes) >= 20 and closes[0] > 0:
                gain_20d = (closes[-1] / closes[0] - 1) * 100
                if 5 <= gain_20d <= 25:
                    momentum_score = 0.8   # 温和上涨最佳区间  
                elif 0 < gain_20d < 5:
                    momentum_score = 0.6
                elif 25 < gain_20d <= 40:
                    momentum_score = 0.5   # 涨幅过大也有风险
                else:
                    momentum_score = 0.3
                    
            # 成交量异动加分  
            if len(volumes) >= 20 and volumes[-1] > 0:
                avg_vol_20 = volumes[-20:].mean()
                vol_ratio = volumes[-1] / avg_vol_20 if avg_vol_20 > 0 else 1
                vol_score = min(1.0, max(0.3, vol_ratio * 0.5))
                
            # 综合L2得分
            total_l2 = (ma_score * 0.4 + momentum_score * 0.4 + vol_score * 0.2)
            
            # 热门榜交叉验证加成
            heat_bonus = hot_scores.get(code, 0) * 0.3
            
            final_score = min(1.0, total_l2 + heat_bonus)
            
            scored.append({
                **cand,
                'l2_score': round(final_score, 4),
                'ma5': round(ma5, 2),
                'ma10': round(ma10, 2),
                'heat_rank': hot_scores.get(code, 0),
            })
            
        except Exception as e:
            continue
            
    # 按L2得分排序，取Top80
    scored.sort(key=lambda x: x.get('l2_score', 0), reverse=True)
    top_l2 = scored[:L2_CANDIDATE_COUNT]
    
    print(f"✅ L2完成: {len(top_l2)}只精选", file=sys.stderr)
    return top_l2



def safe_serializable(obj: Any) -> Any:
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    elif hasattr(obj, 'isna') and obj.isna():
        return None
    elif isinstance(obj, dict):
        return {k: safe_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_serializable(i) for i in obj]
    try:
        float_val = float(obj)
        if float_val == float('inf') or float_val == float('-inf'):
            return None
        return round(float_val, 4)
    except (ValueError, TypeError):
        return str(obj)


# ─── 动态发现模块 (akshare三源) ─────────────────────

# ═══════════════════════════════════════════════
# 持久化池管理 (v7) — 零硬编码，三层漏斗筛选
# ═══════════════════════════════════════════════

def _load_pool_state() -> Dict[str, Any]:
    """加载持久化池状态"""
    try:
        with open(POOL_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        # 数据格式迁移 (旧版 {code:name} → 新版 {code:{name:,activity:}})
        pool = state.get('pool', {})
        migrated = False
        for code in list(pool.keys()):
            if isinstance(pool[code], str):
                pool[code] = {'name': pool[code], 'activity': ACTIVITY_NEW_ENTRY}
                migrated = True
        
        if migrated:
            _save_pool_state(state)
            
        return state
        
    except FileNotFoundError:
        return {'pool': {}, 'last_scan': None, 'cache_version': 1}
    except Exception as e:
        print(f"⚠️ 读取池状态失败: {e}", file=sys.stderr)
        return {'pool': {}, 'last_scan': None, 'cache_version': 1}


def _save_pool_state(state: Dict[str, Any]):
    """保存池状态到JSON文件"""
    try:
        state['last_scan'] = datetime.now().isoformat()
        with open(POOL_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存池状态失败: {e}", file=sys.stderr)


def _update_activity_scores(pool_state: Dict, discovered_codes: set):
    """更新活动分数：发现+1，未发现-1"""
    pool = pool_state.get('pool', {})
    
    for code in list(pool.keys()):
        if code in discovered_codes:
            old_act = pool[code].get('activity', ACTIVITY_NEW_ENTRY)
            new_act = min(ACTIVITY_MAX, old_act + ACTIVITY_DISCOVERED_BONUS)
            if new_act != old_act:
                print(f"   📈 {code}({pool[code]['name']}): activity {old_act}→{new_act}↑", file=sys.stderr)
            pool[code]['activity'] = new_act
        else:
            old_act = pool[code].get('activity', ACTIVITY_NEW_ENTRY)  
            new_act = max(ACTIVITY_REMOVE_THRESHOLD, old_act - ACTIVITY_NOT_FOUND_PENALTY)
            if new_act != old_act:
                print(f"   📉 {code}({pool[code]['name']}): activity {old_act}→{new_act}↓", file=sys.stderr)
            pool[code]['activity'] = new_act


def _enforce_pool_capacity(pool_state: Dict, max_size: int = POOL_MAX_SIZE):
    """强制池容量控制：剔除低活动分股票"""
    pool = pool_state.get('pool', {})
    
    # 按活动分数排序，最低的先剔除  
    sorted_items = sorted(pool.items(), key=lambda x: x[1].get('activity', 0))
    
    while len(sorted_items) > max_size:
        code, info = sorted_items.pop(0)
        if info.get('activity', 0) <= ACTIVITY_REMOVE_THRESHOLD:
            del pool[code]
            print(f"   🗑️ 剔除低活股: {code}({info['name']})", file=sys.stderr)


def build_dynamic_pool(fresh_candidates=None):
    """
    构建动态池：合并持久化记忆 + 新发现 → 活动分数更新 → 容量控制
    
    Args: fresh_candidates: L1+L2筛选后的候选列表 (可选)
    Returns: pool_state dict
    """
    # 加载上次状态
    state = _load_pool_state()
    old_pool = state.get('pool', {})
    
    if fresh_candidates:
        discovered_codes = set(c['code'] for c in fresh_candidates)
    else:
        discovered_codes = set()
        
    # 更新活动分数  
    _update_activity_scores(state, discovered_codes)
    
    # 合并持久化+新发现
    merged = dict(old_pool)
    if fresh_candidates:
        for cand in fresh_candidates:
            code = cand['code']
            name = cand.get('name', '未知')
            if code not in merged or merged[code].get('activity', 0) < ACTIVITY_NEW_ENTRY:
                merged[code] = {'name': name, 'activity': ACTIVITY_NEW_ENTRY}
    
    # 容量控制
    _enforce_pool_capacity({'pool': merged}, POOL_MAX_SIZE)
    
    # 保存状态
    state['pool'] = merged  
    _save_pool_state(state)
    
    pool_size = len(merged)
    print(f"✅ 动态池构建完成: {pool_size}只", file=sys.stderr)


def discover_stocks(max_discover: int = L2_CANDIDATE_COUNT) -> Dict[str, str]:
    """
    动态发现热门标的 — akshare三源发现 + 智能缓存 + 持久化记忆
    
    三层漏斗：
      L1: stock_zh_a_spot_em → 全量扫描过滤 (市值/ST/换手率)
      L2: K线分析 + 热门榜交叉 → Top80精选  
      L3: build_dynamic_pool() → 合并记忆+活动分数 → 最终池子
    
    智能缓存策略：
      - L1/L2结果缓存1小时，避免重复全量扫描
      - L3财务数据每次刷新（实时性要求高）
    
    Returns: {code: name} 字典(兼容旧接口)
    """
    import time
    
    # 检查L1/L2缓存是否有效
    state = _load_pool_state()
    last_scan_ts = state.get('last_scan', None)
    cache_valid = False
    
    if last_scan_ts:
        try:
            last_scan_dt = datetime.fromisoformat(last_scan_ts)
            age_seconds = (datetime.now() - last_scan_dt).total_seconds()
            if age_seconds < CACHE_TTL_L1L2:
                cache_valid = True
                print(f"⚡ L1/L2缓存命中 ({age_seconds:.0f}s前扫描，TTL={CACHE_TTL_L1L2//60}min)", file=sys.stderr)
        except:
            pass
    
    if cache_valid:
        # 直接复用上次L1/L2结果，不重复全量扫描
        print("⚡ [L1→L2] 缓存命中，跳过全量扫描...", file=sys.stderr)
        merged_pool = state.get('pool', {})
        
        # 仍然更新活动分数（基于持久化池子自检查）
        discovered_codes = set(merged_pool.keys())
        _update_activity_scores(state, discovered_codes)
        _save_pool_state(state)
    else:
        print("\n🔍 [L1] 全量扫描A股...", file=sys.stderr)
        l1_candidates = _discover_l1_candidates()
        
        if not l1_candidates:
            # 兜底：只用持久化池子
            pool = state.get('pool', {})
            return {code: (info['name'] if isinstance(info, dict) else info) for code, info in pool.items()}
        
        print(f"🔍 [L2] K线+热门榜分析 ({len(l1_candidates)}只)...", file=sys.stderr)
        l2_top = _discover_l2_ranking(l1_candidates)
        
        if not l2_top:
            pool = state.get('pool', {})  
            return {code: (info['name'] if isinstance(info, dict) else info) for code, info in pool.items()}
        
        print(f"🔍 [L3] 构建动态池...", file=sys.stderr)
        build_dynamic_pool(l2_top)
    
    # 返回兼容格式
    final_state = _load_pool_state()
    merged = final_state.get('pool', {})
    return {code: (info['name'] if isinstance(info, dict) else info) for code, info in merged.items()}


def get_valuation(code: str, price: float) -> Dict[str, Any]:
    """
    获取个股估值指标: PE(TTM), PB, PEG, PCF(市现率), PS(市销率)
    三级缓存策略:
      L1 → 内存VALUATION_CACHE (秒回)
      L2 → AkShare stock_value_em (实时)
      L3 → _valuation_state.json 持久化缓存 (<5天有效)
    """
    # L1: 内存缓存
    if code in VALUATION_CACHE:
        return VALUATION_CACHE[code]

    result = {}
    pcache = {}

    # L2: AkShare实时获取
    try:
        import akshare as ak
        df = ak.stock_value_em(symbol=code)
        if df is not None and not df.empty:
            row = df.tail(1).iloc[0]
            result = {
                'pe_ttm': round(float(row.get('PE(TTM)', 0)), 2) if pd_notna(row, 'PE(TTM)') else None,
                'pe_static': round(float(row.get('PE(静)', 0)), 2) if pd_notna(row, 'PE(静)') else None,
                'pb': round(float(row.get('市净率', 0)), 2) if pd_notna(row, '市净率') else None,
                'peg': round(float(row.get('PEG值', 0)), 4) if pd_notna(row, 'PEG值') else None,
                'pcf': round(float(row.get('市现率', 0)), 2) if pd_notna(row, '市现率') else None,
                'ps': round(float(row.get('市销率', 0)), 2) if pd_notna(row, '市销率') else None,
            }
    except Exception as e:
        print(f"⚠️ {code} AkShare估值数据获取失败: {e}", file=sys.stderr)

    # L3: 持久化缓存 fallback（akshare不可达时读JSON文件）
    if not result:
        try:
            pcache = _load_persistent_cache(_VAL_FILE)
            entry = pcache.get(code, {})
            cached_ts = entry.get('_ts', 0)
            age = time.time() - cached_ts
            if age < _CACHE_TTL_SECONDS and entry.get('pe_ttm') is not None:
                result = {k: v for k, v in entry.items() if k != '_ts'}
                print(f"💾 {code} 估值数据使用本地缓存 ({age/86400:.1f}天前)", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ {code} 持久化估值缓存读取失败: {e}", file=sys.stderr)

    # L2成功时保存到持久化缓存
    if result and pcache.get(code) is None:
        try:
            pcache[code] = dict(result, _ts=time.time())
            _save_persistent_cache(_VAL_FILE, pcache)
        except Exception:
            pass

    VALUATION_CACHE[code] = result
    return result


def get_financial_abstract(code: str) -> Dict[str, Any]:
    """
    获取个股最新一期财务摘要: ROE, 毛利率, 净利率, 现金流, 负债率等
    三级缓存策略:
      L1 → 内存FA_CACHE (秒回)
      L2 → AkShare stock_financial_abstract_ths (实时)
      L3 → _financial_abstract_state.json 持久化缓存 (<5天有效)
    """
    # L1: 内存缓存
    if code in FA_CACHE:
        return FA_CACHE[code]

    result = {}

    def pct_to_float(val):
        """把 '52.22%' 或 False/NaN 转为浮点数"""
        s = str(val).strip().rstrip('%')
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    def raw_to_float(val):
        """把原始数值转浮点（排除 False/NaN）"""
        if val == 'False' or val is False:
            return None
        try:
            return round(float(val), 4)
        except (ValueError, TypeError):
            return None

    # L2: AkShare实时获取
    try:
        import akshare as ak
        df = ak.stock_financial_abstract_ths(symbol=code)
        if df is not None and not df.empty:
            row = df.tail(1).iloc[0]
            result = {
                'roe': pct_to_float(row.get('净资产收益率', None)),
                'gross_margin': pct_to_float(row.get('销售毛利率', None)),
                'net_margin': pct_to_float(row.get('销售净利率', None)),
                'debt_ratio': pct_to_float(row.get('资产负债率', None)),
                'eps': raw_to_float(row.get('基本每股收益', None)),
                'bvps': raw_to_float(row.get('每股净资产', None)),
                'ocfps': raw_to_float(row.get('每股经营现金流', None)),
                'current_ratio': raw_to_float(row.get('流动比率', None)),
                'quick_ratio': raw_to_float(row.get('速动比率', None)),
            }
    except Exception as e:
        print(f"⚠️ {code} AkShare财务数据获取失败: {e}", file=sys.stderr)

    # L3: 持久化缓存 fallback（akshare不可达时读JSON文件）
    if not result:
        try:
            fcache = _load_persistent_cache(_FA_FILE)
            entry = fcache.get(code, {})
            cached_ts = entry.get('_ts', 0)
            age = time.time() - cached_ts
            if age < _CACHE_TTL_SECONDS and entry.get('roe') is not None:
                result = {k: v for k, v in entry.items() if k != '_ts'}
                print(f"💾 {code} 财务数据使用本地缓存 ({age/86400:.1f}天前)", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ {code} 持久化财务缓存读取失败: {e}", file=sys.stderr)

    # L2成功时保存到持久化缓存
    if result:
        try:
            fcache = _load_persistent_cache(_FA_FILE)
            if fcache.get(code) is None:
                fcache[code] = dict(result, _ts=time.time())
                _save_persistent_cache(_FA_FILE, fcache)
        except Exception:
            pass

    FA_CACHE[code] = result
    return result


def pd_notna(row, col):
    """安全判断单元格是否为有效数值"""
    val = row.get(col)
    if val is None or val == 'False' or val is False:
        return False
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False



def _calc_period_returns(code: str, hist_df) -> Dict[str, float]:
    """
    基于历史K线计算各期间收益率
    Returns: {近1个月: x%, 近3个月: y%, ...}
    """
    if hist_df is None or hist_df.empty or '收盘' not in hist_df.columns or '日期' not in hist_df.columns:
        return {}
    
    try:
        import pandas as pd
        
        # 确保日期列是datetime类型
        df = hist_df.copy()
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').reset_index(drop=True)
        
        now = df['日期'].iloc[-1]
        closes = df['收盘'].values
        
        periods = {
            '近1个月': 20,      # ~20交易日 ≈ 1个月
            '近3个月': 60,
            '近半年': 120,
            '近1年': 244,
            'YTD': None,       # 年初至今（特殊处理）
        }
        
        result = {}
        for pname, trading_days in periods.items():
            if pname == 'YTD':
                # 年初至今：找到今年1月1日之后的数据
                year_start = pd.Timestamp(now.year, 1, 1)
                mask = df['日期'] >= year_start
                ytd_df = df[mask]
                if len(ytd_df) > 0 and len(ytd_df) < len(df):
                    start_price = float(ytd_df['收盘'].iloc[0])
                    end_price = float(df['收盘'].iloc[-1])
                    ret = (end_price / start_price - 1) * 100
                    result[pname] = round(ret, 2)
                else:
                    result[pname] = 0.0
            else:
                if len(closes) >= trading_days + 1:
                    start_price = float(closes[-(trading_days + 1)])
                    end_price = float(closes[-1])
                    ret = (end_price / start_price - 1) * 100
                    result[pname] = round(ret, 2)
                else:
                    # K线数据不够，用全部可用数据算
                    if len(closes) > 1:
                        start_price = float(closes[0])
                        end_price = float(closes[-1])
                        ret = (end_price / start_price - 1) * 100
                        result[pname] = round(ret, 2)
                    else:
                        result[pname] = 0.0
        
        return result
    
    except Exception as e:
        print(f"⚠️ {code} 收益率计算失败: {e}", file=sys.stderr)
        return {}


# ─── P4: 技术指标计算函数 ──────────────────────────────

def _calc_rsi(closes, period=14):
    """计算RSI指标"""
    if len(closes) < period + 1:
        return None
    deltas = closes.diff().dropna()
    gains = deltas.where(deltas > 0, 0).tail(period).mean()
    losses = (-deltas.where(deltas < 0, 0)).tail(period).mean()
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100 - (100 / (1 + rs)), 2)

def _calc_macd(closes):
    """计算MACD指标，返回(dif, dea, macd_bar)
    
    Fix: O(n) 正向递推 EMA + DIF 序列
    - 原嵌套循环 i<25 时 ema26_i=ema12_i → DIF=0 污染 DEA
    - 改为单次遍历，EMA12/EMA26 同步更新
    """
    closes_list = closes.tolist() if hasattr(closes, 'tolist') else list(closes)
    n = len(closes_list)
    if n < 26:
        return None
    
    # Step 1: O(n) 正向递推 EMA12 + EMA26 → DIF 序列
    ema12_r = closes_list[0]
    ema26_r = closes_list[0]
    dif_values = [0.0]  # first point, DIF=0 by definition
    
    for i in range(1, n):
        ema12_r = closes_list[i] * 2/13 + ema12_r * 11/13
        ema26_r = closes_list[i] * 2/27 + ema26_r * 25/27
        dif_values.append(ema12_r - ema26_r)
    
    # Step 2: DIF (最后一个值)
    dif = round(dif_values[-1], 3)
    
    # Step 3: DEA = EMA9 of DIF 序列
    dea = dif_values[0]
    for i in range(1, n):
        dea = dif_values[i] * 2/10 + dea * 8/10
    dea = round(dea, 3)
    
    # Step 4: MACD柱
    macd_bar = round((dif - dea) * 2, 3)
    return (dif, dea, macd_bar)

def _calc_boll(closes, period=20):
    """计算布林带，返回(upper, mid, lower, bandwidth%)"""
    if len(closes) < period:
        return None
    closes_arr = closes[-period:].tolist() if hasattr(closes, 'tolist') else list(closes)[-period:]
    mid = sum(closes_arr) / period
    variance = sum((x - mid)**2 for x in closes_arr) / period
    std_dev = variance ** 0.5
    upper = round(mid + 2*std_dev, 2)
    lower = round(mid - 2*std_dev, 2)
    bandwidth = round(std_dev / mid * 100, 2)
    return (upper, mid, lower, bandwidth)

def _calc_technical_indicators(hist_df):
    """计算所有技术指标，返回字典"""
    result = {}
    try:
        closes = hist_df['收盘']
        if len(closes) < 26:  # MACD最少需要
            return result
        
        rsi = _calc_rsi(closes)
        if rsi is not None:
            result['rsi14'] = rsi
        
        macd = _calc_macd(closes)
        if macd:
            result['macd_dif'], result['macd_dea'], result['macd_bar'] = macd
        
        boll = _calc_boll(closes)
        if boll:
            result['boll_upper'], result['boll_mid'], result['boll_lower'], result['boll_bw'] = boll
    except Exception:
        pass  # 技术指标计算失败不影响主流程
    return result


# ─── 辅助函数 ──────────────────────────────
def get_stock_data(code: str, include_valuation: bool = True) -> Optional[Dict[str, Any]]:
    """
    获取单只股票实时数据 + 估值指标 + 财务摘要
    include_valuation=False 时可跳过估值/财务查询（快速模式）
    """
    try:
        import tushare as ts, sys as _sys
        with _redirect_stdout(_io_module.StringIO()):  # suppress tushare deprecation spam
            df = ts.get_realtime_quotes(code)
        if df is None or df.empty:
            return None

        row = df.iloc[0]
        price = float(row['price'])
        pre_close = float(row['pre_close'])
        change_pct = round((price / pre_close - 1) * 100, 2)

        data = {
            'code': code,
            'name': str(row.get('name', '')),
            'price': round(price, 2),
            'change': round(price - pre_close, 4),
            'change_pct': change_pct,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'volume': int(float(row.get('volume', 0))),
            'amount': float(row.get('amount', 0)),
        }

        # MA参考 + 各期间收益率 (akshare优先，tushare备用)
        import time as _time
        hist_df = None
        
        # Try akshare with retry (3 attempts, 1s delay between retries)
        for attempt in range(3):
            try:
                import akshare as ak
                hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                if hist_df is not None and not hist_df.empty and '收盘' in hist_df.columns:
                    break
            except Exception:
                pass
            if attempt < 2:
                _time.sleep(1)  # 短暂等待避免被限流
        
        # Fallback to tushare K-line data (suppress deprecated warning)
        if hist_df is None or (hist_df is not None and (hist_df.empty or '收盘' not in hist_df.columns)):
            try:
                import datetime as _dt, tushare as ts
                end_date = _dt.datetime.now().strftime('%Y-%m-%d')
                start_date = (_dt.datetime.now() - _dt.timedelta(days=300)).strftime('%Y-%m-%d')
                with _redirect_stdout(_io_module.StringIO()):  # suppress tushare deprecation spam
                    kdata = ts.get_k_data(code, autype='qfq', start=start_date, end=end_date)
                if kdata is not None and not kdata.empty:
                    hist_df = kdata.rename(columns={
                        'close': '收盘', 'open': '开盘', 'high': '最高', 
                        'low': '最低', 'volume': '成交量'
                    })
                    if 'date' in hist_df.columns:
                        hist_df = hist_df.rename(columns={'date': '日期'})
            except Exception as _e:
                pass
        
        if hist_df is not None and not hist_df.empty and '收盘' in hist_df.columns:
            data['recent_days'] = len(hist_df)
            closes_series = hist_df['收盘']
            
            if len(closes_series) >= 5:
                data['ma5'] = round(float(closes_series.tail(5).mean()), 2)
                data['ma10'] = round(float(closes_series.tail(10).mean()), 2) if len(closes_series) >= 10 else None
            
            # ── 计算各期间收益率 ──
            returns = _calc_period_returns(code, hist_df)
            if returns:
                data['period_returns'] = returns
            
            # ── P4: 计算技术指标 ──
            tech_indicators = _calc_technical_indicators(hist_df)
            if tech_indicators:
                data.update(tech_indicators)
            
            # ── v0.9新增：为趋势因子提供K线原始数据 ──
            closes_series = hist_df['收盘'].astype(float).values.tolist()
            volumes_series = hist_df.get('成交量', pd.Series([0]*len(hist_df))).astype(float).values.tolist() if '成交量' in hist_df.columns else []
            data['_kline_closes'] = closes_series[-60:]  # 最近60天收盘价
            data['_kline_volumes'] = volumes_series[-60:] if volumes_series else []

        # ── TODO #2: 估值 + 财务数据 ──
        if include_valuation:
            data.update(get_valuation(code, price))
            data.update(get_financial_abstract(code))

        return data

    except Exception as e:
        print(f"⚠️ {code} 数据获取失败: {e}", file=sys.stderr)
        return None


def analyze_codes(codes_str: str, limit: int = 10,
                  include_valuation: bool = True,
                  weights: Optional[Dict] = None,
                  use_exa: bool = False) -> List[Dict[str, Any]]:
    """分析指定股票列表
    
    Args:
        use_exa: 是否启用Exa板块热度搜索 (默认False保性能)
    """
    codes = [c.strip() for c in codes_str.split(',') if c.strip()]

    # 如果输入的是名称,尝试匹配代码
    final_codes = []
    for code in codes:
        if len(code) != 6 or not code.isdigit():
            # 尝试从动态池反向查找
            found = False
            pool = {code: info['name'] if isinstance(info, dict) else info 
                   for code, info in _load_pool_state().get('pool', {}).items()}
            for hc, hn in pool.items():
                if code in hn or hn in code:
                    final_codes.append(hc)
                    found = True
                    break
            if not found:
                print(f"⚠️ 未识别: {code},跳过", file=sys.stderr)
        else:
            final_codes.append(code)

    # 获取数据并筛选
    results = []
    for code in final_codes[:limit]:
        data = get_stock_data(code, include_valuation=include_valuation)
        if data:
            score = compute_score(data, weights=weights, use_exa=use_exa)
            data['screen_score'] = round(score, 2)
            results.append(data)

    # 按得分排序
    results.sort(key=lambda x: x.get('screen_score', 0), reverse=True)
    return results


def screen_hot_pool(
    limit: int = 8,
    min_change_pct: float = -2.0,
    max_change_pct: float = 15.0,
    discovered: Optional[Dict[str, str]] = None,
    include_valuation: bool = True,
    weights: Optional[Dict] = None,
    use_exa: bool = False
) -> List[Dict[str, Any]]:
    """从动态构建的池子筛选 (三层漏斗: L1全量→L2热度动量→L3财务深度)
    
    Args:
        use_exa: 是否启用Exa板块热度搜索 (默认False保性能，与analyze统一规则)
    """
    # 构建动态池 (合并持久化记忆 + 新发现)  
    dynamic_state = _load_pool_state()
    dynamic_pool_raw = dynamic_state.get('pool', {})
    
    # 如果discover参数传入，先触发一轮L1/L2/L3完整发现流程
    if discovered:
        pool_dict = discovered  # discover_stocks已经返回了动态池结果
    else:
        pool_dict = {code: (info['name'] if isinstance(info, dict) else info) 
                     for code, info in dynamic_pool_raw.items()}
    
    # 如果池子为空，触发一次完整L1/L2/L3发现流程
    if not pool_dict:
        print("⚠️ 动态池为空，触发首次全量扫描...", file=sys.stderr)
        pool_dict = discover_stocks()
        dynamic_state = _load_pool_state()  
        dynamic_pool_raw = dynamic_state.get('pool', {})

    # 对池子中的股票做L3深度财务分析 (只对Top N只，控制耗时)  
    results = []
    
    # 按活动分数排序，高分优先分析
    if dynamic_pool_raw:
        sorted_codes = sorted(
            dynamic_pool_raw.keys(), 
            key=lambda c: dynamic_pool_raw[c].get('activity', ACTIVITY_NEW_ENTRY),
            reverse=True
        )[:POOL_MAX_SIZE]  
    else:
        sorted_codes = list(pool_dict.keys())[:POOL_MAX_SIZE]

    for code in sorted_codes:
        data = get_stock_data(code, include_valuation=include_valuation)
        if data:
            cpct = data.get('change_pct', 0)
            if min_change_pct <= cpct <= max_change_pct:
                score = compute_score(data, weights=weights, use_exa=use_exa)
                data['screen_score'] = round(score, 2)
                results.append(data)

    results.sort(key=lambda x: x.get('screen_score', 0), reverse=True)
    return results[:limit]


# ─── 多因子打分模型 (TODO #3) ──────────────────────────────

# 默认因子权重配置（总分10分制）
DEFAULT_WEIGHTS = {
    # === 价值因子组 (7个) ===
    'valuation_pe': 1.5,   # PE(TTM) 合理区间
    'valuation_pb': 1.0,   # PB 合理区间
    'peg':          1.0,   # PEG < 1 加分
    'roe':          1.5,   # ROE 越高越好
    'margins':      1.0,   # 毛利率 + 净利率
    'cashflow':     0.8,   # 每股经营现金流为正
    'health':       0.7,   # 负债率健康、流动/速动比率好
    
    # === 趋势因子组 (4个，v0.9新增) ===
    'consec_up_days': 1.2, # K线连续上涨天数（3-5天最佳）
    'volume_surge':   1.0, # 今日量 vs 20日均量（温和放量最佳）
    'ma_alignment':   1.2, # MA多头排列程度
    'sector_heat':    0.8, # 板块热度（Exa搜索新闻情绪）
}

def _score_momentum(data: Dict[str, Any]) -> float:
    """动量因子：涨幅适中+均线多头 → 满分1分"""
    score = 0.5  # 中性起点
    cpct = data.get('change_pct', 0) or 0

    if 2 <= cpct <= 7:
        score += 0.4   # 温和上涨最佳
    elif 1 <= cpct < 2:
        score += 0.25  # 小幅上涨
    elif cpct > 7:
        score -= 0.1   # 涨幅过大，追高风险
    elif cpct < -3:
        score -= 0.4   # 大跌扣多分
    elif -1 < cpct < 1:
        pass           # 横盘不动，不加分不扣分

    # MA参考
    ma5 = data.get('ma5')
    price = data.get('price', 0)
    if ma5 and price > 0:
        ratio = price / float(ma5)
        if ratio > 1.02:
            score += 0.1   # 价格在MA5上方
        elif ratio < 0.98:
            score -= 0.1  # 低于MA5

    return max(0, min(1, score))


def _score_pe(pe: Optional[float], sector='general') -> float:
    """
    PE合理性评分 → 满分1分
    general: PE 10-30 最佳; 科技可放宽到 15-50
    """
    if pe is None or pe <= 0:
        return 0.4  # 无数据，给中性偏下

    if sector == 'tech':
        best_lo, best_hi = 15, 50
        accept_hi = 80
    else:
        best_lo, best_hi = 10, 30
        accept_hi = 50

    if best_lo <= pe <= best_hi:
        return 1.0
    elif pe < best_lo:
        return 0.7  # PE偏低，可能低估也可能是陷阱
    elif pe <= accept_hi:
        return 0.4  # 偏高但可接受
    else:
        return 0.1  # 太贵了


def _score_pb(pb: Optional[float]) -> float:
    """
    PB合理性评分 → 满分1分
    PB 1-5 最佳, >10 很危险
    """
    if pb is None or pb <= 0:
        return 0.4
    if 1 <= pb <= 5:
        return 1.0
    elif pb < 1:
        return 0.8  # PB<1 可能破净，不一定好
    elif pb <= 10:
        return 0.4
    else:
        return 0.1


def _score_peg(peg: Optional[float]) -> float:
    """
    PEG评分 → 满分1分
    <1 = 低估, 1-1.5 = 合理, >2 = 贵了
    """
    if peg is None or peg <= 0:
        return 0.4
    if peg < 0.5:
        return 0.9  # 严重低估但可能有坑
    elif peg <= 1.0:
        return 1.0
    elif peg <= 1.5:
        return 0.7
    elif peg <= 2.0:
        return 0.4
    else:
        return 0.1


def _score_roe(roe: Optional[float]) -> float:
    """
    ROE评分 → 满分1分
    >20% = 优秀, <5% = 差
    """
    if roe is None:
        return 0.4
    if roe >= 20:
        return 1.0
    elif roe >= 15:
        return 0.85
    elif roe >= 10:
        return 0.7
    elif roe >= 5:
        return 0.5
    else:
        return max(0.1, roe / 20)


def _score_margins(gross: Optional[float], net: Optional[float]) -> float:
    """
    利润率评分 → 满分1分
    毛利率>40% + 净利率>15% = 优秀
    """
    score = 0.0
    count = 0

    if gross is not None:
        count += 1
        if gross >= 60:
            score += 0.7
        elif gross >= 40:
            score += 0.55
        elif gross >= 20:
            score += 0.35
        else:
            score += 0.15

    if net is not None:
        count += 1
        if net >= 25:
            score += 0.7
        elif net >= 15:
            score += 0.55
        elif net >= 8:
            score += 0.35
        else:
            score += 0.15

    return score / count if count > 0 else 0.4


def _score_cashflow(ocfps: Optional[float]) -> float:
    """
    每股经营现金流评分 → 满分1分
    正数为好，负数扣分
    """
    if ocfps is None:
        return 0.4
    if ocfps > 5:
        return 1.0
    elif ocfps >= 1:
        return 0.7
    elif ocfps > 0:
        return 0.5
    else:
        return max(0, 0.3 + ocfps / 10)


def _score_health(debt_ratio: Optional[float], current_ratio: Optional[float], quick_ratio: Optional[float]) -> float:
    """
    财务健康评分 → 满分1分
    负债率<50% + 流动比率>1.5 + 速动比率>1 = 优秀
    """
    score = 0.0
    count = 0

    if debt_ratio is not None:
        count += 1
        if debt_ratio < 30:
            score += 0.7
        elif debt_ratio < 50:
            score += 0.55
        elif debt_ratio < 70:
            score += 0.35
        else:
            score += 0.15

    if current_ratio is not None:
        count += 1
        if current_ratio >= 2:
            score += 0.7
        elif current_ratio >= 1.5:
            score += 0.55
        elif current_ratio >= 1:
            score += 0.35
        else:
            score += 0.15

    if quick_ratio is not None:
        count += 1
        if quick_ratio >= 2:
            score += 0.6
        elif quick_ratio >= 1.5:
            score += 0.45
        elif quick_ratio >= 1:
            score += 0.3
        else:
            score += 0.15

    return score / count if count > 0 else 0.4


# ─── 趋势因子组 (v0.9新增，纯本地计算) ──────────────────────

EXA_SECTOR_CACHE: Dict[str, Tuple[float, str]] = {}  # code → (score, reason)
EXA_LAST_SEARCH_TS: float = 0  # Exa搜索时间戳，防频繁调用
EXA_COOLDOWN_SECONDS = int(os.getenv('EXA_COOLDOWN', '1800'))  # 默认30分钟冷却
EXA_FAILED: bool = False  # Exa是否发生过不可达（用于最终输出提醒）


def _score_consec_up_days(closes: List[float]) -> float:
    """
    连续上涨天数评分 → 满分1分
    
    逻辑：从最新交易日往前数，统计连续收盘价 > 前一天收盘的天数
      3-5天最佳（趋势确立但未过热），≥8天严重追高风险
    """
    if not closes or len(closes) < 2:
        return 0.4  # 数据不足，中性分
    
    consec = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1]:
            consec += 1
        else:
            break
    
    if 3 <= consec <= 5:
        return 1.0   # 🎯 最佳区间：趋势确立但未过热
    elif consec >= 8:
        return 0.2   # ⚠️ 严重过热，追高风险极高
    elif consec >= 6:
        return 0.6   # 开始过热，需警惕
    elif consec == 1 or consec == 2:
        return 0.3   # 刚启动，信号偏弱
    else:
        return 0.4   # 横盘或下跌，中性偏保守


def _score_volume_surge(volumes: List[float]) -> float:
    """
    成交量异动评分 → 满分1分
    
    逻辑：今日量 vs 近20日均量
      1.5-3倍温和放量最佳（资金关注信号），>5倍异常放量需警惕
    """
    if not volumes or len(volumes) < 20:
        return 0.4  # 数据不足，中性分
    
    avg_vol_20 = sum(volumes[-20:]) / 20.0
    if avg_vol_20 <= 0:
        return 0.4
    
    vol_ratio = volumes[-1] / avg_vol_20
    
    if 1.5 <= vol_ratio <= 3.0:
        return 1.0   # 🎯 温和放量：资金关注但未疯狂
    elif vol_ratio > 5.0:
        return 0.2   # ⚠️ 异常放量：可能是出货或恐慌性抛售
    elif vol_ratio < 0.5:
        return 0.1   # 缩量：流动性不足，关注度低
    
    # 默认区间 [0.5, 1.5) 和 (3.0, 5.0]
    return max(0.3, min(0.7, vol_ratio * 0.2))


def _score_ma_alignment(closes: List[float]) -> float:
    """
    MA多头排列评分 → 满分1分
    
    逻辑：计算MA5/MA10/MA20并判断排列关系
      完美多头(MA5>MA10>MA20)最佳，空头排列最差
    """
    if not closes or len(closes) < 20:
        return 0.4  # 数据不足
    
    ma5 = sum(closes[-5:]) / 5.0 if len(closes) >= 5 else 0
    ma10 = sum(closes[-10:]) / 10.0 if len(closes) >= 10 else 0
    ma20 = sum(closes[-20:]) / 20.0 if len(closes) >= 20 else 0
    
    if ma5 > 0 and ma10 > 0 and ma20 > 0:
        if ma5 > ma10 > ma20:
            return 1.0   # 🎯 完美多头排列：短期>中期>长期
        elif ma5 > ma10:
            return 0.6   # 短期强势，中期待确认
        elif ma10 > ma20:
            return 0.4   # 中期趋势向上，短期需观察
    
    return 0.3   # 均线交错或空头排列


def _score_sector_heat(code: str, name: str) -> float:
    """
    板块热度评分 → 满分1分（调用Exa搜索近期新闻）
    
    逻辑：通过mcporter调Exa API搜索公司相关股票新闻，
          检测负面关键词则扣分，否则按结果数量加分。
    冷却机制：同一批次最多调用一次Exa搜索。
    """
    global EXA_FAILED
    # Step 1: 查缓存
    if code in EXA_SECTOR_CACHE:
        score, reason = EXA_SECTOR_CACHE[code]
        print(f"   🔍 Exa缓存命中 [{name}]: {reason}", file=sys.stderr)
        return score
    
    # Step 2: 检查冷却时间
    now_ts = time.time()
    if now_ts - EXA_LAST_SEARCH_TS < EXA_COOLDOWN_SECONDS:
        print(f"   🔍 Exa冷却中 [{name}] ({EXA_COOLDOWN_SECONDS - (now_ts - EXA_LAST_SEARCH_TS):.0f}s后可重试)", file=sys.stderr)
        return 0.5
    
    # Step 3: 调用Exa搜索（通过mcporter subprocess）
    try:
        search_query = f"{name} {code} A股 股票"
        mcporter_config = os.path.expanduser('~/.openclaw/workspace/config/mcporter.json')
        cmd = [
            'mcporter', '--config', mcporter_config,
            'call', 'exa.web_search_exa',
            f'query={search_query}', '--args', '{"numResults":3}'
        ]
        print(f"   🔍 Exa搜索 [{name}]: {cmd[5]}", file=sys.stderr)
        
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=15
        )
        
        if result.returncode != 0:
            print(f"   ⚠️ Exa调用失败 [{name}]: {result.stderr[:200]}", file=sys.stderr)
            return 0.5
        
        # Step 4: 解析结果
        output = result.stdout
        negative_keywords = ['造假', '立案', '处罚', '退市', '违规', '财务舞弊']
        has_negative = any(kw in output for kw in negative_keywords)
        
        title_count = output.count('Title:') if 'Title:' in output else 0
        
        if has_negative:
            score = 0.2  # ⚠️ 检测到负面信号
            reason = f"负面关键词检测(结果{title_count}条)"
        elif title_count >= 2:
            score = 0.8  # 多篇文章覆盖，关注度较高
            reason = f"高热度({title_count}篇报道)"
        elif title_count == 1:
            score = 0.6  # 有报道但不多
            reason = f"中等热度({title_count}篇报道)"
        else:
            score = 0.5  # 无明确结果，中性
            reason = "无搜索结果"
        
        EXA_SECTOR_CACHE[code] = (score, reason)
        return score
    
    except subprocess.TimeoutExpired:
        print(f"   ⚠️ Exa超时 [{name}]", file=sys.stderr)
        EXA_FAILED = True
        return 0.5
    except Exception as e:
        print(f"   ⚠️ Exa异常 [{name}]: {str(e)[:100]}", file=sys.stderr)
        EXA_FAILED = True
        return 0.5


def compute_score(data: Dict[str, Any], weights: Optional[Dict] = None, use_exa: bool = True) -> float:
    """
    多因子综合打分（满分10分）
    
    因子权重可通过 --weights JSON 参数传入，如：
      --weights '{"momentum":3.0,"valuation_pe":1.0}'
    use_exa=False 时跳过Exa搜索（批量筛选模式）
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    total_weight = sum(w.values())
    weighted_score = 0.0

    # PE
    s = _score_pe(data.get('pe_ttm'))
    weighted_score += s * w['valuation_pe']

    # PB
    s = _score_pb(data.get('pb'))
    weighted_score += s * w['valuation_pb']

    # PEG
    s = _score_peg(data.get('peg'))
    weighted_score += s * w['peg']

    # ROE
    s = _score_roe(data.get('roe'))
    weighted_score += s * w['roe']

    # 利润率
    s = _score_margins(data.get('gross_margin'), data.get('net_margin'))
    weighted_score += s * w['margins']

    # 现金流
    s = _score_cashflow(data.get('ocfps'))
    weighted_score += s * w['cashflow']

    # 财务健康
    s = _score_health(
        data.get('debt_ratio'),
        data.get('current_ratio'),
        data.get('quick_ratio'),
    )
    weighted_score += s * w['health']

    # === 趋势因子组 (v0.9新增) ===
    
    # 连续上涨天数
    kline_closes = data.get('_kline_closes') or []
    if kline_closes:
        s = _score_consec_up_days(kline_closes)
        weighted_score += s * w['consec_up_days']
    else:
        print("   ⚠️ 无K线收盘价数据，跳过连续上涨天数评分", file=sys.stderr)
    
    # 成交量异动
    kline_volumes = data.get('_kline_volumes') or []
    if kline_volumes:
        s = _score_volume_surge(kline_volumes)
        weighted_score += s * w['volume_surge']
    else:
        print("   ⚠️ 无K线成交量数据，跳过放量检测评分", file=sys.stderr)
    
    # MA多头排列
    if kline_closes:
        s = _score_ma_alignment(kline_closes)
        weighted_score += s * w['ma_alignment']
    else:
        print("   ⚠️ 无K线收盘价数据，跳过MA排列评分", file=sys.stderr)
    
    # 板块热度（Exa搜索，批量模式跳过）
    stock_code = data.get('code', '')
    stock_name = data.get('name', '未知')
    if use_exa:
        s = _score_sector_heat(stock_code, stock_name)
    else:
        s = 0.5  # 批量模式用中性分跳过Exa
    weighted_score += s * w['sector_heat']

    # 归一化到 0-10
    final = round(weighted_score / total_weight * 10, 2)
    return max(0, min(10, final))


def format_output(data_list, title="📊 分析结果", show_valuation=True):
    if not data_list:
        print("⚠️ 未获取到有效数据")
        return

    print(f"\n{title}")
    print("=" * len(title))

    for i, item in enumerate(data_list, 1):
        code = item.get('code', '')
        name = item.get('name', '')
        price = item.get('price', 'N/A')
        change_pct = item.get('change_pct', 'N/A')
        score = item.get('screen_score', '-')

        try:
            cp = float(change_pct) if isinstance(change_pct, (int, float)) else 0
            color = "🟢" if cp > 0 else ("🔴" if cp < 0 else "⚪")
        except:
            color = "⚪"

        print(f"\n{i}. {name} ({code})")
        print(f"   价格: ¥{price} | 涨跌幅: {color}{change_pct}% | 得分: {score}")

        ma5 = item.get('ma5')
        if ma5:
            diff = (float(price) / float(ma5) - 1) * 100 if float(ma5) > 0 else 0
            print(f"   MA5参考: ¥{ma5} ({'+↑' if diff > 0 else '-↓'}{abs(diff):.1f}%)")

        # ── TODO #2/#3: 估值 + 财务指标展示 ──
        if show_valuation:
            pe = item.get('pe_ttm')
            pb = item.get('pb')
            roe = item.get('roe')
            ocfps = item.get('ocfps')
            net_margin = item.get('net_margin')

            parts = []
            if pe is not None:
                parts.append(f"PE={pe}")
            if pb is not None:
                parts.append(f"PB={pb}")
            if roe is not None:
                parts.append(f"ROE={roe}%")
            if net_margin is not None:
                parts.append(f"净利率={net_margin}%")
            if ocfps is not None:
                tag = "✅" if ocfps > 0 else "⚠️"
                parts.append(f"现金流/股={ocfps}{tag}")

            if parts:
                print(f"   💡 {' | '.join(parts)}")

        # ── P4: 技术面指标展示（RSI/MACD/BOLL）──
        tech_parts = []
        
        # MA5 (已有)
        if ma5 and price > 0:
            try:
                diff = (float(price) / float(ma5) - 1) * 100
                if diff > 10:
                    tech_parts.append(f"MA5偏离+{diff:.1f}%⚠️")
                elif diff > 0:
                    tech_parts.append(f"MA5上方+{diff:.1f}%📈")
                else:
                    tech_parts.append(f"MA5下方{-diff:.1f}%📉")
            except:
                pass
        
        # RSI 指标
        rsi = item.get('rsi14')
        if rsi is not None:
            try:
                rsi_val = float(rsi)
                if rsi_val > 80:
                    tech_parts.append(f"RSI={rsi_val}（超买⚠️）")
                elif rsi_val > 70:
                    tech_parts.append(f"RSI={rsi_val}（偏强）")
                elif rsi_val < 30:
                    tech_parts.append(f"RSI={rsi_val}（超卖，可能反弹📈）")
                else:
                    tech_parts.append(f"RSI={rsi_val}")
            except:
                pass
        
        # MACD 指标
        macd_dif = item.get('macd_dif')
        macd_dea = item.get('macd_dea')
        if macd_dif is not None and macd_dea is not None:
            try:
                dif_val, dea_val = float(macd_dif), float(macd_dea)
                gap = abs(dif_val - dea_val) / max(abs(dea_val), 0.01) * 100
                
                # ✅ Fix: 更准确的判断逻辑
                if dif_val > dea_val and dif_val > 0:
                    tech_parts.append(f"MACD金叉📈")
                elif dif_val < dea_val and dif_val > 0:
                    # DIF在DEA上方但正在向下靠拢 → 看跌
                    if gap < 5:  # 很接近，即将死叉
                        tech_parts.append(f"MACD将死叉⚠️")
                    else:
                        tech_parts.append(f"MACD金叉减弱")
                elif dif_val < dea_val and dif_val < 0:
                    tech_parts.append(f"MACD死叉📉")
                elif dif_val > dea_val and dif_val < 0:
                    # DIF在DEA下方但正在向上靠拢 → 看涨
                    if gap < 5:
                        tech_parts.append(f"MACD将金叉⚠️")
                    else:
                        tech_parts.append(f"MACD死叉减弱")
                else:
                    tech_parts.append(f"MACD中轴附近")
            except:
                pass
        
        # BOLL 布林带
        boll_upper = item.get('boll_upper')
        boll_lower = item.get('boll_lower')
        if boll_upper is not None and boll_lower is not None and price > 0:
            try:
                bw_pct = (float(price) - float(boll_lower)) / (float(boll_upper) - float(boll_lower)) * 100
                if bw_pct > 95:
                    tech_parts.append(f"布林上轨⚠️")
                elif bw_pct < 5:
                    tech_parts.append(f"布林下轨📈")
            except:
                pass
        
        # 连涨天数
        consec_up = item.get('_consec_up_days')
        if consec_up is not None:
            try:
                cud = int(consec_up)
                if cud >= 5 and cud <= 8:
                    tech_parts.append(f"连涨{cud}天（趋势强劲）")
                elif cud > 8:
                    tech_parts.append(f"连涨{cud}天⚠️（追高风险）")
            except:
                pass
        
        # 组装技术面字符串
        if tech_parts:
            print(f"   🔧 技术面：{' | '.join(tech_parts)}")



# ═══════════════════════════════════════════════
# 三栏式输出系统 (2026-05-08)
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# 📊 标准盘前报告模板 v1.0
# 每次screen命令输出此格式，固化可复用
# ═══════════════════════════════════════════════════════════

def format_report_header(title="📈 盘前选股分析报告"):
    """报告头部：时间戳 + 筛选参数说明"""
    from datetime import datetime
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} | v0.9 统一打分规则")
    print(f"{'='*80}\n")


def format_summary_table(data_list, title="📊 Top 选股总览"):
    """第一栏：大列表 — 核心指标 + 四个期间收益率（近1月/3月/半年/年）+ PE/PB/ROE"""
    print(f"\n{'─'*80}")
    print(f"{title}")
    print("─"*80)

    header = f"{'#':<3} {'代码':>6} {'名称':<8} {'价格':>7} {'涨跌':>5} {'得分':>4}"
    header += f" | {'PE':>5} {'PB':>4} {'ROE%':>5}"
    header += f" | {'近1月':>6} {'近3月':>6} {'近半年':>6} {'近1年':>6}"
    print(header)
    print("-"*80)

    for idx, item in enumerate(data_list, 1):
        code = str(item.get('code', ''))
        name = item.get('name', '未知')[:6]
        price = float(item.get('price', 0))
        change_pct = float(item.get('change_pct', 0)) if isinstance(item.get('change_pct'), (int, float)) else 0
        score = float(item.get('screen_score', 0))

        pe = item.get('pe_ttm') or 'N/A'
        pb = item.get('pb') or 'N/A'
        roe = item.get('roe') or 'N/A'
        if isinstance(pe, (int, float)): pe = f"{pe:.1f}"
        else: pe = str(pe)
        if isinstance(pb, (int, float)): pb = f"{pb:.2f}"
        else: pb = str(pb)
        if isinstance(roe, (int, float)): roe = f"{roe:.1f}"
        else: roe = str(roe)

        periods = item.get('period_returns') or {}
        r1m = periods.get('近1个月', 0) or 0
        r3m = periods.get('近3个月', 0) or 0
        r6m = periods.get('近半年', 0) or 0
        r1y = periods.get('近1年', 0) or 0

        cp_emoji = "🟢" if change_pct > 0 else ("🔴" if change_pct < 0 else "⚪")
        row = f"{idx:<3} {code:>6} {name:<8} ¥{price:>6.2f} {cp_emoji}{change_pct:>4.1f}% {score:>4.2f}"
        row += f" | {pe:>5} {pb:>4} {roe:>5}"
        row += f" | {r1m:>+5.1f}% {r3m:>+5.1f}% {r6m:>+5.1f}% {r1y:>+5.1f}%"
        print(row)

    print(f"\n{'─'*80}")


def format_detailed_analysis(data_list, limit=10):
    """第二栏：Top N 个股深度分析卡（估值解读 + 技术面 + 风险因素）"""
    print(f"\n{'='*80}")
    print(f"🔍 Top {limit} 个股深度分析")
    print("="*80)

    for idx, item in enumerate(data_list[:limit], 1):
        text = analyze_stock_text(item, rank=idx)
        print(text)


def analyze_stock_text(item, rank=0):
    """生成对单只股票的详细文字分析和数据解读"""
    code = item.get('code', '')
    name = item.get('name', '未知')
    price = float(item.get('price', 0))
    change_pct = float(item.get('change_pct', 0)) if isinstance(item.get('change_pct'), (int, float)) else 0
    score = float(item.get('screen_score', 0))

    lines = []

    # PE interpretation
    pe = item.get('pe_ttm')
    pe_comment = "PE无数据"
    if pe is not None:
        try:
            pe_val = float(pe)
            if pe_val < 0:
                pe_comment = f"PE={pe_val}（亏损，需关注扭亏预期）"
            elif pe_val < 15:
                pe_comment = f"PE={pe_val}（估值偏低，安全边际充足）"
            elif pe_val < 30:
                pe_comment = f"PE={pe_val}（合理区间）"
            else:
                pe_comment = f"PE={pe_val}（偏高，需高成长支撑）"
        except:
            pass

    # P4修复：ROE评判标准校准（>10%健康, >15%优秀, <5%偏低）
    roe = item.get('roe')
    roe_comment = "ROE无数据"
    if roe is not None:
        try:
            roe_val = float(roe)
            if roe_val > 20:
                roe_comment = f"ROE={roe}%（卓越，行业龙头级别）"
            elif roe_val > 15:
                roe_comment = f"ROE={roe}%（优秀，持续创造价值）"
            elif roe_val >= 10:
                roe_comment = f"ROE={roe}%（健康，达到及格线以上）"
            elif roe_val >= 5:
                roe_comment = f"ROE={roe}%（偏低，需关注盈利能力）"
            else:
                roe_comment = f"ROE={roe}%（⚠️低于安全线，谨慎看待）"
        except:
            pass

    # Gross margin interpretation
    gross_margin = item.get('gross_margin')
    gm_comment = "毛利率无数据"
    if gross_margin is not None:
        try:
            gm_val = float(gross_margin)
            if gm_val > 30:
                gm_comment = f"毛利率={gm_val}%（高毛利，产品竞争力强）"
            elif gm_val > 15:
                gm_comment = f"毛利率={gm_val}%（正常水平）"
            else:
                gm_comment = f"毛利率={gm_val}%（偏低，成本控制压力较大）"
        except:
            pass

    # Cash flow interpretation
    ocfps = item.get('ocfps')
    cf_comment = "现金流无数据"
    if ocfps is not None:
        try:
            oc_val = float(ocfps)
            if oc_val > 0.5:
                cf_comment = f"每股现金流={oc_val}（造血能力强）"
            elif oc_val > 0:
                cf_comment = f"每股现金流={oc_val}（正向但偏弱）"
            else:
                cf_comment = f"每股现金流={oc_val}（⚠️ 需警惕流动性风险）"
        except:
            pass

    # ── P4: 技术面分析增强（RSI/MACD/BOLL）──
    tech_parts = []
    
    # MA5 (已有)
    ma5 = item.get('ma5')
    if ma5 and price > 0:
        try:
            diff = (price / float(ma5) - 1) * 100
            if diff > 10:
                tech_parts.append(f"MA5偏离+{diff:.1f}%⚠️")
            elif diff > 0:
                tech_parts.append(f"MA5上方+{diff:.1f}%📈")
            else:
                tech_parts.append(f"MA5下方{-diff:.1f}%📉")
        except:
            pass
    
    # RSI 指标
    rsi = item.get('rsi14')
    if rsi is not None:
        try:
            rsi_val = float(rsi)
            if rsi_val > 80:
                tech_parts.append(f"RSI={rsi_val}（超买⚠️）")
            elif rsi_val > 70:
                tech_parts.append(f"RSI={rsi_val}（偏强）")
            elif rsi_val < 30:
                tech_parts.append(f"RSI={rsi_val}（超买，可能反弹📈）")
            else:
                tech_parts.append(f"RSI={rsi_val}")
        except:
            pass
    
    # MACD 指标
    macd_dif = item.get('macd_dif')
    macd_dea = item.get('macd_dea')
    if macd_dif is not None and macd_dea is not None:
        try:
            dif_val, dea_val = float(macd_dif), float(macd_dea)
            gap = abs(dif_val - dea_val) / max(abs(dea_val), 0.01) * 100
            
            # ✅ Fix: 更准确的判断逻辑
            if dif_val > dea_val and dif_val > 0:
                tech_parts.append(f"MACD金叉📈")
            elif dif_val < dea_val and dif_val > 0:
                if gap < 5:  # 很接近，即将死叉
                    tech_parts.append(f"MACD将死叉⚠️")
                else:
                    tech_parts.append(f"MACD金叉减弱")
            elif dif_val < dea_val and dif_val < 0:
                tech_parts.append(f"MACD死叉📉")
            elif dif_val > dea_val and dif_val < 0:
                if gap < 5:
                    tech_parts.append(f"MACD将金叉⚠️")
                else:
                    tech_parts.append(f"MACD死叉减弱")
            else:
                tech_parts.append(f"MACD中轴附近")
        except:
            pass
    
    # BOLL 布林带
    boll_upper = item.get('boll_upper')
    boll_lower = item.get('boll_lower')
    if boll_upper is not None and boll_lower is not None and price > 0:
        try:
            bw_pct = (float(price) - float(boll_lower)) / (float(boll_upper) - float(boll_lower)) * 100
            if bw_pct > 95:
                tech_parts.append(f"布林上轨⚠️")
            elif bw_pct < 5:
                tech_parts.append(f"布林下轨📈")
        except:
            pass
    
    # 成交量异常检测（如果有volume数据）
    consec_up = item.get('_consec_up_days')
    if consec_up is not None:
        try:
            cud = int(consec_up)
            if cud >= 5 and cud <= 8:
                tech_parts.append(f"连涨{cud}天（趋势强劲）")
            elif cud > 8:
                tech_parts.append(f"连涨{cud}天⚠️（追高风险）")
        except:
            pass
    
    # 组装技术面字符串
    tech_comment = " | ".join(tech_parts) if tech_parts else ""


    # Period returns analysis (显示全部4个期间)
    periods = item.get('period_returns') or {}
    r1m = periods.get('近1个月', 0)
    r3m = periods.get('近3个月', 0)
    r6m = periods.get('近半年', 0)
    r1y = periods.get('近1年', 0)

    def fmt_ret(val, label):
        """格式化收益率显示"""
        if val is None:
            return f"{label}: N/A"
        if val > 5:
            return f"{label}涨幅+{val:.1f}%📈"
        elif val < -5:
            return f"{label}跌幅{val:.1f}%📉"
        else:
            return f"{label}: {val:+.1f}%"

    # 显示全部4个期间的收益率
    ret_lines = []
    for val, label in [(r1y, '近1年'), (r6m, '近半年'), (r3m, '近3月'), (r1m, '近1月')]:
        if val is not None:
            ret_lines.append(fmt_ret(val, label))

    return_summary = ""
    if ret_lines:
        return_summary = f"\n   📈 收益追踪: {ret_lines[0]} | {ret_lines[1]}"
        for line in ret_lines[2:]:
            return_summary += f"\n          | {line}"

    # News sentiment
    news_score = item.get('_news_score')
    news_reasons = item.get('_news_reasons', [])
    news_comment = ""
    if news_score is not None:
        try:
            ns = float(news_score)
            if ns >= 8:
                news_comment = f"新闻评分 {ns}/10（市场情绪偏乐观）"
            elif ns >= 5:
                news_comment = f"新闻评分 {ns}/10（中性偏积极）"
            else:
                news_comment = f"新闻评分 {ns}/10（⚠️ 关注负面风险）"
        except:
            pass

    # Rating system
    star_map = [
        (8.0, "极度看好 - 高确定性机会"),
        (7.0, "强烈推荐 - 值得重点配置"),
        (6.0, "值得关注 - 可作为核心持仓之一"),
        (5.0, "保持关注 - 适合波段操作"),
        (4.0, "观望为主 - 等待更好买点"),
    ]
    rating_text = "暂无评级"
    for threshold, label in star_map:
        if score >= threshold:
            rating_text = f"{label}"
            break

    # Assemble output
    lines.append(f"\n{'─'*60}")
    lines.append(f"📊 Top{rank}. {name}({code}) | ¥{price:.2f} ({'+' if change_pct > 0 else ''}{change_pct:.1f}%) | 得分 {score:.2f}")
    lines.append(f"{'─'*60}")

    metrics_block = f"""   ┌──────────── 核心指标解读 ────────────┐
   │ PE:     {pe_comment}                        │
   │ ROE:    {roe_comment}                      │
   │ 毛利率:  {gm_comment}                    │
   │ 现金流:  {cf_comment}                     │
   └──────────────────────────────────────┘"""
    lines.append(metrics_block)

    if tech_comment:
        lines.append(f"\n   🔧 技术面：{tech_comment}")
    
    if return_summary:
        lines.append(return_summary)
    
    if news_comment:
        lines.append(f"\n   📰 市场情绪：{news_comment}")
        for reason in news_reasons[:3]:
            lines.append(f"      • {reason}")

    lines.append(f"\n   ⭐⭐⭐ 综合评级：{rating_text}")

    return "\n".join(lines)


def _classify_stock_type(item: Dict[str, Any]) -> str:
    """
    P1统一分类标准：一套逻辑走天下
    
    返回类型:
      speculative — 亏损/劣质股，仅进取型可少量配置
      growth     — 高估值+动量，纯进攻
      value      — 低估值+盈利健康，底仓首选
      balanced   — 中间地带
    """
    pe = float(item.get('pe_ttm', 0)) if item.get('pe_ttm') else 0
    roe = float(item.get('roe', 0)) if item.get('roe') else 0
    gross_margin = float(item.get('gross_margin', 0)) if item.get('gross_margin') else 0
    r1m = (item.get('period_returns') or {}).get('近1个月', 0) or 0
    
    # speculative: PE为负（亏损）或ROE极低（<3%）
    if pe < 0 or roe < 3.0:
        return 'speculative'
    
    # growth: 高PE(>40)或短期涨幅大(>25%)，纯进攻
    if pe > 40 or r1m > 25:
        return 'growth'
    
    # value: PE合理且ROE健康（≥10%）
    if 0 < pe <= 25 and roe >= 10:
        return 'value'
    
    # growth: PE较高(>30)但ROE也高（优质成长）
    if pe > 30 and roe >= 15:
        return 'growth'
    
    # balanced: 其他中间地带
    return 'balanced'


def _is_toxic(item: Dict[str, Any]) -> bool:
    """
    P0质量红线：判断一只股票是否属于“毒资产”
    亏损、ROE极低、毛利率失控 → 保守型绝对不碰
    """
    pe = float(item.get('pe_ttm', 0)) if item.get('pe_ttm') else 0
    roe = float(item.get('roe', 0)) if item.get('roe') else 0
    gross_margin = float(item.get('gross_margin', 0)) if item.get('gross_margin') else 0
    
    # PE为负 → 亏损股
    if pe < 0:
        return True
    # ROE < 2% → 盈利能力太低（连银行定存都不如）
    if roe < 2.0:
        return True
    # 毛利率 < 5% → 成本失控，薄利多销型不适合做底仓
    if gross_margin > 0 and gross_margin < 5.0:
        return True
    
    return False


# 行业板块缓存（P3升级）
SECTOR_CACHE: Dict[str, str] = {}


def _preheat_sector_cache(stocks: List[Dict[str, Any]]) -> None:
    """
    P3批量预取：一次性查询所有候选股的行业数据并缓存
    避免在组合建议中重复查akshare
    """
    if not stocks:
        return
    
    try:
        import akshare as ak
        # 收集需要查询的代码（跳过已有缓存的）
        codes_to_query = []
        for stock in stocks:
            code = stock.get('code', '')
            if code and code not in SECTOR_CACHE:
                codes_to_query.append(code)
        
        # 批量查询
        for code in codes_to_query:
            try:
                df = ak.stock_individual_info_em(symbol=code)
                sector_found = False
                for _, row in df.iterrows():
                    if row['item'] == '行业':
                        sector = str(row['value']).strip()
                        if sector and sector != '--':
                            SECTOR_CACHE[code] = sector
                            sector_found = True
                            break
                if not sector_found:
                    SECTOR_CACHE[code] = '其他'
            except Exception:
                # 单个查询失败不影响整体
                pass
    except ImportError:
        pass  # akshare不可用，fallback到关键词


def _get_sector_name(code: str, name: str) -> str:
    """
P3升级：关键词匹配 + 代码段推断（akshare接口不稳定，以本地词典为主）
    用于组合建议中的行业分散检查
    """
    # Step 1: 查缓存
    if code in SECTOR_CACHE:
        return SECTOR_CACHE[code]
    
    # Step 2: 大型关键词词典匹配（覆盖常见板块）
    sector_keywords = {
        '电力': ['发电', '能源', '电力', '电网', '核电', '水电', '风电'],
        '银行': ['银行', '农商', '城商'],
        '券商': ['证券', '信托', '期货'],
        '保险': ['保险', '寿险', '财险'],
        '科技': ['科技', '信息', '软件', '芯片', '半导体', '电子', '智能', '数据', '云计算', 'AI', '人工智能'],
        '通信': ['通信', '5G', '光模块', '光纤', '卫星'],
        '军工': ['军工', '航天', '航空', '国防', '兵器', '船舶'],
        '医药': ['药', '医疗', '生物', '基因', '疫苗', '中药', '医疗器械', '制药'],
        '消费': ['食品', '饮料', '酒', '乳业', '零食', '调味', '零售', '商超', '餐饮'],
        '家电': ['电器', '空调', '冰箱', '洗衣机', '小家电', '厨电'],
        '汽车': ['汽车', '整车', '新能源汽', '一汽', '上汽', '北汽', '广汽', '比亚迪'],
        '机械': ['机械', '装备', '机床', '轴承', '阀门', '液压', '机器人', '自动化'],
        '钢铁': ['钢铁', '特钢', '金属制品', '冶金'],
        '有色': ['有色', '铜', '铝', '锂', '钴', '稀土', '黄金', '银', '锌', '铅', '锡', '钨'],
        '化工': ['化工', '化学', '化肥', '农药', '涂料', '橡胶', '塑料', '化纤', '新材料'],
        '建材': ['水泥', '玻璃', '陶瓷', '装饰', '幕墙', '防水', '管材', '钢结构'],
        '地产': ['地产', '房地产', '置业', '安居'],
        '建筑': ['建筑', '基建', '工程', '建设', '隧道', '桥梁', '路桥'],
        '交运': ['物流', '运输', '港口', '航运', '航空', '机场', '高铁', '铁路', '快递'],
        '传媒': ['传媒', '影视', '游戏', '动漫', '出版', '广告', '文化', '演艺', '娱乐'],
        '旅游': ['旅游', '酒店', '景点', '度假', '旅行社'],
        '农业': ['农业', '种业', '养殖', '饲料', '畜牧', '渔业', '林业', '棉', '糖'],
        '纺织': ['纺织', '服装', '鞋帽', '皮革', '羽绒', '印染'],
        '环保': ['环保', '水务', '固废', '污治', '园林', '生态'],
    }
    name_str = f"{code}{name}".replace(' ', '')
    for sector, keywords in sector_keywords.items():
        if any(kw in name_str for kw in keywords):
            SECTOR_CACHE[code] = sector
            return sector
    
    # Step 3: 代码段推断（辅助）
    # 60xxxx / 68xxxx → 上证主板 → 传统行业居多
    # 00xxxx / 002xxx / 003xxx → 深证主板/中小板
    # 30xxxx → 创业板 → 科技/成长偏多
    code_prefix = int(code[:1]) if len(code) >= 1 else 0
    if code_prefix == 6:
        SECTOR_CACHE[code] = '传统'
        return '传统'
    elif code_prefix == 3:
        SECTOR_CACHE[code] = '创业'
        return '创业'
    
    # Step 4: 终极fallback
    SECTOR_CACHE[code] = '其他'
    return '其他'


def _calc_portfolio_weights(portfolio: List[Dict[str, Any]]) -> List[int]:
    """
    P2精细化仓位计算：基于得分占比 + 风险等级动态分配
    
    逻辑:
      1. base_weight = (个股score / 总分) * 100%
      2. 按类型打折: value×1.2, balanced×1.0, growth×0.8, speculative×0.6
      3. clamp到[10%, 35%]
      4. 归一化到100%
    """
    if not portfolio:
        return []
    
    # Step 1: 基础得分占比
    total_score = sum(float(s.get('screen_score', 1)) for s in portfolio)
    if total_score == 0:
        return [int(100 / len(portfolio))] * len(portfolio)
    
    weights = []
    type_multipliers = {'value': 1.2, 'balanced': 1.0, 'growth': 0.8, 'speculative': 0.6}
    
    for stock in portfolio:
        score = float(stock.get('screen_score', 1))
        base_w = (score / total_score) * 100
        stype = _classify_stock_type(stock)
        multiplier = type_multipliers.get(stype, 1.0)
        adjusted_w = base_w * multiplier
        weights.append(adjusted_w)
    
    # Step 3: clamp到[10%, 35%]
    weights = [max(10, min(35, w)) for w in weights]
    
    # Step 4: 归一化到100%
    total_w = sum(weights)
    if total_w > 0:
        weights = [round(w / total_w * 100) for w in weights]
    
    # 微调：保证总和=100（四舍五入误差修正）
    diff = 100 - sum(weights)
    if diff != 0 and weights:
        weights[0] += diff
    
    return [int(w) for w in weights]


def format_portfolio_suggestion(data_list, max_count=5):
    """根据得分和特征给出组合配置建议（最多买N只）"""
    print(f"\n{'='*70}")
    print(f"🎯 投资组合配置建议")
    print("="*70)

    sorted_stocks = sorted(data_list, key=lambda x: float(x.get('screen_score', 0)), reverse=True)
    
    # P3升级：批量预取行业数据（避免重复查akshare）
    _preheat_sector_cache(sorted_stocks[:max_count + 5])

    # P1修复：正确分类股票类型（四档）
    growth_candidates = []
    value_candidates = []
    balanced_candidates = []
    speculative_candidates = []  # P1新增

    for item in sorted_stocks[:max_count + 5]:
        stock_type = _classify_stock_type(item)
        if stock_type == 'growth':
            growth_candidates.append(item)
        elif stock_type == 'value':
            value_candidates.append(item)
        elif stock_type == 'speculative':
            speculative_candidates.append(item)
        else:
            balanced_candidates.append(item)

    # P3修复：保守型必须满3只且全部来自价值/平衡类别
    print(f"\n📦 【保守型】最多买3只（稳健为主）")
    port3 = []
    
    # 优先从价值型选，不足则从平衡型补充
    available_for_conservative = value_candidates + balanced_candidates
    for stock in available_for_conservative[:6]:
        if len(port3) >= 3:
            break
        if not _is_toxic(stock):  # P0: 跳过toxic stock
            port3.append(stock)
    
    # P0修复：如果还不够3只，从全部候选中补足，但跳过toxic stock
    warning_msg = ""
    if len(port3) < 3 and sorted_stocks:
        for stock in sorted_stocks:
            if stock not in port3 and not _is_toxic(stock):
                port3.append(stock)
            if len(port3) >= 3:
                break
        # 如果还是没有满3只，说明池子质量整体不行
        if len(port3) < 3:
            warning_msg = "（候选池质量不足，仅推荐{}只，宁缺毋滥）".format(len(port3))

    # P3修复：行业分散检查
    sectors_in_port3 = set()
    for stock in port3:
        sector = _get_sector_name(stock.get('code', ''), stock.get('name', ''))
        sectors_in_port3.add(sector)
    
    if len(sectors_in_port3) < min(len(port3), 2):
        print(f"   ⚠️ 行业集中警告：当前组合集中在 {len(sectors_in_port3)} 个行业")

    for idx, stock in enumerate(port3, 1):
        name = stock.get('name', '未知')
        code = stock.get('code', '')
        pe = float(stock.get('pe_ttm', 0)) if stock.get('pe_ttm') else 0
        score = float(stock.get('screen_score', 0))
        roe = float(stock.get('roe', 0))
        sector = _get_sector_name(code, name)
        
        stock_type_label = _classify_stock_type(stock)
        if stock_type_label == 'value':
            role = "价值底仓"
        elif stock_type_label == 'growth':
            role = "成长弹性"
        elif stock_type_label == 'speculative':
            role = "投机观察"
        else:
            role = "平衡配置"
        
        print(f"   {idx}. {name}({code}) - [{sector}] {role}")
        print(f"      得分: {score:.2f} | PE={pe} | ROE={roe}%")

    # P3修复：进取型按类型正确分配
    print(f"\n📦 【进取型】最多买5只（均衡配置）")
    port5 = []
    
    # 均衡配置：2价值 + 1平衡 + 1成长 + 1投机(可选)
    port5.extend(value_candidates[:2])
    if balanced_candidates:
        port5.append(balanced_candidates[0])
    port5.extend(growth_candidates[:1])
    # P1新增：进取型可以少量配置投机股，最多1只
    if speculative_candidates and len(port5) < 4:
        port5.append(speculative_candidates[0])
    
    # 不足5只时补足
    remaining = [s for s in sorted_stocks if s not in port5]
    while len(port5) < max_count and remaining:
        port5.append(remaining.pop(0))

    # P2修复：统一计算所有仓位
    weights = _calc_portfolio_weights(port5[:5])
    
    for idx, stock in enumerate(port5[:5], 1):
        name = stock.get('name', '未知')
        code = stock.get('code', '')
        score = float(stock.get('screen_score', 0))
        r1y = (stock.get('period_returns') or {}).get('近1年', 0) or 0

        stype = _classify_stock_type(stock)
        type_labels = {'value': '价值', 'growth': '成长', 'balanced': '平衡', 'speculative': '投机'}
        stock_type_label = type_labels.get(stype, '平衡')
        print(f"   {idx}. {name}({code}) - {stock_type_label}")
        print(f"      建议仓位: ~{weights[idx-1]}% | 得分: {score:.2f} | 近1年: {r1y:+.0f}%")

    # P4升级：个性化风险提示
    print(f"\n⚠️ 本组合风险提示:")
    
    # 个股风险
    for stock in port5[:5]:
        name = stock.get('name', '未知')
        pe = float(stock.get('pe_ttm', 0)) if stock.get('pe_ttm') else 0
        roe = float(stock.get('roe', 0)) if stock.get('roe') else 0
        r1y = (stock.get('period_returns') or {}).get('近1年', 0) or 0
        warnings = []
        
        if pe < 0:
            warnings.append("PE为负，存在亏损风险")
        elif pe > 50:
            warnings.append(f"PE偏高({pe})，需高成长支撑")
        
        if roe < 3.0:
            warnings.append(f"ROE过低({roe}%)，盈利能力弱")
        elif roe < 8.0:
            warnings.append(f"ROE偏低({roe}%)，关注盈利改善")
        
        if r1y > 100:
            warnings.append("短期涨幅过大，注意回调风险")
        
        if warnings:
            print(f"   • {name}: {'; '.join(warnings)}")
    
    # 行业集中度
    sectors = [_get_sector_name(s.get('code', ''), s.get('name', '')) for s in port5[:5]]
    from collections import Counter
    sector_counts = Counter(sectors)
    max_conc = max(sector_counts.values()) if sector_counts else 0
    if max_conc >= 3:
        concentrated = [s for s, c in sector_counts.items() if c >= 3]
        print(f"   • 行业集中: {', '.join(concentrated)}板块占比过高")
    
    # 投机股比例
    speculative_count = sum(1 for s in port5[:5] if _classify_stock_type(s) == 'speculative')
    if speculative_count >= 2:
        print(f"   • 投机股{speculative_count}只，整体风险偏高")
    
    # 通用建议
    print("\n⚠️ 投资建议:")
    print("   • 以上仅为基于量化模型的筛选结果，不构成投资建议")
    print("   • 建议分批建仓，控制单只股票仓位不超过30%")
    print("   • 设置止损位（通常-8%~-10%）和止盈目标（+20%~+50%）")
    print("   • 关注个股财报季表现及行业政策变化")

    print(f"\n{'='*70}")


def get_kline_data(code: str, days: int = 300):
    """
    P5 helper: 获取历史K线数据 (akshare优先，tushare兜底)
    
    Returns DataFrame with columns: ['日期', '开盘', '收盘', '最高', '最低', '成交量']
    """
    import time as _time
    import datetime as _dt
    hist_df = None
    
    # Try akshare with retry (3 attempts, 1s delay)
    for attempt in range(3):
        try:
            import akshare as ak
            hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if hist_df is not None and not hist_df.empty and '收盘' in hist_df.columns:
                break
        except Exception:
            pass
        if attempt < 2:
            _time.sleep(1)
    
    # Fallback to tushare K-line data (suppress deprecated warning)
    if hist_df is None or (hist_df is not None and (hist_df.empty or '收盘' not in hist_df.columns)):
        try:
            import tushare as ts
            end_date = _dt.datetime.now().strftime('%Y-%m-%d')
            start_date = (_dt.datetime.now() - _dt.timedelta(days=days)).strftime('%Y-%m-%d')
            with _redirect_stdout(_io_module.StringIO()):  # suppress tushare deprecation spam
                kdata = ts.get_k_data(code, autype='qfq', start=start_date, end=end_date)
            if kdata is not None and not kdata.empty:
                hist_df = kdata.rename(columns={
                    'close': '收盘', 'open': '开盘', 'high': '最高', 
                    'low': '最低', 'volume': '成交量'
                })
                if 'date' in hist_df.columns:
                    hist_df = hist_df.rename(columns={'date': '日期'})
        except Exception as _e:
            pass
    
    return hist_df if hist_df is not None else (pd.DataFrame() if pd else None)


def run_backtest(codes, days=250, threshold=6.0):
    """
P5: 历史回测验证模型信号
    
    基于历史K线数据，按模型打分规则模拟交易：
    - 得分 >= 阈值 → 买入信号
    - 得分 < 阈值/2 → 卖出信号
    - 计算累计收益率、最大回撤、夏普比率等指标
    """
    from datetime import timedelta
    
    print(f"\n{'='*70}")
    print(f"🔬 回测引擎启动 | 周期: {days}天 | 买入阈值: {threshold}")
    print(f"{'='*70}\n")
    
    all_results = []
    
    for code in codes:
        try:
            # 获取历史K线
            hist_df = get_kline_data(code)
            if len(hist_df) < days:
                print(f"⚠️ {code} K线数据不足{days}天，跳过")
                continue
            
            # 取最近N天数据
            df = hist_df.tail(days).copy()
            
            # 初始化交易状态
            cash = 100000.0  # 初始资金
            shares = 0
            position_cost = 0.0
            signals = []
            daily_returns = []
            portfolio_value_history = [cash]
            
            # 逐日回测（简化版：每10天重新计算一次得分）
            for i in range(min(30, len(df) - 26), len(df)):
                if i % 10 != 0:  # 每10个交易日评估一次
                    continue
                
                try:
                    # 获取当前股票数据（简化版）
                    current_price = float(df['收盘'].iloc[i])
                    prev_price = float(df['收盘'].iloc[i-1])
                    change_pct = (current_price / prev_price - 1) * 100
                    
                    # 计算简化得分（基于动量+技术指标）
                    score = _calc_simple_signal_score(df.iloc[:i], current_price, change_pct)
                    
                    signal_date = str(df['日期'].iloc[i]) if '日期' in df.columns else f"Day{i}"
                    
                    # 交易逻辑
                    if score >= threshold and shares == 0:  # 买入信号且空仓
                        shares = int(cash / current_price)
                        position_cost = current_price * shares
                        cash -= position_cost
                        signals.append((signal_date, 'BUY', current_price, score))
                    elif score < threshold / 2 and shares > 0:  # 卖出信号且持仓
                        revenue = current_price * shares
                        profit = revenue - (shares * position_cost)
                        cash += revenue
                        shares = 0
                        signals.append((signal_date, 'SELL', current_price, score))
                    
                    # 记录每日组合价值
                    portfolio_value = cash + shares * current_price
                    portfolio_value_history.append(portfolio_value)
                    if len(portfolio_value_history) > 1:
                        daily_return = (portfolio_value / portfolio_value_history[-2] - 1)
                        daily_returns.append(daily_return)
                
                except Exception as e:
                    continue  # 跳过错误交易日
            
            # 计算最终指标
            final_value = cash + shares * float(df['收盘'].iloc[-1])
            total_return = (final_value / 100000.0 - 1) * 100
            max_drawdown = _calc_max_drawdown(portfolio_value_history)
            
            # 夏普比率（简化）
            if daily_returns:
                avg_daily_return = sum(daily_returns) / len(daily_returns)
                std_daily_return = (sum((r - avg_daily_return)**2 for r in daily_returns) / len(daily_returns)) ** 0.5
                sharpe_ratio = avg_daily_return / std_daily_return * 252 ** 0.5 if std_daily_return > 0 else 0
            else:
                sharpe_ratio = 0
            
            all_results.append({
                'code': code,
                'final_value': round(final_value, 2),
                'total_return': round(total_return, 2),
                'max_drawdown': round(max_drawdown * 100, 2),
                'sharpe_ratio': round(sharpe_ratio, 2),
                'signals': signals
            })
        
        except Exception as e:
            print(f"❌ {code} 回测失败: {e}")
    
    # 输出回测结果
    print("\n📊 回测结果汇总")
    print("="*80)
    print(f"{'代码':>6} | {'最终净值':>12} | {'总收益率':>10} | {'最大回撤':>10} | {'夏普比率':>8}")
    print("-"*80)
    
    for r in all_results:
        ret_str = f"{r['total_return']:+.2f}%"
        dd_str = f"{r['max_drawdown']:.2f}%"
        sr_str = f"{r['sharpe_ratio']:.2f}"
        print(f"{r['code']:>6} | {r['final_value']:>12.2f} | {ret_str:>10} | {dd_str:>10} | {sr_str:>8}")
    
    # 输出交易信号
    if all_results:
        print(f"\n📋 交易信号明细（前3只股票）")
        for r in all_results[:3]:
            if r['signals']:
                print(f"\n{r['code']}:")
                for sig_date, action, price, score in r['signals'][-10:]:  # 最近10个信号
                    emoji = "🟢" if action == 'BUY' else "🔴"
                    print(f"   {sig_date} | {action:>4} | ¥{price:.2f} | 得分:{score:.1f}")
    
    print(f"\n{'='*70}\n")


def _calc_max_drawdown(value_history):
    """计算最大回撤"""
    if not value_history:
        return 0.0
    max_value = value_history[0]
    max_dd = 0.0
    for v in value_history:
        if v > max_value:
            max_value = v
        dd = (max_value - v) / max_value if max_value > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _calc_simple_signal_score(hist_df, current_price, change_pct):
    """
    P5: 简化版信号得分（用于回测，不需要完整估值数据）
    
    基于历史K线计算动量+技术指标综合得分
    v2校准：各因子改为连续评分，避免全二元条件导致分数过低
    """
    score = 0.0
    closes = hist_df['收盘'] if '收盘' in hist_df.columns else hist_df.iloc[:, -1]
    n = len(closes)
    
    # === 动量因子 (最高3.5分) ===
    if n >= 20:
        momentum_20d = (current_price / closes.iloc[-20] - 1) * 100
        # 连续评分：+10%→满分, -10%→0分
        score += max(0, min(momentum_20d / 10, 3.5))
    
    if n >= 5:
        momentum_5d = (current_price / closes.iloc[-5] - 1) * 100
        # 短期动量：+5%→满分, -5%→0分
        score += max(0, min(momentum_5d / 5, 1.5))
    
    # === MA排列因子 (最高2.5分) ===
    if n >= 20:
        ma5 = closes.iloc[-5:].mean()
        ma10 = closes.iloc[-10:].mean()
        ma20 = closes.iloc[-20:].mean() if n >= 20 else ma10
        
        # MA5>MA10: +1.5分; MA10>MA20完美多头: +1分
        ratio_5_10 = (ma5 - ma10) / max(ma10, 1)
        score += max(0, min(ratio_5_10 * 75, 1.5))
        
        ratio_10_20 = (ma10 - ma20) / max(ma20, 1)
        score += max(0, min(ratio_10_20 * 50, 1.0))
    
    # === RSI因子 (最高2分) ===
    rsi = _calc_rsi(closes)
    if rsi is not None:
        # RSI在35-65之间最佳(避免超买超卖但保留动量空间)
        if 35 <= rsi <= 65:
            score += 2.0
        elif 25 <= rsi <= 75:
            # 偏离越远扣分越多
            if rsi < 35:
                score += max(0, (rsi - 25) / 10)
            else:
                score += max(0, (75 - rsi) / 10)
    
    # === MACD因子 (最高1.5分) ===
    macd = _calc_macd(closes)
    if macd and len(macd) >= 2:
        diff = macd[0] - macd[1]
        if diff > 0:  # DIF在DEA上方
            score += min(abs(diff) * 5, 1.5)
    
    return round(min(score, 10.0), 2)
def main():
    """主函数入口 - stock_screen v9+ (P1-P5 completed)"""
    parser = argparse.ArgumentParser(description='轻量版股票筛选器 v0.9 — 混合打分模型 (价值6:趋势4) + Exa可选增强')
    subparsers = parser.add_subparsers(dest='action', help='操作类型')

    # ── 分析指定股票 ──
    analyze_p = subparsers.add_parser('analyze', help='分析指定股票代码')
    analyze_p.add_argument('--codes', required=True, help='股票代码列表,逗号分隔')
    analyze_p.add_argument('--limit', type=int, default=10)

    # ── 热门池筛选 ──
    screen_p = subparsers.add_parser('screen', help='从热门股池筛选')
    screen_p.add_argument('--limit', type=int, default=10)
    screen_p.add_argument('--min-change', type=float, default=-2.0)
    screen_p.add_argument('--max-change', type=float, default=15.0)
    screen_p.add_argument('--discover', action='store_true', help='先通过akshare三源发现新标的再筛选')

    # ── P5: 回测功能 ──
    backtest_p = subparsers.add_parser('backtest', help='历史回测验证模型信号')
    backtest_p.add_argument('--codes', required=True, help='股票代码列表,逗号分隔')
    backtest_p.add_argument('--days', type=int, default=250, help='回测天数（默认250天≈1年）')
    backtest_p.add_argument('--threshold', type=float, default=6.0, help='买入信号得分阈值（默认6分）')
    discover_p = subparsers.add_parser('discover', help='通过akshare三源动态发现热门标的')
    discover_p.add_argument('--max-discover', type=int, default=10, help='最多发现几只新标的')

    # ── 全局选项: JSON输出 / 权重配置 / 快速模式 ──
    for sub in subparsers.choices.values():
        sub.add_argument('--format', choices=['table', 'json'], default='table')
        sub.add_argument('--no-valuation', action='store_true', help='跳过估值/财务查询(更快)')
        sub.add_argument('--weights', type=str, default=None,
                        help='自定义权重JSON，如 \'{"valuation_pe":2.0}\'')
        sub.add_argument('--enable-exa', action='store_true', help='启用Exa板块热度搜索(默认关闭)')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(0)

    try:
        fmt = getattr(args, 'format', 'table')
        show_valuation = not getattr(args, 'no_valuation', False)

        # 解析权重JSON
        custom_weights = None
        if getattr(args, 'weights', None):
            try:
                custom_weights = json.loads(args.weights)
            except json.JSONDecodeError as e:
                print(f"❌ 权重JSON解析失败: {e}", file=sys.stderr)
                sys.exit(1)

        if args.action == 'analyze':
            results = analyze_codes(
                args.codes,
                limit=args.limit,
                include_valuation=show_valuation,
                weights=custom_weights,
                use_exa=getattr(args, 'enable_exa', False),
            )

            if fmt == 'json':
                print(json.dumps(safe_serializable(results), ensure_ascii=False, indent=2))
            else:
                format_output(results, f"🎯 个股分析 ({len(results)}只)", show_valuation=show_valuation)
                # Exa不可达时提醒
                if EXA_FAILED:
                    print("\n⚠️ [注意] Exa API 调用失败，板块热度因子使用默认中性分(0.5)")
                    print("   可能原因：网络超时、mcporter未配置或Exa服务不可达")
                    print("   建议：检查 ~/.openclaw/workspace/config/mcporter.json 配置后重试\n")

        elif args.action == 'screen':
            # 默认走动态池构建（零硬编码），--discover标志保留向后兼容  
            if getattr(args, 'discover', False):
                discovered = discover_stocks(max_discover=getattr(args, 'max_discover', L2_CANDIDATE_COUNT))
            else:
                discovered = None  # screen_hot_pool内部会触发动态池构建

            results = screen_hot_pool(
                limit=args.limit,
                min_change_pct=args.min_change,
                max_change_pct=args.max_change,
                discovered=discovered,
                include_valuation=show_valuation,
                weights=custom_weights,
                use_exa=getattr(args, 'enable_exa', False),
            )

            if fmt == 'json':
                print(json.dumps(safe_serializable(results), ensure_ascii=False, indent=2))
            else:
                try:
                    with open(POOL_STATE_FILE, 'r', encoding='utf-8') as pf:
                        pstate = json.load(pf)
                        persistent_count = len(pstate.get('pool', {}))
                except:
                    persistent_count = 0
                fresh_count = len(discovered) if discovered else 0
                pool_note = f"动态池{persistent_count + fresh_count}只(持久化{persistent_count}+新发现{fresh_count})"
                # ═══ 📊 标准盘前报告模板 v1.0 ═══
                format_report_header()
                format_summary_table(results, title=f"📊 Top 选股总览 ({len(results)}只)")
                format_detailed_analysis(results, limit=10)
                
                format_portfolio_suggestion(results, max_count=5)
                print(f"\n{'='*50}")
                print(f"注: 基于{pool_note}实时数据")
                
                # Exa不可达时提醒
                if EXA_FAILED:
                    print("\n⚠️ [注意] 本次筛选过程中 Exa API 调用失败，板块热度因子使用默认中性分(0.5)")
                    print("   可能原因：网络超时、mcporter未配置或Exa服务不可达")
                    print("   建议：检查 ~/.openclaw/workspace/config/mcporter.json 配置后重试\n")

        elif args.action == 'discover':
            discovered = discover_stocks(max_discover=getattr(args, 'max_discover', 10))
            if fmt == 'json':
                result_list = [{'code': str(k), 'name': v, 'source': 'akshare_discovered'} for k, v in discovered.items()]
                print(json.dumps(result_list, ensure_ascii=False, indent=2))
            else:
                if not discovered:
                    print("⚠️ 未动态发现新标的,可能搜索结果解析失败")
                else:
                    print(f"\n🔍 akshare 动态发现结果 ({len(discovered)}只):")
                    print("=" * 40)
                    for code, name in discovered.items():
                        print(f"   {name} ({code})")
        
        elif args.action == 'backtest':
            codes = [c.strip() for c in args.codes.split(',') if c.strip()]
            run_backtest(codes, days=args.days, threshold=args.threshold)

    except Exception as e:
        print(f"❌ 执行失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
