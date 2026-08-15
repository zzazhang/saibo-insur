# -*- coding: utf-8 -*-
"""安全类型转换：空/脏输入不抛异常。"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple


def to_number(value: Any, field: str, warnings: List[str]) -> float:
    """把任意输入压成 float；无法解析则记 0 并 warning。"""
    if value is None:
        return 0.0
    if isinstance(value, bool):
        warnings.append("%s: 布尔值已按 %s 处理" % (field, 1 if value else 0))
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        try:
            if value != value:  # NaN
                warnings.append("%s: 无效数值，按 0 处理" % field)
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            warnings.append("%s: 无效数值，按 0 处理" % field)
            return 0.0
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text == "" or text in ("-", "—", "–", "null", "None", "n/a", "N/A"):
            return 0.0
        try:
            return float(text)
        except ValueError:
            warnings.append("%s: 无法解析 %r，按 0 处理" % (field, value))
            return 0.0
    warnings.append("%s: 不支持的类型 %s，按 0 处理" % (field, type(value).__name__))
    return 0.0


def to_switch(value: Any, field: str, warnings: List[str]) -> str:
    """仅精确 ON 计入；其它一律 OFF。"""
    if value is None or value == "":
        return "OFF"
    if isinstance(value, str):
        text = value.strip()
        if text == "ON":
            return "ON"
        if text == "OFF":
            return "OFF"
        # 宽松：英文/大小写
        if text.upper() == "ON":
            warnings.append("%s: %r 已规范为 ON" % (field, value))
            return "ON"
        warnings.append("%s: %r 非 ON，按 OFF 处理" % (field, value))
        return "OFF"
    warnings.append("%s: %r 非 ON，按 OFF 处理" % (field, value))
    return "OFF"


def to_yes_no(value: Any, field: str, warnings: List[str]) -> str:
    """法律确认等：仅「是」生效。"""
    if value is None:
        return "否"
    if isinstance(value, str):
        text = value.strip()
        if text == "是":
            return "是"
        if text == "否":
            return "否"
        if text.lower() in ("yes", "y", "true", "1"):
            warnings.append("%s: %r 已规范为「是」" % (field, value))
            return "是"
        warnings.append("%s: %r 非「是」，按「否」处理" % (field, value))
        return "否"
    warnings.append("%s: %r 非「是」，按「否」处理" % (field, value))
    return "否"


def to_s1_method(value: Any, warnings: List[str]) -> Tuple[str, Optional[str]]:
    """
    返回 (method, warning_note)。
    合法：公式外推法 / 财务对照法。
    非法：返回原清洗串，由公式层按 Excel 语义（两路都不强制清零）。
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        warnings.append("测法选择为空：S1-01/02 与 S1-03 可能同时计入，请选择一种测法")
        return "", "empty"
    if not isinstance(value, str):
        warnings.append("测法选择无效 %r：请使用「公式外推法」或「财务对照法」" % (value,))
        return "", "invalid"
    text = value.strip()
    if text in ("公式外推法", "财务对照法"):
        return text, None
    warnings.append(
        "测法选择 %r 无法识别：S1-01/02 与 S1-03 可能同时计入" % (value,)
    )
    return text, "unrecognized"
