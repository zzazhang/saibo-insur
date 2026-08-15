# -*- coding: utf-8 -*-
"""核算编排：科目 → 大类 → 汇总。"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

from . import coerce
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

    extras = {"s1_method": s1_method}
    raw_items = case.get("items") or {}
    item_results: List[Dict[str, Any]] = []
    by_code: Dict[str, Dict[str, Any]] = {}

    for meta in catalog["items"]:
        code = meta["code"]
        item_input = raw_items.get(code) or {}
        # 合并：缺省用 catalog 默认，便于部分提交
        merged = {
            "params": {},
            "voucher": meta.get("voucher_default"),
            "include": meta.get("include_default", "ON"),
        }
        for p in meta.get("params") or []:
            merged["params"][p["key"]] = p.get("default")
        if item_input.get("params"):
            merged["params"].update(item_input["params"])
        if "voucher" in item_input:
            merged["voucher"] = item_input.get("voucher")
        if "include" in item_input:
            merged["include"] = item_input.get("include")
        if "legal_confirm" in item_input:
            merged["legal_confirm"] = item_input.get("legal_confirm")

        result = assess_item(meta, merged, extras, warnings)
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
        "items": item_results,
        "categories": cat_results,
        "summary": {
            "covered_total": covered_total,
            "sla_deduction": sla_deduction,
            "net_assessed_loss": net,
            "indirect_subtotal": indirect,
            "direct_subtotal": direct,
            "fact_total": fact_total,
        },
        "warnings": warnings,
        "labels": labels,
    }
