# -*- coding: utf-8 -*-
"""
保单库：条款责任映射（第②层）+ 结算参数（第③层）。

承保状态六档：
  covered       条款明确承保
  limited       有限承保 / 需特约 / 需事先同意，条件满足才赔  → 计入，但标记
  conditional   附条件承保（如须公安立案、须用指定机构）       → 计入，但标记
  excluded      条款明确列为责任免除                          → 不计入
  nominal_only  条款字面列明，但国内监管实践下实际不可赔      → 不计入，本土化论证核心
  unmapped      条款中没有对应责任项                          → 不计入

nominal_only 是本项目的关键设计：它把「条款写了」与「实际赔得出来」分开记录，
典型如赎金——多数国内条款都写了网络勒索责任，但普遍带「在中国法律允许范围内」
之类的限定语，实践中不可赔。这一档让案例能同时展示两个数字。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_POLICIES_PATH = os.path.join(_HERE, "data", "policies.json")

# 计入（include=ON）的状态
INCLUDING_STATUSES = ("covered", "limited", "conditional")

STATUS_LABELS = {
    "covered": "承保",
    "limited": "有限承保",
    "conditional": "附条件承保",
    "excluded": "明确除外",
    "nominal_only": "名义承保·实际不可赔",
    "unmapped": "条款无对应责任",
}

_CACHE: Optional[Dict[str, Any]] = None


def load_policies() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(_POLICIES_PATH):
            _CACHE = {"policies": []}
        else:
            with open(_POLICIES_PATH, "r", encoding="utf-8") as f:
                _CACHE = json.load(f)
    return _CACHE


def list_policies() -> List[Dict[str, Any]]:
    """轻量列表，供前端下拉使用（不含 69 项 coverage 明细）。"""
    out = []
    for p in load_policies().get("policies", []):
        st = p.get("settlement") or {}
        out.append(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "insurer": p.get("insurer"),
                "product_type": p.get("product_type"),
                "source_file": p.get("source_file"),
                "summary": p.get("summary"),
                "aggregate_limit": st.get("aggregate_limit"),
                "deductible": (st.get("deductible") or {}).get("amount"),
                "bi_mode": (st.get("bi") or {}).get("deductible_mode"),
                "parameters_are_assumed": p.get("parameters_are_assumed", True),
            }
        )
    return out


def get_policy(policy_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not policy_id:
        return None
    for p in load_policies().get("policies", []):
        if p.get("id") == policy_id:
            return p
    return None


def coverage_for(policy: Dict[str, Any], code: str) -> Dict[str, Any]:
    """
    取某科目在该保单下的承保判定。
    优先级：items 精确条目 > categories 大类默认 > default 兜底。
    """
    cov = policy.get("coverage") or {}
    items = cov.get("items") or {}
    if code in items:
        entry = dict(items[code])
        entry.setdefault("status", cov.get("default", "unmapped"))
        return entry
    cat = code.split("-")[0]
    cats = cov.get("categories") or {}
    if cat in cats:
        entry = cats[cat]
        if isinstance(entry, str):
            return {"status": entry, "source": "category"}
        entry = dict(entry)
        entry["source"] = "category"
        return entry
    return {"status": cov.get("default", "unmapped"), "source": "default"}


def build_coverage_map(policy: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    """展开成 69 项完整映射，供前端一键应用与案例文档生成。"""
    out: Dict[str, Any] = {}
    for meta in catalog["items"]:
        code = meta["code"]
        entry = coverage_for(policy, code)
        status = entry.get("status", "unmapped")
        out[code] = {
            "code": code,
            "name": meta["name"],
            "category": meta["category"],
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "include": "ON" if status in INCLUDING_STATUSES else "OFF",
            "clause": entry.get("clause"),
            "note": entry.get("note"),
            "source": entry.get("source", "item"),
        }
    return out


def coverage_stats(coverage_map: Dict[str, Any]) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for v in coverage_map.values():
        stats[v["status"]] = stats.get(v["status"], 0) + 1
    return stats
