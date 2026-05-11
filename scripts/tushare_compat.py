"""
TuSource Pandas 2.x Compatibility Shim
======================================
Pandas 2.0+ removed DataFrame.append() but TuShare 1.4.29 still uses it.
This module patches tushare at import time to work with modern pandas.

Usage: 
    from tushare_compat import patched_ts as ts
"""

import pandas as pd
from functools import wraps


def _patch_dataframe_append():
    """Add back DataFrame.append() for older code that depends on it"""
    
    @wraps(pd.DataFrame._constructor_sliced)  
    def append(self, other, ignore_index=False, verify_integrity=True, sort=None):
        """Compatibility wrapper: pandas 2.x removed .append(), restore it via concat"""
        if isinstance(other, pd.DataFrame):
            result = pd.concat([self, other], ignore_index=ignore_index, sort=sort)
        elif isinstance(other, (list, tuple)):
            result = pd.concat(list(self) + list(other), ignore_index=ignore_index, sort=sort)
        else:
            result = pd.concat([self, other], ignore_index=ignore_index, sort=sort)
        
        if verify_integrity and not result.index.is_unique:
            raise ValueError("Indexes are overlapping")
            
        return result
    
    # Monkey-patch DataFrame.append
    pd.DataFrame.append = append


def _patch_tushare_trading():
    """Patch tushare's trading module to use concat instead of append"""
    try:
        import tushare.stock.trading as trading_mod
        
        # Read the source file and replace all .append() calls with pd.concat()
        import inspect
        src_file = inspect.getfile(trading_mod)
        
        if not src_file.endswith('.py'):
            return  # Can't patch compiled files
            
        with open(src_file, 'r') as f:
            content = f.read()
            
        original_content = content
        
        # Multi-line pattern for data.append(...) spanning multiple lines  
        import re
        
        # Pattern: data = data.append(something,\n                           ignore_index=True)
        content = re.sub(
            r'(data\s*=\s*data)\.append\(\s*\n?\s*(.*?)\n?\s*,\s*\n?\s*ignore_index\s*=\s*True\)',
            lambda m: f'{m.group(1)} = pd.concat([{m.group(1)}, {m.group(2).replace("\\n", "").strip()}], ignore_index=True)',
            content, 
            flags=re.DOTALL
        )
        
        # Pattern: df = df.append(something, ignore_index=True) (single line)
        content = re.sub(
            r'(df\s*=\s*df)\.append\(([^)]+),\s*ignore_index\s*=\s*True\)',
            r'\1 = pd.concat([\2], ignore_index=True)',
            content
        )
        
        # Pattern: df.append(data,  ignore_index=True) (without assignment on same line)
        content = re.sub(
            r'(\w+)\.append\(data,\s*ignore_index\s*=\s*True\)',
            r'pd.concat([df, data], ignore_index=True)',
            content
        )
        
        # Pattern: data.append(df) without ignore_index (first iteration)  
        content = re.sub(
            r'data\.append\(df\)\s+if\s+i\s*==\s*0',
            r'pd.concat([data, df], ignore_index=True) if i == 0',
            content
        )
        
        # If anything changed, write back
        if content != original_content:
            with open(src_file, 'w') as f:
                f.write(content)
            return True
            
    except Exception as e:
        print(f"⚠️ TuShare trading patch skipped: {e}")
        
    return False


def patched_ts():
    """Return a tushare module that's compatible with pandas 2.x"""
    import tushare as ts
    
    # Apply patches
    _patch_dataframe_append()
    _patch_tushare_trading()
    
    return ts
