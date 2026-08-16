# -*- coding: utf-8 -*-
"""
命令行工具：批量跑案例、校验、导出 Markdown 报告与总览表。

    python -m claims_calc.cli list                     列出保单库
    python -m claims_calc.cli validate cases/*.json    只校验不计算
    python -m claims_calc.cli run cases/*.json         跑数并打印三层结果
    python -m claims_calc.cli run cases/*.json --md out/   同时导出 Markdown 报告
    python -m claims_calc.cli run cases/*.json --summary out/总览.md
    python -m claims_calc.cli compare cases/case-01.json --policies pingan-cyber-b,taikang-online
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from claims_calc import cases as case_io  # noqa: E402
from claims_calc import policies as pol  # noqa: E402
from claims_calc import sources as src  # noqa: E402
from claims_calc.engine import compute, get_catalog  # noqa: E402


def _money(x: Any) -> str:
    try:
        return format(float(x or 0), ",.0f")
    except (TypeError, ValueError):
        return str(x)


def _pct(x: Any) -> str:
    try:
        return "%.1f%%" % (float(x or 0) * 100)
    except (TypeError, ValueError):
        return "—"


def _expand(patterns: List[str]) -> List[str]:
    out: List[str] = []
    for p in patterns:
        hits = sorted(glob.glob(p))
        if not hits:
            print("  ! 没有匹配的文件：%s" % p)
        out.extend(hits)
    return out


# --------------------------------------------------------------------------
# Markdown 报告
# --------------------------------------------------------------------------

def render_markdown(case: Dict[str, Any], result: Dict[str, Any]) -> str:
    s = result.get("summary") or {}
    stl = result.get("settlement") or {}
    pol_info = result.get("policy") or {}
    narrative = case.get("narrative") or {}
    lines: List[str] = []

    title = case.get("case_name") or case.get("case_id") or "未命名案例"
    lines.append("# %s" % title)
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    lines.append("| 案件编号 | %s |" % (case.get("case_id") or "—"))
    lines.append("| 核算日期 | %s |" % (case.get("calc_date") or "—"))
    lines.append("| 投保产品 | %s |" % (pol_info.get("name") or "（未指定保单）"))
    lines.append("| 承保人 | %s |" % (pol_info.get("insurer") or "—"))
    lines.append("| 条款来源 | %s |" % (pol_info.get("source_file") or "—"))
    lines.append("| 责任映射模式 | %s |" % (result.get("coverage_mode") or "—"))
    lines.append("")

    if pol_info.get("parameters_are_assumed"):
        lines.append(
            "> **参数假设声明**：本案使用的分项限额、免赔额、累计限额均为演示用假设值。"
            "条款原文对这些数值的表述为「由投保人与保险人协商确定」，无公开数字。"
        )
        lines.append("")

    if narrative.get("insured"):
        lines.append("## 一、案情概要")
        lines.append("")
        lines.append(narrative["insured"])
        lines.append("")
    if narrative.get("incident"):
        lines.append("## 二、事故经过")
        lines.append("")
        lines.append(narrative["incident"])
        lines.append("")
    if narrative.get("timeline"):
        lines.append("### 时间线")
        lines.append("")
        for t in narrative["timeline"]:
            lines.append("- %s" % t)
        lines.append("")

    # 三层结果
    lines.append("## 三、三层口径结果")
    lines.append("")
    lines.append("| 口径 | 金额（元） | 说明 |")
    lines.append("| --- | ---: | --- |")
    lines.append("| ① 事实口径核定损失 | %s | 事故实际造成的损失，不看保单 |"
                 % _money(s.get("fact_total")))
    lines.append("| ② 承保过滤计入金额 | %s | 属于本保单责任范围的部分 |"
                 % _money(s.get("covered_total")))
    if stl.get("applied"):
        lines.append("| ③ 保单结算赔付额 | **%s** | 扣减限额与免赔额后的实际赔付 |"
                     % _money(stl.get("payable")))
        lines.append("")
        lines.append("- 赔付率（对事实损失）：**%s**" % _pct(stl.get("payout_ratio_vs_fact")))
        lines.append("- 赔付率（对计入金额）：%s" % _pct(stl.get("payout_ratio_vs_covered")))
        lines.append("- 被保险人自留：%s 元" % _money(stl.get("self_retention")))
    lines.append("")

    # 结算过程
    if stl.get("applied") and stl.get("steps"):
        lines.append("## 四、结算过程")
        lines.append("")
        lines.append("| 步骤 | 余额（元） | 增减 | 说明 |")
        lines.append("| --- | ---: | ---: | --- |")
        for st in stl["steps"]:
            delta = st.get("delta") or 0
            dtxt = "—" if abs(delta) < 0.005 else _money(delta)
            lines.append("| %s | %s | %s | %s |"
                         % (st.get("step"), _money(st.get("amount")), dtxt, st.get("note") or ""))
        lines.append("")

        rows = [r for r in stl.get("sublimits") or [] if r.get("before")]
        if rows:
            lines.append("### 分项限额适用情况")
            lines.append("")
            lines.append("| 分项组 | 条款依据 | 限额 | 裁剪前 | 裁剪后 | 削减 |")
            lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
            for r in rows:
                lines.append("| %s | %s | %s | %s | %s | %s |" % (
                    r.get("name"), r.get("clause") or "—", _money(r.get("limit")),
                    _money(r.get("before")), _money(r.get("after")),
                    _money(r.get("cut")) if r.get("cut") else "—"))
            lines.append("")

        bi = stl.get("bi") or {}
        if bi.get("gross"):
            lines.append("### 营业中断口径拆解")
            lines.append("")
            lines.append("| 量 | 金额（元） |")
            lines.append("| --- | ---: |")
            lines.append("| 中断毛损失（未扣等待期） | %s |" % _money(bi.get("gross")))
            lines.append("| 等待期自留额 | %s |" % _money(bi.get("waiting_retention")))
            lines.append("| 约定免赔额 | %s |" % _money(bi.get("deductible")))
            lines.append("| 实际自留（口径：%s） | %s |"
                         % (bi.get("mode"), _money(bi.get("retention_applied"))))
            lines.append("| SLA 抵扣 | %s |" % _money(bi.get("sla_deduction")))
            lines.append("| 可赔基数 | %s |" % _money(bi.get("base")))
            lines.append("")

    # 科目明细
    lines.append("## 五、科目明细与条款责任对应")
    lines.append("")
    lines.append("| 编号 | 标准科目 | 核定损失 | 承保判定 | 条款依据 | 计入 |")
    lines.append("| --- | --- | ---: | --- | --- | :---: |")
    for it in result.get("items") or []:
        if not (it.get("assessed_loss") or 0):
            continue
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            it["code"], it["name"], _money(it["assessed_loss"]),
            it.get("coverage_label") or "—",
            it.get("coverage_clause") or "—",
            "✓" if it.get("effective_covered") else "✗"))
    lines.append("")

    # 不可赔项专列
    blocked = [
        it for it in result.get("items") or []
        if (it.get("assessed_loss") or 0) > 0 and not it.get("effective_covered")
    ]
    if blocked:
        lines.append("### 已核定但不予赔付的科目")
        lines.append("")
        lines.append("| 编号 | 科目 | 金额 | 原因 |")
        lines.append("| --- | --- | ---: | --- |")
        for it in blocked:
            lines.append("| %s | %s | %s | %s%s |" % (
                it["code"], it["name"], _money(it["assessed_loss"]),
                it.get("coverage_label") or "大类未纳入本案",
                "：" + it["coverage_note"] if it.get("coverage_note") else ""))
        lines.append("")

    # 参数来源
    audit = src.audit_case(case)
    lines.append("## 六、参数来源与可信度")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("| --- | ---: |")
    lines.append("| 填写的参数总数 | %d |" % audit["total"])
    lines.append("| 已标注来源 | %d（%.0f%%） |"
                 % (audit["annotated"], audit["coverage"] * 100))
    lines.append("| 可直接引用 | %s |" % ("是" if audit["citable"] else "**否**"))
    lines.append("")

    if audit["strong"]:
        lines.append("### 已核实的参数")
        lines.append("")
        lines.append("| 参数 | 取值 | 可信度 | 来源 | 说明 |")
        lines.append("| --- | ---: | --- | --- | --- |")
        for r in audit["strong"]:
            i = r["info"]
            lines.append("| %s | %s | %s | %s | %s |" % (
                r["key"], r["value"], i["confidence_label"],
                i["source_title"] or "—", r["note"] or i["note"] or "—"))
        lines.append("")

    if audit["weak"]:
        lines.append("### 需查证或无来源的参数")
        lines.append("")
        lines.append("| 参数 | 取值 | 可信度 | 来源 | 待办 |")
        lines.append("| --- | ---: | --- | --- | --- |")
        for r in audit["weak"]:
            i = r["info"]
            lines.append("| %s | %s | **%s** | %s | %s |" % (
                r["key"], r["value"], i["confidence_label"],
                i["source_title"] or "—",
                i["action_required"] or r["note"] or i["note"] or "—"))
        lines.append("")

    if audit["missing"]:
        lines.append("### 未标注来源的参数")
        lines.append("")
        lines.append("> 以下参数没有任何出处标注。它们在计算结果中与有来源的参数"
                     "外观完全一致，但不具备可引用性——这是本案例目前最需要补齐的部分。")
        lines.append("")
        lines.append("| 参数 | 取值 |")
        lines.append("| --- | ---: |")
        for m in audit["missing"]:
            lines.append("| %s | %s |" % (m["key"], m["value"]))
        lines.append("")

    if not audit["citable"]:
        lines.append("> **引用限制**：本案例存在未标注或待查证的参数，"
                     "其计算结果可用于演示工具能力与条款结构对比，"
                     "但不得作为损失金额的实证依据对外引用。")
        lines.append("")

    if narrative.get("disputes"):
        lines.append("## 七、争议点与本土化提示")
        lines.append("")
        for d in narrative["disputes"]:
            lines.append("- %s" % d)
        lines.append("")

    notes = (pol_info.get("settlement_notes") or []) + (stl.get("notes") or [])
    if notes:
        lines.append("## 八、条款结构说明")
        lines.append("")
        for n in notes:
            lines.append("- %s" % n)
        lines.append("")

    if result.get("warnings"):
        lines.append("## 九、核算提示")
        lines.append("")
        for w in result["warnings"]:
            lines.append("- %s" % w)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*本报告由理赔核算器自动生成，数字可通过 "
                 "`python -m claims_calc.cli run <案例文件>` 复现。*")
    return "\n".join(lines)


def render_summary(rows: List[Dict[str, Any]]) -> str:
    lines = ["# 案例总览", "",
             "| 案例 | 投保产品 | 事实损失 | 计入金额 | 赔付额 | 赔付率 | 自留 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["case_name"], r["policy_name"], _money(r["fact"]), _money(r["covered"]),
            _money(r["payable"]), _pct(r["ratio"]), _money(r["retention"])))
    lines.append("")
    lines.append("*赔付率 = 保单结算赔付额 ÷ 事实口径核定损失。*")
    return "\n".join(lines)


def render_mapping(policy: Dict[str, Any], catalog: Dict[str, Any]) -> str:
    """
    导出某保单的 69 项完整条款责任对应表——案例流程第二步的交付物。
    报告里只显示已填科目，这里是全量，含未触发的科目，便于核对承保边界。
    """
    cov = pol.build_coverage_map(policy, catalog)
    stats = pol.coverage_stats(cov)
    cat_names = {c["code"]: c["name"] for c in catalog["categories"]}

    lines = ["# %s — 条款责任对应表" % policy.get("name"), ""]
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    lines.append("| 承保人 | %s |" % (policy.get("insurer") or "—"))
    lines.append("| 产品类型 | %s |" % (policy.get("product_type") or "—"))
    lines.append("| 条款来源 | %s |" % (policy.get("source_file") or "—"))
    lines.append("")
    if policy.get("summary"):
        lines.append("> %s" % policy["summary"])
        lines.append("")

    lines.append("## 承保状态分布")
    lines.append("")
    lines.append("| 状态 | 科目数 | 占比 |")
    lines.append("| --- | ---: | ---: |")
    total = len(cov)
    for key in ("covered", "limited", "conditional", "excluded", "nominal_only", "unmapped"):
        n = stats.get(key, 0)
        if not n:
            continue
        lines.append("| %s | %d | %.1f%% |"
                     % (pol.STATUS_LABELS.get(key, key), n, n * 100.0 / total))
    incl = sum(stats.get(k, 0) for k in pol.INCLUDING_STATUSES)
    lines.append("| **合计可计入** | **%d** | **%.1f%%** |" % (incl, incl * 100.0 / total))
    lines.append("")
    lines.append("> 「可计入」只表示该科目属于本保单责任范围，"
                 "不等于全额赔付——实际赔付额还要经分项限额、免赔额与累计限额裁剪。")
    lines.append("")

    lines.append("## 逐项对应")
    lines.append("")
    current = None
    for meta in catalog["items"]:
        c = cov[meta["code"]]
        if c["category"] != current:
            current = c["category"]
            lines.append("")
            lines.append("### %s %s" % (current, cat_names.get(current, "")))
            lines.append("")
            lines.append("| 编号 | 标准科目 | 承保判定 | 条款依据 | 说明 |")
            lines.append("| --- | --- | --- | --- | --- |")
        lines.append("| %s | %s | %s | %s | %s |" % (
            c["code"], c["name"], c["status_label"],
            c["clause"] or "—", c["note"] or "—"))
    lines.append("")

    notes = policy.get("settlement_notes") or []
    if notes:
        lines.append("## 结算结构说明")
        lines.append("")
        for n in notes:
            lines.append("- %s" % n)
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------

def cmd_mapping(args: argparse.Namespace) -> int:
    catalog = get_catalog()
    policy = pol.get_policy(args.policy)
    if not policy:
        print("未找到保单：%s" % args.policy)
        return 1
    text = render_mapping(policy, catalog)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("→ %s" % args.out)
    else:
        print(text)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """检查案例参数的来源标注覆盖情况。"""
    files = _expand(args.files)
    bad = 0
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            case = json.load(f)
        a = src.audit_case(case)
        mark = "✓" if a["citable"] else "✗"
        if not a["citable"]:
            bad += 1
        print("%s %s" % (mark, case.get("case_name") or os.path.basename(path)))
        print("   参数 %d 个，已标注 %d 个（%.0f%%），已核实 %d，待查证 %d，未标注 %d"
              % (a["total"], a["annotated"], a["coverage"] * 100,
                 len(a["strong"]), len(a["weak"]), len(a["missing"])))
        if args.verbose:
            for m in a["missing"]:
                print("     未标注  %-12s = %s" % (m["key"], m["value"]))
            for r in a["weak"]:
                print("     待查证  %-12s = %s  (%s)"
                      % (r["key"], r["value"], r["info"]["confidence_label"]))
        print()
    if bad:
        print("%d/%d 个案例尚不可对外引用。" % (bad, len(files)))
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    """列出参数来源库。"""
    lib = src.load()
    print(lib.get("principle", ""))
    print()
    for s_ in lib.get("sources", []):
        print("  [%s] %s" % (s_["id"], s_["title"]))
        print("      类型 %s ｜ 优先级 %s ｜ 状态 %s"
              % (s_.get("kind"), s_.get("priority"), s_.get("verification_status")))
        if s_.get("caveat"):
            print("      注意：%s" % s_["caveat"])
        print()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("保单库（%s 款）：\n" % len(pol.list_policies()))
    for p in pol.list_policies():
        print("  %-26s %s" % (p["id"], p["name"]))
        print("  %-26s %s" % ("", p.get("product_type") or ""))
        print("  %-26s 累计限额 %s ｜ 免赔额 %s ｜ BI 口径 %s%s"
              % ("", _money(p.get("aggregate_limit")), _money(p.get("deductible")),
                 p.get("bi_mode"),
                 " ｜ 参数为假设值" if p.get("parameters_are_assumed") else ""))
        print()
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    catalog = get_catalog()
    bad = 0
    for path in _expand(args.files):
        with open(path, "r", encoding="utf-8") as f:
            case = json.load(f)
        issues = case_io.validate_case(case, catalog)
        if issues:
            bad += 1
            print("✗ %s" % path)
            for i in issues:
                print("    - %s" % i)
        else:
            print("✓ %s" % path)
    print("\n%d 个文件，%d 个有问题" % (len(_expand(args.files)), bad))
    return 1 if bad else 0


def cmd_run(args: argparse.Namespace) -> int:
    catalog = get_catalog()
    files = _expand(args.files)
    rows: List[Dict[str, Any]] = []
    failed = 0

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            case = json.load(f)
        issues = case_io.validate_case(case, catalog)
        if issues and args.strict:
            print("✗ %s 校验未通过：%s" % (path, "；".join(issues)))
            failed += 1
            continue
        result = compute(case_io.strip_to_compute(case))
        s = result["summary"]
        stl = result.get("settlement") or {}
        pinfo = result.get("policy") or {}

        name = case.get("case_name") or os.path.basename(path)
        print("── %s" % name)
        print("   保单：%s" % (pinfo.get("name") or "（未指定）"))
        print("   ① 事实口径 %14s" % _money(s["fact_total"]))
        print("   ② 计入金额 %14s" % _money(s["covered_total"]))
        if stl.get("applied"):
            print("   ③ 赔付额   %14s   赔付率 %s"
                  % (_money(stl["payable"]), _pct(stl["payout_ratio_vs_fact"])))
        for w in result.get("warnings") or []:
            print("   ! %s" % w)
        print()

        rows.append({
            "case_name": name,
            "policy_name": pinfo.get("name") or "—",
            "fact": s["fact_total"],
            "covered": s["covered_total"],
            "payable": stl.get("payable") if stl.get("applied") else s["covered_total"],
            "ratio": stl.get("payout_ratio_vs_fact") if stl.get("applied") else None,
            "retention": stl.get("self_retention") if stl.get("applied") else None,
        })

        if args.md:
            os.makedirs(args.md, exist_ok=True)
            base = os.path.splitext(os.path.basename(path))[0]
            md_path = os.path.join(args.md, base + ".md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(render_markdown(case, result))
            json_path = os.path.join(args.md, base + ".result.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print("   → %s" % md_path)
            print()

    if args.summary and rows:
        os.makedirs(os.path.dirname(os.path.abspath(args.summary)) or ".", exist_ok=True)
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write(render_summary(rows))
        print("总览表 → %s" % args.summary)

    return 1 if failed else 0


def cmd_compare(args: argparse.Namespace) -> int:
    """同一案件事实跑多张保单，输出对照表——案例集里的平行对照就靠它。"""
    with open(args.file, "r", encoding="utf-8") as f:
        case = json.load(f)
    ids = [x.strip() for x in args.policies.split(",") if x.strip()]
    rows = []
    for pid in ids:
        c = dict(case_io.strip_to_compute(case))
        c["policy_id"] = pid
        c["coverage_mode"] = "policy"
        result = compute(c)
        stl = result["settlement"]
        rows.append({
            "case_name": (result.get("policy") or {}).get("name") or pid,
            "policy_name": pid,
            "fact": result["summary"]["fact_total"],
            "covered": stl["covered_total"],
            "payable": stl["payable"],
            "ratio": stl["payout_ratio_vs_fact"],
            "retention": stl["self_retention"],
        })
    text = render_summary(rows).replace("# 案例总览", "# 同一事故 · 多保单对照")
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("\n→ %s" % args.out)
    return 0


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_calc.cli", description="理赔核算器命令行工具")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="列出保单库")
    p_list.set_defaults(func=cmd_list)

    p_val = sub.add_parser("validate", help="校验案例文件结构")
    p_val.add_argument("files", nargs="+")
    p_val.set_defaults(func=cmd_validate)

    p_map = sub.add_parser("mapping", help="导出某保单的 69 项条款责任对应表")
    p_map.add_argument("policy", help="保单 id")
    p_map.add_argument("--out", help="输出 Markdown 文件")
    p_map.set_defaults(func=cmd_mapping)

    p_aud = sub.add_parser("audit", help="检查案例参数的来源标注覆盖")
    p_aud.add_argument("files", nargs="+")
    p_aud.add_argument("-v", "--verbose", action="store_true")
    p_aud.set_defaults(func=cmd_audit)

    p_src = sub.add_parser("sources", help="列出参数来源库")
    p_src.set_defaults(func=cmd_sources)

    p_run = sub.add_parser("run", help="批量跑案例")
    p_run.add_argument("files", nargs="+")
    p_run.add_argument("--md", help="同时把 Markdown 报告与结果 JSON 写到该目录")
    p_run.add_argument("--summary", help="生成总览表到指定文件")
    p_run.add_argument("--strict", action="store_true", help="校验不通过就跳过")
    p_run.set_defaults(func=cmd_run)

    p_cmp = sub.add_parser("compare", help="同一案件跑多张保单做对照")
    p_cmp.add_argument("file")
    p_cmp.add_argument("--policies", required=True, help="逗号分隔的保单 id")
    p_cmp.add_argument("--out", help="输出 Markdown 文件")
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
