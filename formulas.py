# -*- coding: utf-8 -*-
"""科目核定损失公式（对齐 03 理赔核算器）。"""

from __future__ import annotations

from typing import Any, Dict, List

from . import coerce


def _p(params: Dict[str, float], key: str) -> float:
    return float(params.get(key, 0.0) or 0.0)


def compute_formula_amount(
    formula_type: str,
    params: Dict[str, float],
    extras: Dict[str, Any],
) -> float:
    """不含凭证覆盖的纯公式结果。"""
    if formula_type == "voucher_only":
        return 0.0

    if formula_type == "product2":
        return _p(params, "p1") * _p(params, "p2")

    if formula_type == "product3":
        return _p(params, "p1") * _p(params, "p2") * _p(params, "p3")

    if formula_type == "f3_vuln":
        # (高危*4 + 中危*2 + 低危*1) * 费率 * 加急系数
        return (
            (_p(params, "p1") * 4 + _p(params, "p2") * 2 + _p(params, "p3") * 1)
            * _p(params, "p4")
            * _p(params, "p5")
        )

    if formula_type == "f6_notify":
        # 渠道1人数*单价 + 渠道2人数*单价
        return _p(params, "p1") * _p(params, "p2") + _p(params, "p3") * _p(params, "p4")

    if formula_type == "f8_brand":
        # IF(前>0, MAX(前-后,0)/前 * 限额, 0)
        before = _p(params, "p1")
        after = _p(params, "p2")
        limit = _p(params, "p3")
        if before > 0:
            return max(before - after, 0.0) / before * limit
        return 0.0

    if formula_type == "s1_extrapolate":
        # 财务对照法时记 0；否则 日均*MAX(中断-等待,0)*毛利率*影响比例
        if extras.get("s1_method") == "财务对照法":
            return 0.0
        return (
            _p(params, "p1")
            * max(_p(params, "p2") - _p(params, "p3"), 0.0)
            * _p(params, "p4")
            * _p(params, "p5")
        )

    if formula_type == "s1_financial":
        # 公式外推法时记 0；否则 MAX(基线-实际,0)*毛利率*影响比例
        if extras.get("s1_method") == "公式外推法":
            return 0.0
        return (
            max(_p(params, "p1") - _p(params, "p2"), 0.0)
            * _p(params, "p3")
            * _p(params, "p4")
        )

    if formula_type == "max_diff":
        return max(_p(params, "p1") - _p(params, "p2"), 0.0)

    if formula_type == "s3_ransom":
        # MIN(支付, 限额)；限额<=0 则不封顶
        pay = _p(params, "p1")
        limit = _p(params, "p2")
        if limit > 0:
            return min(pay, limit)
        return pay

    if formula_type == "sum2":
        return _p(params, "p1") + _p(params, "p2")

    if formula_type == "r1_confirm":
        if extras.get("legal_confirm") == "是":
            return _p(params, "p1")
        return 0.0

    return 0.0


def assess_item(
    meta: Dict[str, Any],
    item_input: Dict[str, Any],
    extras: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    """计算单科目核定损失与计入金额。"""
    code = meta["code"]
    raw_params = item_input.get("params") or {}
    params: Dict[str, float] = {}
    display_params: Dict[str, Any] = {}
    local_extras = dict(extras)

    for pmeta in meta.get("params") or []:
        key = pmeta["key"]
        raw_val = raw_params.get(key, pmeta.get("default"))
        # R1-03 的 p2 是「是/否」文本，不当数值
        if meta["formula_type"] == "r1_confirm" and key == "p2":
            confirm = coerce.to_yes_no(raw_val, "%s.legal_confirm" % code, warnings)
            local_extras["legal_confirm"] = confirm
            display_params[key] = confirm
            continue
        num = coerce.to_number(raw_val, "%s.%s" % (code, key), warnings)
        params[key] = num
        display_params[key] = num

    if meta["formula_type"] == "r1_confirm" and "legal_confirm" not in local_extras:
        confirm_raw = item_input.get("legal_confirm")
        local_extras["legal_confirm"] = coerce.to_yes_no(
            confirm_raw, "%s.legal_confirm" % code, warnings
        )
        display_params["p2"] = local_extras["legal_confirm"]

    voucher = coerce.to_number(
        item_input.get("voucher", meta.get("voucher_default")),
        "%s.voucher" % code,
        warnings,
    )
    include = coerce.to_switch(
        item_input.get("include", meta.get("include_default", "ON")),
        "%s.include" % code,
        warnings,
    )

    if voucher > 0:
        assessed = voucher
    else:
        assessed = compute_formula_amount(meta["formula_type"], params, local_extras)

    covered = assessed if include == "ON" else 0.0

    out = {
        "code": code,
        "name": meta["name"],
        "category": meta["category"],
        "formula_desc": meta.get("formula_desc"),
        "hint": meta.get("hint"),
        "params": display_params,
        "voucher": voucher,
        "include": include,
        "assessed_loss": assessed,
        "covered_amount": covered,
    }
    if meta["formula_type"] == "r1_confirm":
        out["legal_confirm"] = local_extras.get("legal_confirm", "否")
    return out