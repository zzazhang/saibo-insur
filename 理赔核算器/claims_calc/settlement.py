# -*- coding: utf-8 -*-
"""
保单结算层（第三层）。

三层口径：
  ① 事实口径核定损失   —— 事故造成多少损失，不看保单        （engine + formulas）
  ② 承保过滤计入金额   —— 哪些损失属于本保单责任范围，定性  （engine 两级开关）
  ③ 保单结算赔付额     —— 属于责任范围的部分实际赔多少，定量（本模块）

结算顺序（固定，不可颠倒；顺序不同结果不同）：
  1. 取各科目「计入金额」为结算基数
  2. 营业中断(BI)特殊处理：按保单口径重算等待期/免赔额，扣减已获 SLA 赔偿
  3. 分项限额裁剪（按分项组）
  4. 每次事故免赔额（BI 若已在第 2 步扣过自身免赔额则不重复扣）
  5. 条件免赔额调整（如安全隐患未整改，免赔额上浮）
  6. 累计赔偿限额封顶

已知坑与本模块的处理：
  坑① 等待期重复扣减
      S1-01/S1-02 的公式里 p3 已经扣过一次等待期。若保单是「免赔额与等待期
      自留额取高者」（苏黎世 6.3、泰康 第八条第四款），直接在核定损失上再减
      一次免赔额就是错的。本模块把 BI 拆成 gross / waiting_retention / net
      三个量，按 bi.deductible_mode 重新组装，不在核定值上二次扣减。
  坑② 分项限额是否占用累计限额
      苏黎世 5.3 明确分项限额是累计限额的一部分、不额外增加；其他保单可能
      独立叠加。由 sublimit.shares_aggregate 显式声明。
  坑③ 免赔额的适用范围
      每次事故一个免赔额 / 每项责任各自免赔额，两种结构结果不同。
      由 deductible.scope 显式声明（per_occurrence / per_sublimit）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import coerce

# BI 科目默认集合（可被保单 settlement.bi.items 覆盖）
DEFAULT_BI_ITEMS = ("S1-01", "S1-02", "S1-03")

# 保单未声明时的兜底结算参数：不限额、不免赔，等价于「只做承保过滤」
FALLBACK_SETTLEMENT: Dict[str, Any] = {
    "aggregate_limit": 0,
    "deductible": {"scope": "per_occurrence", "amount": 0},
    "sublimits": [],
    "bi": {"deductible_mode": "waiting_only", "deductible": 0},
    "conditional_deductible": [],
}


# --------------------------------------------------------------------------
# 科目匹配
# --------------------------------------------------------------------------

def match_item(code: str, pattern: str) -> bool:
    """
    支持三种写法：
      精确科目  "S1-01"
      前缀通配  "F1-*"
      整个大类  "F1"
    """
    if not pattern:
        return False
    if pattern == code:
        return True
    if pattern.endswith("*"):
        return code.startswith(pattern[:-1])
    if "-" not in pattern:
        return code.split("-")[0] == pattern
    return False


def match_any(code: str, patterns: Any) -> bool:
    for p in patterns or []:
        if match_item(code, str(p)):
            return True
    return False


def effective_covered(r: Dict[str, Any]) -> float:
    """
    两级开关的与关系：大类 ON 且明细 ON 才真正计入。
    engine 会写入 effective_covered；缺失时退回 covered_amount。
    """
    if "effective_covered" in r:
        return float(r.get("effective_covered") or 0.0)
    return float(r.get("covered_amount") or 0.0)


def is_active(r: Dict[str, Any]) -> bool:
    return r.get("include") == "ON" and r.get("category_switch", "ON") == "ON"


# --------------------------------------------------------------------------
# 营业中断拆解（坑① 的核心）
# --------------------------------------------------------------------------

def decompose_bi(
    item_result: Dict[str, Any],
    meta: Dict[str, Any],
    max_indemnity_days: float,
    warnings: List[str],
) -> Dict[str, Any]:
    """
    把一条营业中断科目拆成 gross / waiting_retention / net。

    公式外推法 (s1_extrapolate)：
        p1 日均收入, p2 中断天数, p3 等待期, p4 毛利率, p5 影响比例
        gross   = p1 * eff_days               * p4 * p5
        waiting = p1 * MIN(eff_days, p3)      * p4 * p5
        net     = p1 * MAX(eff_days - p3, 0)  * p4 * p5   == gross - waiting
        其中 eff_days = MIN(p2, 赔偿期上限)

    财务对照法 (s1_financial)：基线-实际口径，条款里没有等待期概念，
        waiting = 0，gross = net = 核定值。

    凭证直接核定：无法拆解，退化为 gross = net = 凭证额，waiting = 0，并告警。
    """
    code = item_result["code"]
    assessed = float(item_result.get("assessed_loss") or 0.0)
    ftype = meta.get("formula_type")
    params = item_result.get("params") or {}
    voucher = float(item_result.get("voucher") or 0.0)

    out = {
        "code": code,
        "name": item_result.get("name"),
        "gross": assessed,
        "waiting_retention": 0.0,
        "net": assessed,
        "days_capped": False,
        "decomposable": False,
    }

    if assessed <= 0:
        out["decomposable"] = True
        return out

    if voucher > 0:
        warnings.append(
            "%s 使用凭证直接核定，无法拆出等待期自留额；"
            "若保单为「免赔额与等待期取高者」，本次按等待期已含在凭证内处理" % code
        )
        return out

    if ftype == "s1_extrapolate":
        def _f(key: str) -> float:
            try:
                return float(params.get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        daily, days, wait = _f("p1"), _f("p2"), _f("p3")
        margin, ratio = _f("p4"), _f("p5")

        eff_days = days
        if max_indemnity_days and max_indemnity_days > 0 and days > max_indemnity_days:
            eff_days = max_indemnity_days
            out["days_capped"] = True
            warnings.append(
                "%s 中断 %g 天超过保单赔偿期上限 %g 天，已按上限截断"
                % (code, days, max_indemnity_days)
            )

        unit = daily * margin * ratio
        out["gross"] = unit * eff_days
        out["waiting_retention"] = unit * min(eff_days, wait)
        out["net"] = unit * max(eff_days - wait, 0.0)
        out["decomposable"] = True
        out["waiting_days"] = wait
        out["effective_days"] = eff_days
        return out

    if ftype == "s1_financial":
        out["decomposable"] = True
        return out

    return out


def settle_bi(
    bi_items: List[Dict[str, Any]],
    bi_conf: Dict[str, Any],
    sla_compensation: float,
    warnings: List[str],
) -> Dict[str, Any]:
    """
    按保单口径算出营业中断的可赔基数。

    deductible_mode：
      waiting_only    仅等待期自留，无额外免赔额         base = Σnet
      deductible_only 仅免赔额，条款无等待期概念         base = Σgross − D
      higher_of       免赔额与等待期自留额取高者         base = Σgross − MAX(Σwaiting, D)
                      （苏黎世 6.3 / 泰康 第八条第四款）
      both            等待期与免赔额叠加扣减             base = Σnet − D

    SLA 抵扣在此处一并完成：已从云服务商/供应商获得的赔偿从 BI 基数中扣除，
    上限为 BI 基数本身（不会把别的责任项扣成负数）。
    """
    mode = (bi_conf or {}).get("deductible_mode") or "waiting_only"
    deduct = float((bi_conf or {}).get("deductible") or 0.0)

    gross = sum(x["gross"] for x in bi_items)
    waiting = sum(x["waiting_retention"] for x in bi_items)
    net = sum(x["net"] for x in bi_items)

    if mode == "waiting_only":
        base = net
        retention = waiting
        if deduct > 0:
            warnings.append(
                "保单 BI 口径为 waiting_only，但同时配置了免赔额 %g，已忽略；"
                "若确需叠加请改为 both" % deduct
            )
    elif mode == "deductible_only":
        base = max(gross - deduct, 0.0)
        retention = min(gross, deduct)
        if waiting > 0:
            warnings.append(
                "保单 BI 口径为 deductible_only，S1 参数中的等待期自留额 %g 未被扣减"
                "（避免与免赔额重复扣减）" % waiting
            )
    elif mode == "higher_of":
        retention = max(waiting, deduct)
        base = max(gross - retention, 0.0)
    elif mode == "both":
        base = max(net - deduct, 0.0)
        retention = waiting + min(net, deduct)
    else:
        warnings.append("未知 BI 口径 %r，已按 waiting_only 处理" % mode)
        mode = "waiting_only"
        base = net
        retention = waiting

    sla_used = min(max(sla_compensation, 0.0), base)
    base_after_sla = base - sla_used

    return {
        "mode": mode,
        "gross": gross,
        "waiting_retention": waiting,
        "net": net,
        "deductible": deduct,
        "retention_applied": retention,
        "base_before_sla": base,
        "sla_deduction": -sla_used,
        "base": base_after_sla,
        "deductible_consumed": mode in ("deductible_only", "higher_of", "both"),
    }


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

def settle(
    item_results: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    policy: Optional[Dict[str, Any]],
    sla_compensation: float = 0.0,
    flags: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    执行保单结算。policy 为 None 时返回 applied=False 的空壳结果，
    调用方可据此判断是否展示第三层。
    """
    if warnings is None:
        warnings = []
    flags = flags or {}

    covered_total = sum(effective_covered(r) for r in item_results)

    if not policy:
        return {
            "applied": False,
            "policy_id": None,
            "policy_name": None,
            "covered_total": covered_total,
            "payable": covered_total,
            "steps": [],
            "sublimits": [],
            "bi": None,
            "notes": ["未指定保单，结算层未启用；赔付额等同于计入金额"],
        }

    conf = dict(FALLBACK_SETTLEMENT)
    conf.update(policy.get("settlement") or {})
    meta_by_code = {it["code"]: it for it in catalog["items"]}

    bi_conf = conf.get("bi") or {}
    bi_codes = bi_conf.get("items") or list(DEFAULT_BI_ITEMS)
    max_days = float(bi_conf.get("max_indemnity_days") or 0.0)

    # ---- 第 2 步：BI 特殊处理 -------------------------------------------
    bi_results = [r for r in item_results if r["code"] in bi_codes and is_active(r)]
    bi_parts = [
        decompose_bi(r, meta_by_code.get(r["code"], {}), max_days, warnings)
        for r in bi_results
    ]
    bi = settle_bi(bi_parts, bi_conf, sla_compensation, warnings)
    bi["items"] = bi_parts

    if sla_compensation > 0 and not bi_results:
        warnings.append(
            "填写了已获 SLA 赔偿 %g，但本案没有计入的营业中断科目，该抵扣未生效"
            % sla_compensation
        )

    # ---- 结算基数：非 BI 科目取计入金额，BI 取上一步算出的 base ---------
    bases: Dict[str, float] = {}
    for r in item_results:
        if r["code"] in bi_codes:
            continue
        if not is_active(r):
            continue
        amt = effective_covered(r)
        if amt:
            bases[r["code"]] = amt

    base_total = sum(bases.values()) + bi["base"]

    steps: List[Dict[str, Any]] = [
        {
            "step": "计入金额（承保过滤后）",
            "amount": covered_total,
            "delta": 0.0,
            "note": "第②层结果",
        },
        {
            "step": "营业中断按保单口径重算 + SLA 抵扣",
            "amount": base_total,
            "delta": base_total - covered_total,
            "note": "BI 口径：%s；自留 %s；SLA 抵扣 %s"
            % (
                bi["mode"],
                _fmt(bi["retention_applied"]),
                _fmt(-bi["sla_deduction"]),
            ),
        },
    ]

    # ---- 第 3 步：分项限额 ----------------------------------------------
    sublimit_rows: List[Dict[str, Any]] = []
    running = dict(bases)
    bi_running = bi["base"]
    matched_codes: set = set()

    for sl in conf.get("sublimits") or []:
        patterns = sl.get("items") or []
        limit = float(sl.get("limit") or 0.0)
        hits = {c: v for c, v in running.items() if match_any(c, patterns)}
        covers_bi = any(match_any(c, patterns) for c in bi_codes)
        group_amount = sum(hits.values()) + (bi_running if covers_bi else 0.0)

        for c in hits:
            if c in matched_codes:
                warnings.append("科目 %s 同时命中多个分项限额组，请检查保单配置" % c)
            matched_codes.add(c)

        if limit > 0 and group_amount > limit:
            capped = limit
            scale = limit / group_amount if group_amount else 0.0
            for c in hits:
                running[c] = running[c] * scale
            if covers_bi:
                bi_running = bi_running * scale
        else:
            capped = group_amount

        sublimit_rows.append(
            {
                "id": sl.get("id"),
                "name": sl.get("name"),
                "clause": sl.get("clause"),
                "items": patterns,
                "limit": limit,
                "before": group_amount,
                "after": capped,
                "cut": group_amount - capped,
                "shares_aggregate": bool(sl.get("shares_aggregate", True)),
            }
        )

    unmatched = [c for c in running if c not in matched_codes]
    after_sublimits = sum(running.values()) + bi_running
    total_cut = sum(r["cut"] for r in sublimit_rows)
    if total_cut > 0:
        steps.append(
            {
                "step": "分项限额裁剪",
                "amount": after_sublimits,
                "delta": -total_cut,
                "note": "触顶 %d 个分项组"
                % sum(1 for r in sublimit_rows if r["cut"] > 0),
            }
        )
    if unmatched:
        warnings.append(
            "以下科目未落入任何分项限额组，按无分项上限处理：%s"
            % "、".join(sorted(unmatched))
        )

    # ---- 第 4/5 步：免赔额（含条件调整） --------------------------------
    ded_conf = conf.get("deductible") or {}
    ded_amount = float(ded_conf.get("amount") or 0.0)
    ded_scope = ded_conf.get("scope") or "per_occurrence"

    cond_notes: List[str] = []
    for cond in conf.get("conditional_deductible") or []:
        flag = cond.get("flag")
        if not flag or not flags.get(flag):
            continue
        ctype = cond.get("type")
        val = float(cond.get("value") or 0.0)
        if ctype == "pct_uplift":
            add = ded_amount * val
            ded_amount += add
            cond_notes.append(
                "%s：免赔额上浮 %g%%（+%s）" % (cond.get("desc") or flag, val * 100, _fmt(add))
            )
        elif ctype == "fixed_uplift":
            ded_amount += val
            cond_notes.append("%s：免赔额增加 %s" % (cond.get("desc") or flag, _fmt(val)))
        elif ctype == "exclude_all":
            cond_notes.append("%s：触发全额免赔" % (cond.get("desc") or flag))
            ded_amount = after_sublimits

    after_ded = after_sublimits
    ded_applied = 0.0

    if ded_amount > 0:
        if ded_scope == "per_occurrence":
            # BI 若已在第 2 步消耗过自身免赔额，不再重复扣（坑①）
            if bi["deductible_consumed"]:
                pool = after_sublimits - bi_running
                cut = min(ded_amount, max(pool, 0.0))
                after_ded = after_sublimits - cut
                ded_applied = cut
                if bi_running > 0:
                    cond_notes.append(
                        "营业中断已在 BI 口径中扣除自留额，本次事故免赔额不重复适用于 BI"
                    )
            else:
                cut = min(ded_amount, after_sublimits)
                after_ded = after_sublimits - cut
                ded_applied = cut
        elif ded_scope == "per_sublimit":
            total_cut2 = 0.0
            for row in sublimit_rows:
                if row["after"] <= 0:
                    continue
                cut = min(ded_amount, row["after"])
                row["deductible"] = cut
                row["after"] = row["after"] - cut
                total_cut2 += cut
            after_ded = after_sublimits - total_cut2
            ded_applied = total_cut2
        else:
            warnings.append("未知免赔额适用范围 %r，已按 per_occurrence 处理" % ded_scope)
            cut = min(ded_amount, after_sublimits)
            after_ded = after_sublimits - cut
            ded_applied = cut

        steps.append(
            {
                "step": "免赔额（%s）" % ded_scope,
                "amount": after_ded,
                "delta": -ded_applied,
                "note": "约定免赔额 %s%s"
                % (_fmt(ded_amount), "；" + "；".join(cond_notes) if cond_notes else ""),
            }
        )
    elif cond_notes:
        steps.append(
            {
                "step": "条件免赔额调整",
                "amount": after_ded,
                "delta": 0.0,
                "note": "；".join(cond_notes),
            }
        )

    after_ded = max(after_ded, 0.0)

    # ---- 第 6 步：累计限额 -----------------------------------------------
    agg = float(conf.get("aggregate_limit") or 0.0)
    payable = after_ded
    agg_cut = 0.0
    standalone = 0.0
    if agg > 0:
        # 区分「占用累计限额」与「不占用」的分项组（坑②）。
        # 免赔额已在上一步整体扣除，此处按裁剪后金额的占比把它分摊回两侧，
        # 否则不占用组会被重复扣一次免赔额。
        standalone_before = sum(
            r["after"] for r in sublimit_rows if not r.get("shares_aggregate", True)
        )
        if after_sublimits > 0:
            standalone = after_ded * (standalone_before / after_sublimits)
        else:
            standalone = 0.0
        shared = max(after_ded - standalone, 0.0)
        if shared > agg:
            agg_cut = shared - agg
            payable = agg + standalone
        if agg_cut > 0:
            steps.append(
                {
                    "step": "累计赔偿限额封顶",
                    "amount": payable,
                    "delta": -agg_cut,
                    "note": "累计限额 %s%s"
                    % (
                        _fmt(agg),
                        "；另有不占用累计限额的分项 %s" % _fmt(standalone)
                        if standalone
                        else "",
                    ),
                }
            )

    fact_total = sum(float(r.get("assessed_loss") or 0.0) for r in item_results)

    return {
        "applied": True,
        "policy_id": policy.get("id"),
        "policy_name": policy.get("name"),
        "insurer": policy.get("insurer"),
        "covered_total": covered_total,
        "base_total": base_total,
        "after_sublimits": after_sublimits,
        "deductible_amount": ded_amount,
        "deductible_applied": ded_applied,
        "deductible_scope": ded_scope,
        "aggregate_limit": agg,
        "aggregate_cut": agg_cut,
        "payable": payable,
        "self_retention": fact_total - payable,
        "payout_ratio_vs_fact": (payable / fact_total) if fact_total else 0.0,
        "payout_ratio_vs_covered": (payable / covered_total) if covered_total else 0.0,
        "steps": steps,
        "sublimits": sublimit_rows,
        "bi": bi,
        "conditional_notes": cond_notes,
        "notes": policy.get("settlement_notes") or [],
    }


def _fmt(x: float) -> str:
    try:
        return format(float(x), ",.0f")
    except (TypeError, ValueError):
        return str(x)
