# -*- coding: utf-8 -*-
"""网络安全保险理赔核算器（独立前后端小应用的计算核）。"""

from .engine import build_demo_case, compute, get_catalog

__all__ = ["compute", "get_catalog", "build_demo_case"]
__version__ = "0.1.0"
