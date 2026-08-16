# -*- coding: utf-8 -*-
"""网络安全保险理赔核算器（独立前后端小应用的计算核）。

三层口径：
  ① 事实口径核定损失   engine + formulas    事故造成多少损失，不看保单
  ② 承保过滤计入金额   engine + policies    哪些损失属于本保单责任范围
  ③ 保单结算赔付额     settlement           实际赔多少，受限额与免赔额约束
"""

from .cases import list_cases, load_case, minimize, save_case, validate_case
from .engine import build_demo_case, compute, get_catalog
from .policies import build_coverage_map, get_policy, list_policies
from .settlement import settle

__all__ = [
    "compute",
    "get_catalog",
    "build_demo_case",
    "list_policies",
    "get_policy",
    "build_coverage_map",
    "settle",
    "list_cases",
    "load_case",
    "save_case",
    "validate_case",
    "minimize",
]
__version__ = "0.3.0"
