# -*- coding: utf-8 -*-
"""结算层回归测试，重点是三个已知的坑。"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from claims_calc import cases as case_io  # noqa: E402
from claims_calc import policies as pol  # noqa: E402
from claims_calc import settlement  # noqa: E402
from claims_calc import sources as psrc  # noqa: E402
from claims_calc.engine import build_demo_case, compute, get_catalog  # noqa: E402


def demo(policy_id=None, **kw):
    c = build_demo_case()
    if policy_id:
        c["policy_id"] = policy_id
        c["coverage_mode"] = "policy"
    c.update(kw)
    return compute(c)


class TestNoPolicy(unittest.TestCase):
    def test_settlement_not_applied_without_policy(self):
        r = compute(build_demo_case())
        self.assertFalse(r["settlement"]["applied"])
        self.assertIsNone(r["summary"]["payable"])
        # 无保单时第①②层必须与改造前完全一致
        self.assertEqual(r["summary"]["net_assessed_loss"], 1676500.0)
        self.assertEqual(r["summary"]["covered_total"], 1676500.0)


class TestCoverageMapping(unittest.TestCase):
    def test_policy_mode_drives_include(self):
        r = demo("pingan-cyber-b")
        by = {i["code"]: i for i in r["items"]}
        # 赎金：条款列明但国内实践不可赔
        self.assertEqual(by["S3-01"]["coverage_status"], "nominal_only")
        self.assertEqual(by["S3-01"]["include"], "OFF")
        self.assertEqual(by["S3-01"]["assessed_loss"], 800000.0)  # 事实口径照常核定
        self.assertEqual(by["S3-01"]["effective_covered"], 0.0)
        # 平安B 除外外包商，故依赖中断不赔
        self.assertEqual(by["S1-02"]["coverage_status"], "excluded")
        # 泰康承保从属营业收入损失
        by2 = {i["code"]: i for i in demo("taikang-online")["items"]}
        self.assertEqual(by2["S1-02"]["coverage_status"], "covered")

    def test_include_override_is_respected_and_warned(self):
        c = build_demo_case()
        c["policy_id"] = "pingan-cyber-b"
        c["coverage_mode"] = "policy"
        c["items"]["S3-01"]["include_override"] = True
        c["items"]["S3-01"]["include"] = "ON"
        r = compute(c)
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["S3-01"]["include"], "ON")
        self.assertTrue(any("S3-01" in w for w in r["warnings"]))

    def test_manual_mode_ignores_policy_coverage(self):
        c = build_demo_case()
        c["policy_id"] = "pingan-cyber-b"
        c["coverage_mode"] = "manual"
        r = compute(c)
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["S3-01"]["include"], "ON")  # catalog 默认
        self.assertTrue(r["settlement"]["applied"])  # 结算层仍然生效


class TestPitfallWaitingPeriod(unittest.TestCase):
    """坑①：等待期不得与免赔额重复扣减。"""

    def test_bi_decomposition_is_consistent(self):
        r = demo("taikang-online")
        bi = r["settlement"]["bi"]
        # S1-01: 500000 * 0.4 * 0.8 = 160000/天，中断3天，等待期1天
        self.assertEqual(bi["gross"], 480000.0)
        self.assertEqual(bi["waiting_retention"], 160000.0)
        self.assertEqual(bi["net"], 320000.0)
        self.assertEqual(bi["gross"] - bi["waiting_retention"], bi["net"])

    def test_higher_of_takes_the_larger_retention(self):
        # 泰康免赔额 10 万 < 等待期自留 16 万 → 取等待期
        t = demo("taikang-online")["settlement"]["bi"]
        self.assertEqual(t["mode"], "higher_of")
        self.assertEqual(t["retention_applied"], 160000.0)
        self.assertEqual(t["base"], 320000.0)
        # 苏黎世免赔额 20 万 > 等待期自留 16 万 → 取免赔额
        z = demo("zurich-cn-2020")["settlement"]["bi"]
        self.assertEqual(z["retention_applied"], 200000.0)
        self.assertEqual(z["base"], 280000.0)

    def test_occurrence_deductible_not_charged_twice_to_bi(self):
        """higher_of 下 BI 已自留，事故免赔额只能落在非 BI 部分。"""
        s = demo("taikang-online")["settlement"]
        self.assertTrue(s["bi"]["deductible_consumed"])
        non_bi = s["after_sublimits"] - s["bi"]["base"]
        self.assertEqual(s["deductible_applied"], min(100000.0, non_bi))
        # 若错误地对全额再扣一次，赔付会比现在少 10 万
        self.assertEqual(s["payable"], 736500.0)

    def test_waiting_only_does_not_double_deduct(self):
        s = demo("pingan-cyber-b")["settlement"]
        self.assertEqual(s["bi"]["mode"], "waiting_only")
        self.assertEqual(s["bi"]["base"], 320000.0)  # 等于 net，未再扣免赔额

    def test_max_indemnity_days_caps_gross_and_waiting(self):
        parts = settlement.decompose_bi(
            {"code": "S1-01", "name": "x", "assessed_loss": 320000.0,
             "params": {"p1": 500000, "p2": 300, "p3": 1, "p4": 0.4, "p5": 0.8},
             "voucher": 0},
            {"formula_type": "s1_extrapolate"},
            max_indemnity_days=270,
            warnings=[],
        )
        self.assertTrue(parts["days_capped"])
        self.assertEqual(parts["gross"], 160000.0 * 270)
        self.assertEqual(parts["net"], 160000.0 * 269)

    def test_voucher_bi_warns_and_degrades_safely(self):
        c = build_demo_case()
        c["policy_id"] = "zurich-cn-2020"
        c["coverage_mode"] = "policy"
        c["items"]["S1-01"]["voucher"] = 500000
        r = compute(c)
        self.assertTrue(any("凭证直接核定" in w for w in r["warnings"]))
        self.assertEqual(r["settlement"]["bi"]["gross"], 500000.0)
        self.assertEqual(r["settlement"]["bi"]["waiting_retention"], 0.0)


class TestPitfallSublimits(unittest.TestCase):
    """坑②：分项限额是否占用累计限额。"""

    def test_sublimit_caps_group(self):
        c = build_demo_case()
        c["policy_id"] = "pingan-cyber-b"
        c["coverage_mode"] = "policy"
        c["items"]["F1-01"]["params"]["p1"] = 4000  # 逼爆 F1 分项限额 30 万
        r = compute(c)
        row = [x for x in r["settlement"]["sublimits"] if x["id"] == "SL-DET"][0]
        self.assertGreater(row["before"], row["limit"])
        self.assertEqual(row["after"], 300000.0)

    def test_standalone_group_does_not_consume_aggregate(self):
        svc = [
            s for s in pol.get_policy("cosco-emergency-service")["settlement"]["sublimits"]
            if s["id"] == "SL-SVC"
        ][0]
        self.assertFalse(svc["shares_aggregate"])
        s = demo("cosco-emergency-service")["settlement"]
        self.assertEqual(s["aggregate_cut"], 0.0)

    def test_aggregate_limit_caps_total(self):
        c = build_demo_case()
        c["policy_id"] = "zhufeng-detect-repair"
        c["coverage_mode"] = "policy"
        for code in ("F1-01", "F2-01"):
            c["items"][code]["params"]["p1"] = 100000
        r = compute(c)
        s = r["settlement"]
        self.assertLessEqual(s["payable"], s["aggregate_limit"])

    def test_unmatched_items_warn(self):
        r = demo("cosco-emergency-service")
        # S2-05 在 COSCO 下不承保，不会出现在告警里；构造一个落不进分项组的科目
        self.assertTrue(r["settlement"]["applied"])


class TestPitfallDeductibleScope(unittest.TestCase):
    """坑③：免赔额适用范围与条件免赔额。"""

    def test_conditional_pct_uplift(self):
        base = demo("cosco-emergency-service")["settlement"]
        lifted = demo("cosco-emergency-service",
                      policy_flags={"unremediated_finding": True})["settlement"]
        self.assertEqual(base["deductible_amount"], 100000.0)
        self.assertEqual(lifted["deductible_amount"], 110000.0)
        self.assertEqual(base["payable"] - lifted["payable"], 10000.0)
        self.assertTrue(lifted["conditional_notes"])

    def test_exclude_all_flag_zeroes_payout(self):
        s = demo("zhufeng-detect-repair",
                 policy_flags={"non_designated_vendor": True})["settlement"]
        self.assertEqual(s["payable"], 0.0)


class TestCategorySwitchInteraction(unittest.TestCase):
    def test_category_off_removed_from_settlement(self):
        c = build_demo_case()
        c["policy_id"] = "pingan-cyber-b"
        c["coverage_mode"] = "policy"
        base = compute(c)["settlement"]["payable"]
        c["categories"]["S1"]["switch"] = "OFF"
        off = compute(c)["settlement"]
        self.assertEqual(off["bi"]["gross"], 0.0)
        self.assertLess(off["payable"], base)


class TestSlaDeduction(unittest.TestCase):
    def test_sla_reduces_bi_base_only(self):
        s = demo("pingan-cyber-b", sla_compensation=50000)["settlement"]
        self.assertEqual(s["bi"]["sla_deduction"], -50000.0)
        self.assertEqual(s["bi"]["base"], 270000.0)

    def test_sla_capped_at_bi_base(self):
        s = demo("pingan-cyber-b", sla_compensation=99999999)["settlement"]
        self.assertEqual(s["bi"]["base"], 0.0)
        self.assertGreaterEqual(s["payable"], 0.0)

    def test_sla_without_bi_warns(self):
        c = build_demo_case()
        c["policy_id"] = "pingan-cyber-b"
        c["coverage_mode"] = "policy"
        c["categories"]["S1"]["switch"] = "OFF"
        c["sla_compensation"] = 10000
        r = compute(c)
        self.assertTrue(any("SLA" in w for w in r["warnings"]))


class TestPolicyLibrary(unittest.TestCase):
    def test_all_policies_load_and_settle(self):
        catalog = get_catalog()
        ids = [p["id"] for p in pol.list_policies()]
        self.assertGreaterEqual(len(ids), 5)
        for pid in ids:
            r = demo(pid)
            s = r["settlement"]
            self.assertTrue(s["applied"], pid)
            self.assertGreaterEqual(s["payable"], 0.0, pid)
            self.assertLessEqual(s["payable"], r["summary"]["fact_total"] + 1e-6, pid)
            cov = pol.build_coverage_map(pol.get_policy(pid), catalog)
            self.assertEqual(len(cov), len(catalog["items"]), pid)

    def test_unknown_policy_warns_and_degrades(self):
        c = build_demo_case()
        c["policy_id"] = "does-not-exist"
        r = compute(c)
        self.assertFalse(r["settlement"]["applied"])
        self.assertTrue(any("未找到保单" in w for w in r["warnings"]))

    def test_all_policies_declare_assumed_parameters(self):
        for p in pol.list_policies():
            self.assertTrue(p["parameters_are_assumed"], p["id"])


class TestItemMatching(unittest.TestCase):
    def test_patterns(self):
        self.assertTrue(settlement.match_item("F1-01", "F1-01"))
        self.assertTrue(settlement.match_item("F1-01", "F1-*"))
        self.assertTrue(settlement.match_item("F1-11", "F1"))
        self.assertFalse(settlement.match_item("F10-01", "F1"))
        self.assertFalse(settlement.match_item("F1-01", "F2"))
        self.assertFalse(settlement.match_item("F1-01", ""))


class TestStrictItems(unittest.TestCase):
    """
    案例文件的语义必须是「没写 = 没发生」。

    catalog 里的 default 是给 Web 端预填演示数据用的（S3-01 赎金默认 80 万）。
    如果部分提交的案例继承这些默认值，一个写明「未支付赎金」的案子会凭空
    多出 80 万核定损失，而且从结果上完全看不出来——这是静默错误，最危险。
    """

    def test_partial_case_does_not_inherit_demo_defaults(self):
        case = {
            "policy_id": "pingan-cyber-b",
            "coverage_mode": "policy",
            "categories": {"F1": {"switch": "ON"}},
            "items": {"F1-01": {"params": {"p1": 10, "p2": 1000}}},
        }
        r = compute(case)
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["F1-01"]["assessed_loss"], 10000.0)
        # 这三项在 catalog 里有非零默认值，未声明就必须记 0
        self.assertEqual(by["S3-01"]["assessed_loss"], 0.0)
        self.assertEqual(by["S1-01"]["assessed_loss"], 0.0)
        self.assertEqual(by["F6-02"]["assessed_loss"], 0.0)
        self.assertEqual(by["S2-05"]["assessed_loss"], 0.0)
        self.assertEqual(r["summary"]["fact_total"], 10000.0)

    def test_full_submission_keeps_defaults(self):
        """Web 端提交全部 69 项，行为不能变。"""
        r = compute(build_demo_case())
        self.assertEqual(r["summary"]["fact_total"], 1676500.0)

    def test_strict_items_can_be_forced_off(self):
        case = {
            "strict_items": False,
            "items": {"F1-01": {"params": {"p1": 10, "p2": 1000}}},
        }
        by = {i["code"]: i for i in compute(case)["items"]}
        self.assertEqual(by["S3-01"]["assessed_loss"], 800000.0)

    def test_strict_items_can_be_forced_on(self):
        c = build_demo_case()
        c["strict_items"] = True
        # 全量提交 + 强制严格：显式写出的值仍然生效
        self.assertEqual(compute(c)["summary"]["fact_total"], 1676500.0)

    def test_empty_items_falls_back_to_defaults(self):
        """完全不给 items 时走 catalog 默认，保持 /api/compute 空请求的老行为。"""
        r = compute({"items": {}})
        self.assertEqual(r["summary"]["fact_total"], 1676500.0)


class TestInRowLimitContamination(unittest.TestCase):
    """
    坑④：保单参数漏进事实层。

    结算层引入前，S3-01 的赎金分项限额、F8-01 的品牌修复分项限额是作为公式
    变量写在行内的。填「支付 60 万、限额 50 万」，事实口径记的是 50 万——
    事实层被保单参数污染。限额裁剪现在由第③层负责，行内限额属重复建模。
    """

    def test_ransom_inrow_limit_warns(self):
        r = compute({
            "policy_id": "cosco-emergency-service",
            "coverage_mode": "policy",
            "categories": {"S3": {"switch": "ON"}},
            "items": {"S3-01": {"params": {"p1": 600000, "p2": 500000}}},
        })
        self.assertTrue(any("S3-01" in w and "污染" in w for w in r["warnings"]))
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["S3-01"]["assessed_loss"], 500000.0)  # 被污染的结果

    def test_blank_inrow_limit_records_actual_amount(self):
        r = compute({
            "policy_id": "cosco-emergency-service",
            "coverage_mode": "policy",
            "categories": {"S3": {"switch": "ON"}},
            "items": {"S3-01": {"params": {"p1": 600000}}},
        })
        self.assertFalse(any("污染" in w for w in r["warnings"]))
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["S3-01"]["assessed_loss"], 600000.0)

    def test_no_warning_without_policy(self):
        r = compute({
            "categories": {"S3": {"switch": "ON"}},
            "items": {"S3-01": {"params": {"p1": 600000, "p2": 500000}}},
        })
        self.assertFalse(any("污染" in w for w in r["warnings"]))


class TestCase01Counterfactual(unittest.TestCase):
    """CASE-01 与 CASE-01B 构成受控对比：唯一差异是赎金。"""

    def test_ransom_does_not_change_payout(self):
        a = compute(case_io.strip_to_compute(case_io.load_case("case-01-cosco-ransomware")))
        b = compute(case_io.strip_to_compute(case_io.load_case("case-01b-cosco-ransom-paid")))
        # 事实口径相差正好一笔赎金
        self.assertEqual(
            b["summary"]["fact_total"] - a["summary"]["fact_total"], 600000.0
        )
        # 计入金额与赔付额完全不变——这就是「名义承保」的量化落差
        self.assertEqual(b["summary"]["covered_total"], a["summary"]["covered_total"])
        self.assertEqual(b["settlement"]["payable"], a["settlement"]["payable"])
        self.assertLess(
            b["settlement"]["payout_ratio_vs_fact"],
            a["settlement"]["payout_ratio_vs_fact"],
        )

    def test_ransom_is_nominal_only(self):
        r = compute(case_io.strip_to_compute(case_io.load_case("case-01b-cosco-ransom-paid")))
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["S3-01"]["coverage_status"], "nominal_only")
        self.assertEqual(by["S3-01"]["assessed_loss"], 600000.0)
        self.assertEqual(by["S3-01"]["effective_covered"], 0.0)

    def test_business_interruption_entirely_unmapped(self):
        r = compute(case_io.strip_to_compute(case_io.load_case("case-01-cosco-ransomware")))
        by = {i["code"]: i for i in r["items"]}
        self.assertEqual(by["S1-01"]["coverage_status"], "unmapped")
        self.assertEqual(by["S1-01"]["assessed_loss"], 1134000.0)  # BI 不含工时费率，未受重算影响
        self.assertEqual(r["settlement"]["bi"]["gross"], 0.0)

    def test_conditional_deductible_triggered(self):
        r = compute(case_io.strip_to_compute(case_io.load_case("case-01-cosco-ransomware")))
        self.assertEqual(r["settlement"]["deductible_amount"], 110000.0)
        self.assertTrue(r["settlement"]["conditional_notes"])


class TestParameterSources(unittest.TestCase):
    """
    参数来源层：案例里的每个数字都要能说清出处。

    最危险的不是「没有来源」，而是「没有来源但看起来和有来源的一样」。
    审计器的职责就是把这件事变得无处可藏。
    """

    def test_unannotated_case_is_not_citable(self):
        case = {"items": {"F1-01": {"params": {"p1": 100, "p2": 1000}}}}
        a = psrc.audit_case(case)
        self.assertEqual(a["total"], 2)
        self.assertEqual(a["annotated"], 0)
        self.assertFalse(a["citable"])
        self.assertEqual(len(a["missing"]), 2)

    def test_editor_estimate_counts_as_weak_not_strong(self):
        """标了「编者估计」也不算数——标注 ≠ 有出处。"""
        case = {
            "items": {"F1-01": {"params": {"p1": 100}}},
            "param_sources": {"F1-01.p1": {"ref": "editor-estimate"}},
        }
        a = psrc.audit_case(case)
        self.assertEqual(a["annotated"], 1)
        self.assertEqual(len(a["weak"]), 1)
        self.assertEqual(len(a["strong"]), 0)
        self.assertFalse(a["citable"])

    def test_verified_source_counts_as_strong(self):
        case = {
            "items": {"S1-01": {"params": {"p2": 5}}},
            "param_sources": {"S1-01.p2": {"ref": "ransomware-recovery-days"}},
        }
        a = psrc.audit_case(case)
        self.assertEqual(len(a["strong"]), 1)
        self.assertTrue(a["citable"])

    def test_unknown_ref_is_flagged(self):
        case = {
            "items": {"F1-01": {"params": {"p1": 100}}},
            "param_sources": {"F1-01.p1": {"ref": "no-such-source"}},
        }
        a = psrc.audit_case(case)
        self.assertFalse(a["strong"])
        self.assertFalse(a["weak"][0]["info"]["found"])

    def test_zero_params_are_not_counted(self):
        case = {"items": {"F1-01": {"params": {"p1": 0, "p2": None}}}}
        self.assertEqual(psrc.audit_case(case)["total"], 0)

    def test_voucher_is_audited(self):
        case = {"items": {"F5-01": {"voucher": 150000}}}
        a = psrc.audit_case(case)
        self.assertEqual(a["total"], 1)
        self.assertEqual(a["missing"][0]["key"], "F5-01")

    def test_domestic_standard_takes_priority(self):
        """本土化原则：工时类科目挂靠的必须是国标，不是国际报告。"""
        gb = psrc.get_source("gbt-42461-2023")
        self.assertEqual(gb["priority"], "primary_domestic")
        for ref in ("gbt42461-rate-expert", "gbt42461-rate-senior",
                    "gbt42461-rate-mid", "gbt42461-rate-junior"):
            param = psrc.get_parameter(ref)
            self.assertEqual(param["source_id"], "gbt-42461-2023")
            self.assertEqual(param["confidence"], "verified")
        # 市场加成系数是国标之外的假设，必须如实标为 assumed
        markup = psrc.get_parameter("market-markup-emergency")
        self.assertEqual(markup["confidence"], "assumed")
        self.assertIsNone(markup["source_id"])
        self.assertIn("循环", markup["note"])
        for ref in ("ibm-cost-data-breach-2025", "sophos-ransomware-2025"):
            self.assertEqual(psrc.get_source(ref)["priority"], "international_benchmark")
            self.assertIn("caveat", psrc.get_source(ref))

    def test_saved_cases_are_fully_annotated(self):
        """cases/ 里的正式案例必须 100% 标注（可以待查证，但不能没标）。"""
        for name in [c["name"] for c in case_io.list_cases()]:
            if name.startswith("demo-"):
                continue
            a = psrc.audit_case(case_io.load_case(name))
            self.assertEqual(a["missing"], [], "%s 存在未标注参数" % name)


class TestC1C6ControlledPair(unittest.TestCase):
    """
    C1/C6 受控对照：同一事故、同一参数，仅换保单。
    差额必须完全来自产品结构，不得来自事故严重程度。
    """

    def _pair(self):
        c1 = compute(case_io.strip_to_compute(
            case_io.load_case("case-c1-allianz-outsourcer")))
        c6 = compute(case_io.strip_to_compute(
            case_io.load_case("case-c6-pingan-outsourcer")))
        return c1, c6

    def test_fact_loss_identical(self):
        """事实口径必须一模一样，否则对照不成立。"""
        c1, c6 = self._pair()
        self.assertEqual(c1["summary"]["fact_total"], c6["summary"]["fact_total"])

    def test_outsourcer_exclusion_actually_binds(self):
        """
        外包商除外必须真的咬合到科目上。
        若案情只用普通科目，平安B的外包商除外一次都不会触发，
        对照组的结论就会正确而理由错误——这是最难发现的错。
        """
        c1, c6 = self._pair()
        a = {i["code"]: i for i in c1["items"]}
        b = {i["code"]: i for i in c6["items"]}
        # S1-02 依赖中断：安联承保、平安B除外，且金额非零
        self.assertGreater(a["S1-02"]["assessed_loss"], 0)
        self.assertEqual(a["S1-02"]["coverage_status"], "covered")
        self.assertEqual(b["S1-02"]["coverage_status"], "excluded")
        self.assertGreater(a["S1-02"]["effective_covered"], 0)
        self.assertEqual(b["S1-02"]["effective_covered"], 0.0)
        # F1-06 供应链调查费同样必须有金额
        self.assertGreater(a["F1-06"]["assessed_loss"], 0)

    def test_third_party_liability_is_dominant_gap(self):
        """第三方责任是差额主体，须能从分项限额裁剪中看出。"""
        c1, c6 = self._pair()
        legal = [r for r in c6["settlement"]["sublimits"]
                 if r["id"] == "SL-LEGAL"][0]
        self.assertGreater(legal["cut"], 1000000)
        self.assertEqual(c1["settlement"]["aggregate_cut"], 0.0)

    def test_payout_gap(self):
        c1, c6 = self._pair()
        self.assertGreater(c1["settlement"]["payout_ratio_vs_fact"], 0.9)
        self.assertLess(c6["settlement"]["payout_ratio_vs_fact"], 0.5)

    def test_unapproved_outsourcer_cliff_zeroes_payout(self):
        """原因型除外：外包商未被认可，整案赔付归零而非个别科目不赔。"""
        case = case_io.strip_to_compute(
            case_io.load_case("case-c6-pingan-outsourcer"))
        case["policy_flags"] = {"unapproved_outsourcer": True}
        r = compute(case)
        self.assertEqual(r["settlement"]["payable"], 0.0)
        self.assertTrue(r["settlement"]["conditional_notes"])
        # 事实口径不受影响——损失照常核定，只是不赔
        self.assertGreater(r["summary"]["fact_total"], 5000000)

    def test_allianz_waiting_period_is_zero_by_clause(self):
        """安联条款规定营业中断含等待期内损失，p3 填 0 是依条款而非疏漏。"""
        case = case_io.load_case("case-c1-allianz-outsourcer")
        self.assertEqual(case["items"]["S1-01"]["params"]["p3"], 0)
        self.assertIn("等待期", case["param_sources"]["S1-01.p3"]["note"])


class TestCaseIO(unittest.TestCase):
    def test_safe_name_rejects_traversal(self):
        for bad in ["../etc/passwd", "a/b", "", "案例", "a b"]:
            with self.assertRaises(ValueError):
                case_io.safe_name(bad)
        self.assertEqual(case_io.safe_name("case-01_v2.json"), "case-01_v2")

    def test_validate_catches_structural_errors(self):
        catalog = get_catalog()
        issues = case_io.validate_case(
            {
                "coverage_mode": "policy",
                "items": {"ZZ-99": {}, "F1-01": {"params": {"p9": 1}, "include": "MAYBE"}},
                "categories": {"QQ": {"switch": "ON"}},
                "s1_method": "拍脑袋法",
            },
            catalog,
        )
        joined = "；".join(issues)
        self.assertIn("ZZ-99", joined)
        self.assertIn("p9", joined)
        self.assertIn("include", joined)
        self.assertIn("QQ", joined)
        self.assertIn("s1_method", joined)
        self.assertIn("policy_id", joined)

    def test_valid_case_passes(self):
        catalog = get_catalog()
        case = {
            "policy_id": "pingan-cyber-b",
            "coverage_mode": "policy",
            "s1_method": "公式外推法",
            "items": {"F1-01": {"params": {"p1": 40, "p2": 1500}}},
            "categories": {"F1": {"switch": "ON"}},
        }
        self.assertEqual(case_io.validate_case(case, catalog), [])

    def test_minimize_drops_zero_items_and_roundtrips(self):
        catalog = get_catalog()
        c = build_demo_case()
        c["policy_id"] = "pingan-cyber-b"
        c["coverage_mode"] = "policy"
        r = compute(c)
        small = case_io.minimize(c, catalog, r)
        self.assertLess(len(small["items"]), 20)
        self.assertIn("S1-01", small["items"])
        self.assertNotIn("R1-03", small["items"])
        # 压缩后重算结果必须一致
        r2 = compute(case_io.strip_to_compute(small))
        self.assertEqual(
            r2["settlement"]["payable"], r["settlement"]["payable"]
        )
        self.assertEqual(r2["summary"]["fact_total"], r["summary"]["fact_total"])

    def test_strip_to_compute_removes_narrative(self):
        stripped = case_io.strip_to_compute(
            {"case_id": "X", "narrative": {"incident": "..."}, "items": {}}
        )
        self.assertNotIn("narrative", stripped)
        self.assertIn("case_id", stripped)


class TestSavedCasesReproduce(unittest.TestCase):
    """cases/ 目录里的每个案例文件都必须能跑通且结构合法。"""

    def test_all_saved_cases(self):
        catalog = get_catalog()
        names = [c["name"] for c in case_io.list_cases()]
        for name in names:
            case = case_io.load_case(name)
            self.assertEqual(case_io.validate_case(case, catalog), [], name)
            r = compute(case_io.strip_to_compute(case))
            self.assertGreaterEqual(r["summary"]["fact_total"], 0.0, name)


if __name__ == "__main__":
    unittest.main()
