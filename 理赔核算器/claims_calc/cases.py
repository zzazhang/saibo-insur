# -*- coding: utf-8 -*-
"""
案例文件读写。

案例 JSON 就是 /api/compute 的入参，外加几个描述性字段，落盘后即可复现。
最小可用的案例文件只需要 policy_id + 涉及科目的参数——include 交给
coverage_mode="policy" 由条款责任映射自动决定，不必手写 69 行开关。

案例文件结构：
{
  "schema_version": "1.0",
  "case_id":   "CASE-01",
  "case_name": "某电商平台遭黑客入侵致系统与数据破坏",
  "calc_date": "2026-03-15",
  "narrative": {                      # 纯描述，不参与计算
      "insured":   "被保险人画像",
      "incident":  "事故经过",
      "timeline":  ["2026-03-01 首次发现异常", ...],
      "evidence":  ["取证机构报告", ...],
      "disputes":  ["争议点", ...]
  },
  "policy_id":     "pingan-cyber-b",
  "coverage_mode": "policy",          # policy | manual
  "policy_flags":  {"unremediated_finding": false},
  "s1_method":     "公式外推法",
  "sla_compensation": 0,
  "categories": {"F1": {"switch": "ON"}, ...},
  "items": {"F1-01": {"params": {"p1": 40, "p2": 1500}}, ...}
}
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CASES_DIR = os.path.abspath(os.path.join(_HERE, "..", "cases"))

_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

# 计算相关字段（描述性字段不在此列，读取时原样保留）
COMPUTE_KEYS = (
    "case_id",
    "case_name",
    "calc_date",
    "policy_id",
    "policy",
    "coverage_mode",
    "policy_flags",
    "s1_method",
    "sla_compensation",
    "categories",
    "items",
)


def cases_dir(root: Optional[str] = None) -> str:
    return os.path.abspath(root or os.environ.get("CASES_DIR") or DEFAULT_CASES_DIR)


def safe_name(name: str) -> str:
    """
    案例文件名只允许字母、数字、下划线、连字符。

    含路径分隔符或 .. 的输入直接报错，而不是靠 basename 静默截断——
    静默把 "../etc/passwd" 改写成 "passwd" 虽然没有穿越风险，
    但会让调用方以为写对了地方，是更难查的问题。
    """
    raw = str(name or "").strip()
    if raw.lower().endswith(".json"):
        raw = raw[:-5]
    if os.sep in raw or "/" in raw or "\\" in raw or ".." in raw:
        raise ValueError("案例名不能包含路径分隔符或上级目录：%r" % name)
    if not raw or not _NAME_RE.match(raw):
        raise ValueError("案例名只能包含字母、数字、下划线和连字符：%r" % name)
    return raw


def list_cases(root: Optional[str] = None) -> List[Dict[str, Any]]:
    d = cases_dir(root)
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(d, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            out.append({"name": fn[:-5], "error": "文件无法解析", "case_name": None})
            continue
        out.append(
            {
                "name": fn[:-5],
                "case_id": data.get("case_id"),
                "case_name": data.get("case_name"),
                "policy_id": data.get("policy_id"),
                "calc_date": data.get("calc_date"),
                "updated_at": os.path.getmtime(path),
            }
        )
    return out


def load_case(name: str, root: Optional[str] = None) -> Dict[str, Any]:
    path = os.path.join(cases_dir(root), safe_name(name) + ".json")
    if not os.path.exists(path):
        raise FileNotFoundError("案例不存在：%s" % name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_case(name: str, case: Dict[str, Any], root: Optional[str] = None) -> str:
    d = cases_dir(root)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, safe_name(name) + ".json")
    payload = dict(case)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def delete_case(name: str, root: Optional[str] = None) -> bool:
    path = os.path.join(cases_dir(root), safe_name(name) + ".json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def validate_case(case: Dict[str, Any], catalog: Dict[str, Any]) -> List[str]:
    """
    结构性校验。返回问题列表（空列表 = 通过）。
    只查结构，不查业务合理性；数值脏输入由 coerce 层兜底。
    """
    issues: List[str] = []
    if not isinstance(case, dict):
        return ["案例必须是 JSON 对象"]

    valid_items = {it["code"] for it in catalog["items"]}
    valid_cats = {c["code"] for c in catalog["categories"]}
    param_keys = {
        it["code"]: {p["key"] for p in (it.get("params") or [])}
        for it in catalog["items"]
    }

    for code, entry in (case.get("items") or {}).items():
        if code not in valid_items:
            issues.append("未知科目编号：%s" % code)
            continue
        if not isinstance(entry, dict):
            issues.append("%s 的内容必须是对象" % code)
            continue
        for k in (entry.get("params") or {}):
            if k not in param_keys[code]:
                issues.append("%s 不存在参数 %s" % (code, k))
        inc = entry.get("include")
        if inc is not None and inc not in ("ON", "OFF"):
            issues.append("%s 的 include 只能是 ON 或 OFF，当前为 %r" % (code, inc))

    for code, entry in (case.get("categories") or {}).items():
        if code not in valid_cats:
            issues.append("未知大类编号：%s" % code)
        elif (entry or {}).get("switch") not in ("ON", "OFF", None):
            issues.append("大类 %s 的 switch 只能是 ON 或 OFF" % code)

    mode = case.get("coverage_mode")
    if mode not in (None, "policy", "manual"):
        issues.append("coverage_mode 只能是 policy 或 manual，当前为 %r" % mode)
    if mode == "policy" and not (case.get("policy_id") or case.get("policy")):
        issues.append("coverage_mode 为 policy 时必须指定 policy_id")

    s1 = case.get("s1_method")
    if s1 is not None and s1 not in ("公式外推法", "财务对照法", ""):
        issues.append("s1_method 只能是「公式外推法」或「财务对照法」，当前为 %r" % s1)

    return issues


def strip_to_compute(case: Dict[str, Any]) -> Dict[str, Any]:
    """去掉描述性字段，只留计算入参。"""
    return {k: v for k, v in case.items() if k in COMPUTE_KEYS}


def minimize(
    case: Dict[str, Any],
    catalog: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    压缩案例：只保留真正填过的科目，便于人工阅读与 diff。

    传入 compute() 的结果时，核定损失为 0 的科目会被整条丢弃——
    否则 catalog 里那些非零默认值（如 S1-02 的影响比例 1）会留下无意义的残渣。
    """
    zero_codes = set()
    if result:
        for r in result.get("items") or []:
            if not (r.get("assessed_loss") or 0):
                zero_codes.add(r["code"])

    # 「显式填 0」与「留空」不是一回事。
    # 例如安联条款规定营业中断包含等待期内损失，故 S1-01 的 p3 等待期须填 0；
    # 若把 0 当空值丢掉，重载时会回落到 catalog 默认的 1 天，凭空多扣一天。
    # 因此：只有当某参数的值与 catalog 默认值相同、且为空/零时才可省略。
    defaults = {}
    for meta in catalog["items"]:
        defaults[meta["code"]] = {
            p["key"]: p.get("default") for p in (meta.get("params") or [])
        }

    def _droppable(code: str, key: str, value: Any) -> bool:
        if value in (None, ""):
            return True
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        if v != 0:
            return False
        d = defaults.get(code, {}).get(key)
        try:
            return d in (None, "") or float(d) == 0.0
        except (TypeError, ValueError):
            return False

    out = dict(case)
    items = {}
    for meta in catalog["items"]:
        code = meta["code"]
        entry = (case.get("items") or {}).get(code)
        if not entry:
            continue
        if code in zero_codes and not entry.get("include_override"):
            continue
        params = {}
        for k, v in (entry.get("params") or {}).items():
            if _droppable(code, k, v):
                continue
            params[k] = v
        keep: Dict[str, Any] = {}
        if params:
            keep["params"] = params
        voucher = entry.get("voucher")
        if voucher not in (None, "", 0, "0"):
            keep["voucher"] = voucher
        if entry.get("include_override"):
            keep["include_override"] = True
            keep["include"] = entry.get("include", "ON")
        elif case.get("coverage_mode") != "policy" and entry.get("include") == "OFF":
            keep["include"] = "OFF"
        if entry.get("legal_confirm") == "是":
            keep["legal_confirm"] = "是"
        if keep:
            items[code] = keep
    out["items"] = items

    cats = {}
    for cat in catalog["categories"]:
        sw = ((case.get("categories") or {}).get(cat["code"]) or {}).get("switch")
        if sw:
            cats[cat["code"]] = {"switch": sw}
    out["categories"] = cats
    return out
