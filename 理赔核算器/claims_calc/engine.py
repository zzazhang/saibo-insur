# -*- coding: utf-8 -*-
"""核算编排：科目 → 大类 → 汇总。"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

from . import coerce, policies, settlement
from .formulas import assess_item

_HERE = os.path.dirname(os.path.abspath(__file__))
_CATALOG_PATH = os.path.join(_HERE, "data", "catalog.json")

_CATALOG_CACHE: Optional[Dict[str, Any]] = None


def get_catalog() -> Dict[str, Any]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            _CATALOG_CACHE = json.load(f)
    return _CATALOG_CACHE


def _item_index(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {it["code"]: it for it in catalog["items"]}


def build_demo_case() -> Dict[str, Any]:
    """从 catalog 默认值组装 03 演示案输入。"""
    catalog = get_catalog()
    items: Dict[str, Any] = {}
    for meta in catalog["items"]:
        params = {}
        for p in meta.get("params") or []:
            params[p["key"]] = p.get("default")
        entry = {
            "params": params,
            "voucher": meta.get("voucher_default"),
            "include": meta.get("include_default", "ON"),
        }
        # R1-03：确认值在 p2
        if meta["formula_type"] == "r1_confirm":
            for p in meta.get("params") or []:
                if p["key"] == "p2":
                    entry["legal_confirm"] = p.get("default")
        items[meta["code"]] = entry

    categories = {}
    for cat in catalog["categories"]:
        categories[cat["code"]] = {"switch": cat.get("switch_default", "ON")}

    case_defaults = catalog.get("case_defaults") or {}
    return {
        "case_id": case_defaults.get("case_id") or "",
        "case_name": case_defaults.get("case_name") or "",
        "calc_date": case_defaults.get("calc_date") or "",
        "s1_method": catalog.get("s1_method_default") or "公式外推法",
        "sla_compensation": catalog.get("sla_default") or 0,
        "categories": categories,
        "items": items,
    }


def compute(case: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    执行完整核算。默认 soft：脏输入不 raise，写入 warnings。
    返回结构含 items / categories / summary / warnings / labels。
    """
    catalog = get_catalog()
    warnings: List[str] = []
    if case is None:
        case = build_demo_case()
    else:
        case = deepcopy(case)

    s1_method, _ = coerce.to_s1_method(case.get("s1_method"), warnings)
    sla = coerce.to_number(case.get("sla_compensation"), "sla_compensation", warnings)

    # ---- 保单解析（第②/③层的依据）--------------------------------------
    policy = case.get("policy")
    if not policy:
        policy = policies.get_policy(case.get("policy_id"))
    if case.get("policy_id") and not policy:
        warnings.append("未找到保单 %r，本次按无保单处理" % case.get("policy_id"))

    coverage_mode = case.get("coverage_mode")
    if not coverage_mode:
        coverage_mode = "policy" if policy else "manual"
    if coverage_mode == "policy" and not policy:
        warnings.append("coverage_mode 为 policy 但未指定保单，已回退为 manual")
        coverage_mode = "manual"

    # ---- 参数默认值策略 ---------------------------------------------------
    # catalog 里的 default 是给 Web 端预填演示数据用的（如 S3-01 赎金 80 万）。
    # 案例文件是「已写明的事实」，没写的科目必须记 0，否则会静默继承演示值——
    # 一个说明「未支付赎金」的案子会凭空多出 80 万核定损失，且从结果上看不出来。
    # 因此：case 显式给出 items 时默认走严格模式；Web 端的 build_demo_case 会
    # 提交全部 69 项，不受影响。可用 strict_items 显式覆盖。
    raw_items = case.get("items") or {}
    strict_items = case.get("strict_items")
    if strict_items is None:
        strict_items = bool(raw_items) and len(raw_items) < len(catalog["items"])

    extras = {"s1_method": s1_method}
    item_results: List[Dict[str, Any]] = []
    by_code: Dict[str, Dict[str, Any]] = {}

    for meta in catalog["items"]:
        code = meta["code"]
        item_input = raw_items.get(code) or {}
        declared = code in raw_items
        # 合并：缺省用 catalog 默认，便于部分提交
        merged = {
            "params": {},
            "voucher": meta.get("voucher_default"),
            "include": meta.get("include_default", "ON"),
        }
        for p in meta.get("params") or []:
            if strict_items and not declared:
                merged["params"][p["key"]] = None
            else:
                merged["params"][p["key"]] = p.get("default")
        if strict_items and not declared:
            merged["voucher"] = None
        if item_input.get("params"):
            merged["params"].update(item_input["params"])
        if "voucher" in item_input:
            merged["voucher"] = item_input.get("voucher")
        if "include" in item_input:
            merged["include"] = item_input.get("include")
        if "legal_confirm" in item_input:
            merged["legal_confirm"] = item_input.get("legal_confirm")

        # 保单模式：include 由条款责任映射决定；
        # 除非该科目显式声明 include_override=true（用于案例中论证特约扩展等情形）
        cov_meta = None
        if policy:
            cov_meta = policies.coverage_for(policy, code)
        if coverage_mode == "policy" and cov_meta is not None:
            if item_input.get("include_override"):
                merged["include"] = item_input.get("include", "ON")
            else:
                merged["include"] = (
                    "ON"
                    if cov_meta.get("status") in policies.INCLUDING_STATUSES
                    else "OFF"
                )

        result = assess_item(meta, merged, extras, warnings)
        if cov_meta is not None:
            status = cov_meta.get("status", "unmapped")
            result["coverage_status"] = status
            result["coverage_label"] = policies.STATUS_LABELS.get(status, status)
            result["coverage_clause"] = cov_meta.get("clause")
            result["coverage_note"] = cov_meta.get("note")
            result["include_override"] = bool(item_input.get("include_override"))
            if result["include_override"]:
                warnings.append(
                    "%s 手工覆盖了保单责任映射（条款判定为%s，本案强制置为 %s）"
                    % (code, result["coverage_label"], result["include"])
                )
        item_results.append(result)
        by_code[code] = result

    raw_cats = case.get("categories") or {}
    cat_results: List[Dict[str, Any]] = []
    covered_total = 0.0
    fact_total = 0.0
    s1_covered = 0.0

    for cat in catalog["categories"]:
        code = cat["code"]
        switch = coerce.to_switch(
            (raw_cats.get(code) or {}).get("switch", cat.get("switch_default", "ON")),
            "category.%s.switch" % code,
            warnings,
        )
        members = [r for r in item_results if r["category"] == code]
        assessed_subtotal = sum(m["assessed_loss"] for m in members)
        covered_sum = sum(m["covered_amount"] for m in members)
        covered_subtotal = covered_sum if switch == "ON" else 0.0
        filled_count = sum(1 for m in members if m["assessed_loss"] > 0)

        # 计入金额 = 大类 ON 且明细 ON（明细已在 covered_amount 体现）
        cat_results.append(
            {
                "code": code,
                "name": cat["name"],
                "switch": switch,
                "assessed_subtotal": assessed_subtotal,
                "covered_subtotal": covered_subtotal,
                "filled_count": filled_count,
            }
        )
        # 把大类开关下沉到明细，供结算层与前端使用（两级与关系）
        for m in members:
            m["category_switch"] = switch
            m["effective_covered"] = (
                m["covered_amount"] if switch == "ON" else 0.0
            )

        covered_total += covered_subtotal
        fact_total += assessed_subtotal
        if code == "S1":
            s1_covered = covered_subtotal

    sla_deduction = -min(sla, s1_covered)
    net = covered_total + sla_deduction

    # 间接：F8-01 + S1-03，随大类与明细开关联动（对齐汇总页 E27）
    cat_switch = {c["code"]: c["switch"] for c in cat_results}
    f8 = by_code.get("F8-01")
    s103 = by_code.get("S1-03")
    indirect = 0.0
    if cat_switch.get("F8") == "ON" and f8 and f8["include"] == "ON":
        indirect += f8["assessed_loss"]
    if cat_switch.get("S1") == "ON" and s103 and s103["include"] == "ON":
        indirect += s103["assessed_loss"]
    direct = covered_total - indirect

    # ---- 第③层：保单结算 -------------------------------------------------
    stl = settlement.settle(
        item_results,
        catalog,
        policy,
        sla_compensation=sla,
        flags=case.get("policy_flags") or {},
        warnings=warnings,
    )

    policy_info = None
    if policy:
        cov_map = policies.build_coverage_map(policy, catalog)
        policy_info = {
            "id": policy.get("id"),
            "name": policy.get("name"),
            "insurer": policy.get("insurer"),
            "product_type": policy.get("product_type"),
            "source_file": policy.get("source_file"),
            "summary": policy.get("summary"),
            "parameters_are_assumed": policy.get("parameters_are_assumed", True),
            "coverage_mode": coverage_mode,
            "coverage_stats": policies.coverage_stats(cov_map),
            "settlement_notes": policy.get("settlement_notes") or [],
        }

    # ---- 保单参数漏进事实层的检查 ----------------------------------------
    # 结算层引入前，S3-01 的赎金分项限额、F8-01 的品牌修复分项限额是作为公式
    # 变量写在行内的，事实层因此被保单参数污染：填「支付 60 万、限额 50 万」，
    # 核定损失记的是 50 万，而不是实际支付的 60 万。
    # 现在限额裁剪已由第③层负责，行内限额属于重复建模，须留空。
    if policy:
        _INROW_LIMITS = {
            "S3-01": ("p2", "赎金分项限额"),
            "F8-01": ("p3", "品牌修复分项限额"),
        }
        _sublimit_patterns = []
        for sl in ((policy.get("settlement") or {}).get("sublimits") or []):
            _sublimit_patterns.extend(sl.get("items") or [])
        for _code, (_key, _label) in _INROW_LIMITS.items():
            _entry = raw_items.get(_code) or {}
            _val = coerce.to_number(
                (_entry.get("params") or {}).get(_key), "%s.%s" % (_code, _key), []
            )
            if _val > 0 and settlement.match_any(_code, _sublimit_patterns):
                warnings.append(
                    "%s 行内填写了「%s」%s，但所选保单已在结算层为该科目设有分项限额；"
                    "行内限额会污染事实口径（核定损失记成限额而非实际发生额），请留空"
                    % (_code, _label, format(_val, ",.0f"))
                )

    labels = {
        "column_headers": catalog.get("column_headers") or {},
        "summary_headers": catalog.get("summary_headers") or {},
        "s1_method_label": catalog.get("s1_method_label"),
        "s1_methods": catalog.get("s1_methods") or [],
        "sla_row": catalog.get("sla_row") or {},
        "notes": catalog.get("notes") or [],
    }

    return {
        "case_id": case.get("case_id") or "",
        "case_name": case.get("case_name") or "",
        "calc_date": case.get("calc_date") or "",
        "s1_method": s1_method,
        "sla_compensation": sla,
        "policy_id": policy.get("id") if policy else None,
        "coverage_mode": coverage_mode,
        "policy": policy_info,
        "items": item_results,
        "categories": cat_results,
        "settlement": stl,
        "summary": {
            "covered_total": covered_total,
            "sla_deduction": sla_deduction,
            "net_assessed_loss": net,
            "indirect_subtotal": indirect,
            "direct_subtotal": direct,
            "fact_total": fact_total,
            "payable": stl.get("payable") if stl.get("applied") else None,
            "settlement_applied": bool(stl.get("applied")),
        },
        "warnings": warnings,
        "labels": labels,
    }
