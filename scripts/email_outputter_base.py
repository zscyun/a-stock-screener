#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screener Email Dispatch - Outputter Base Class

分层架构：输出器基类定义渲染协议。
按爸比的设计：数据源 → [读取器] → [数据对象] → [输出器]
"""

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from email_core_models import StockData, ReportContext


class Outputter(ABC):
    """
    输出器基类：定义渲染协议。

    每个子类负责一种输出格式（HTML邮件 / CLI文本 / Markdown等），
    从数据对象生成目标格式的内容并执行输出动作。
    """

    @abstractmethod
    def render(self, context: 'ReportContext', stocks: List['StockData']) -> str:
        """
        渲染内容：将结构化数据转换为目标格式的字符串。

        Args:
            context: 报告元数据（日期/版本等）
            stocks:  股票数据列表
        Returns:
            渲染后的内容字符串
        """
        pass

    @abstractmethod
    def output(self, context: 'ReportContext', stocks: List['StockData']) -> bool:
        """
        执行输出动作（发送邮件/写入文件等）。

        Args:
            context: 报告元数据
            stocks:  股票数据列表
        Returns:
            True=成功, False=失败
        """
        pass

    @property
    def output_name(self) -> str:
        """输出器名称（用于日志）"""
        return self.__class__.__name__
