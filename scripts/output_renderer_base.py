#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StockOutputRenderer — 选股结果输出渲染器抽象基类

设计目标：
  - 定义统一的输出协议 (render_header / render_body / render_footer)
  - 所有子类接收 ScreeningResult，产出对应格式的字符串/文件
  - screener main() 只负责生产数据 + 选 renderer，不耦合任何格式化逻辑
  - 新增输出方式只需继承基类实现几个方法即可

架构：
    screener data (ScreeningResult)
        │
        ▼
    StockOutputRenderer (ABC) ─── render_header() → str
                                   render_body()   → str
                                   render_footer() → str
                                   render()        → str  (组合以上三者)
        ├── TextCLIExporter     (终端文本报告)
        ├── HTMLEmailExporter   (HTML邮件)
        ├── JSONExporter        (API/结构化对接)
        └── ...自由扩展
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from .screening_result import ScreeningResult


class StockOutputRenderer(ABC):
    """选股结果输出渲染器抽象基类"""

    # 子类覆盖此属性声明支持的格式标识符 (如 'text', 'html', 'json')
    FORMAT_ID: str = 'base'

    def __init__(self, title: Optional[str] = None, version_tag: Optional[str] = None):
        self.title = title or '选股分析报告'
        self.version_tag = version_tag or ''

    @abstractmethod
    def render_header(self, result: ScreeningResult) -> str:
        """渲染报告头部（标题、时间戳、版本等）"""
        pass

    @abstractmethod
    def render_body(self, result: ScreeningResult) -> str:
        """渲染报告主体内容（股票列表、深度分析、组合建议等）"""
        pass

    @abstractmethod
    def render_footer(self, result: ScreeningResult) -> str:
        """渲染报告尾部（风险提示、免责声明等）"""
        pass

    def render(self, result: ScreeningResult) -> str:
        """完整渲染 — 子类可覆盖以自定义组合方式"""
        parts = [
            self.render_header(result),
            self.render_body(result),
            self.render_footer(result),
        ]
        return '\n'.join(p for p in parts if p)

    def export(self, result: ScreeningResult, filepath: Optional[str] = None):
        """渲染并保存到文件（可选）"""
        content = self.render(result)
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        return content


# ═══════════════════════════════════════════
# Renderer 工厂 — 根据格式标识创建渲染器实例
# ═══════════════════════════════════════════

_REGISTRY: dict = {}  # format_id → class


def register_renderer(cls: type) -> type:
    """装饰器：自动注册到渲染器工厂"""
    _REGISTRY[cls.FORMAT_ID] = cls
    return cls


def create_renderer(format_id: str, **kwargs) -> StockOutputRenderer:
    """根据格式标识创建渲染器实例"""
    if format_id not in _REGISTRY:
        raise ValueError(f"未注册的输出格式: {format_id}，已注册: {list(_REGISTRY.keys())}")
    return _REGISTRY[format_id](**kwargs)


def available_formats() -> List[str]:
    """返回所有已注册的格式标识符"""
    return list(_REGISTRY.keys())
