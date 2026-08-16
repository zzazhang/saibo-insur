# -*- coding: utf-8 -*-
"""
参数来源库：给案例里的每个数字标注出处与可信度。

案例文件用 param_sources 块做标注，不参与计算：

  "param_sources": {
    "F1-01.p2": {"ref": "sec-service-rate-senior", "note": "按江苏省高级级别单价折算"},
    "S1-01.p1": {"ref": "editor-estimate", "note": "按年营收 6.6 亿 ÷ 365 取整"}
  }

键的格式是 `科目编号.参数键`，或整条科目 `科目编号`（用于凭证类科目）。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "data", "parameter_sources.json")

CONFIDENCE_LABELS = {
    "verified": "已核实",
    "derived": "推算",
    "pending": "待查证",
    "assumed": "编者估计",
}

# 对外结论中不可依赖的可信度档位
WEAK_CONFIDENCE = ("pending", "assumed")

_CACHE: Optional[Dict[str, Any]] = None


def load() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(_PATH):
            _CACHE = {"sources": [], "parameters": []}
        else:
            with open(_PATH, "r", encoding="utf-8") as f:
                _CACHE = json.load(f)
    return _CACHE


def get_parameter(ref: str) -> Optional[Dict[str, Any]]:
    for p in load().get("parameters", []):
        if p.get("id") == ref:
            return p
    return None


def get_source(source_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not source_id:
        return None
    for s in load().get("sources", []):
        if s.get("id") == source_id:
            return s
    return None


def resolve(ref: str) -> Dict[str, Any]:
    """把一个 ref 展开成含来源信息的完整条目。"""
    param = get_parameter(ref)
    if not param:
        return {
            "ref": ref,
            "found": False,
            "confidence": "assumed",
            "confidence_label": "来源库中查无此条目",
        }
    src = get_source(param.get("source_id"))
    conf = param.get("confidence", "assumed")
    return {
        "ref": ref,
        "found": True,
        "label": param.get("label"),
        "unit": param.get("unit"),
        "confidence": conf,
        "confidence_label": CONFIDENCE_LABELS.get(conf, conf),
        "point": param.get("point"),
        "range": param.get("range"),
        "note": param.get("note"),
        "caveat": param.get("caveat"),
        "derivation": param.get("derivation"),
        "action_required": param.get("action_required"),
        "source_title": (src or {}).get("title"),
        "source_kind": (src or {}).get("kind"),
        "source_priority": (src or {}).get("priority"),
        "source_url": (src or {}).get("url"),
    }


def _filled_params(case: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """列出案例中实际填了值的参数键（含凭证）。"""
    out: List[Tuple[str, Any]] = []
    for code, entry in (case.get("items") or {}).items():
        for k, v in (entry.get("params") or {}).items():
            if v not in (None, "", 0, "0"):
                out.append(("%s.%s" % (code, k), v))
        if (entry.get("voucher") not in (None, "", 0, "0")):
            out.append((code, entry.get("voucher")))
    return sorted(out)


def audit_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查案例的参数标注覆盖情况。

    返回三组：已标注且可信、已标注但需查证、完全未标注。
    未标注的参数是最危险的——数字看起来和有来源的一样，但其实没有出处。
    """
    ann = case.get("param_sources") or {}
    filled = _filled_params(case)

    strong: List[Dict[str, Any]] = []
    weak: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for key, value in filled:
        entry = ann.get(key)
        if not entry:
            missing.append({"key": key, "value": value})
            continue
        info = resolve(entry.get("ref", ""))
        row = {
            "key": key,
            "value": value,
            "note": entry.get("note"),
            "info": info,
        }
        if info["confidence"] in WEAK_CONFIDENCE or not info["found"]:
            weak.append(row)
        else:
            strong.append(row)

    total = len(filled)
    return {
        "total": total,
        "annotated": total - len(missing),
        "coverage": (total - len(missing)) / total if total else 1.0,
        "strong": strong,
        "weak": weak,
        "missing": missing,
        "citable": not missing and not weak,
    }
