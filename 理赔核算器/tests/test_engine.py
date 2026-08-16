# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from claims_calc import build_demo_case, compute, get_catalog


class TestGoldenDemo(unittest.TestCase):
    def test_demo_net(self):
        result = compute(build_demo_case())
        self.assertEqual(result["summary"]["net_assessed_loss"], 1676500.0)
        self.assertEqual(result["summary"]["covered_total"], 1676500.0)
        by = {c["code"]: c for c in result["categories"]}
        self.assertEqual(by["F1"]["covered_subtotal"], 144500.0)
        self.assertEqual(by["F2"]["covered_subtotal"], 290000.0)
        self.assertEqual(by["F3"]["covered_subtotal"], 72000.0)
        self.assertEqual(by["F6"]["covered_subtotal"], 10000.0)
        self.assertEqual(by["S1"]["covered_subtotal"], 320000.0)
        self.assertEqual(by["S2"]["covered_subtotal"], 40000.0)
        self.assertEqual(by["S3"]["covered_subtotal"], 800000.0)

    def test_item_formulas(self):
        result = compute(build_demo_case())
        by = {i["code"]: i for i in result["items"]}
        self.assertEqual(by["F1-01"]["assessed_loss"], 60000.0)
        self.assertEqual(by["F3-01"]["assessed_loss"], 72000.0)
        self.assertEqual(by["F6-02"]["assessed_loss"], 10000.0)
        self.assertEqual(by["S1-01"]["assessed_loss"], 320000.0)
        self.assertEqual(by["S1-03"]["assessed_loss"], 0.0)
        self.assertEqual(by["S3-01"]["assessed_loss"], 800000.0)


class TestSoftInput(unittest.TestCase):
    def test_empty_case_no_crash(self):
        result = compute({"items": {}, "categories": {}})
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["net_assessed_loss"], result["summary"]["covered_total"])

    def test_dirty_numbers(self):
        case = build_demo_case()
        case["items"]["F1-01"]["params"]["p1"] = "abc"
        case["items"]["F1-01"]["params"]["p2"] = ""
        case["sla_compensation"] = "不是数"
        result = compute(case)
        self.assertTrue(any("F1-01" in w for w in result["warnings"]))
        by = {i["code"]: i for i in result["items"]}
        self.assertEqual(by["F1-01"]["assessed_loss"], 0.0)

    def test_voucher_override(self):
        case = build_demo_case()
        case["items"]["F1-01"]["voucher"] = 12345
        result = compute(case)
        by = {i["code"]: i for i in result["items"]}
        self.assertEqual(by["F1-01"]["assessed_loss"], 12345.0)

    def test_category_off(self):
        case = build_demo_case()
        case["categories"]["F1"]["switch"] = "OFF"
        result = compute(case)
        by = {c["code"]: c for c in result["categories"]}
        self.assertEqual(by["F1"]["covered_subtotal"], 0.0)
        self.assertEqual(by["F1"]["assessed_subtotal"], 144500.0)
        self.assertEqual(result["summary"]["net_assessed_loss"], 1676500.0 - 144500.0)

    def test_item_off(self):
        case = build_demo_case()
        case["items"]["F1-01"]["include"] = "OFF"
        result = compute(case)
        by = {i["code"]: i for i in result["items"]}
        self.assertEqual(by["F1-01"]["assessed_loss"], 60000.0)
        self.assertEqual(by["F1-01"]["covered_amount"], 0.0)

    def test_s1_method_switch(self):
        case = build_demo_case()
        case["s1_method"] = "财务对照法"
        case["items"]["S1-03"]["params"] = {
            "p1": 1000000,
            "p2": 200000,
            "p3": 0.5,
            "p4": 1,
        }
        result = compute(case)
        by = {i["code"]: i for i in result["items"]}
        self.assertEqual(by["S1-01"]["assessed_loss"], 0.0)
        self.assertEqual(by["S1-03"]["assessed_loss"], 400000.0)

    def test_sla_cap(self):
        case = build_demo_case()
        case["sla_compensation"] = 9999999
        result = compute(case)
        self.assertEqual(result["summary"]["sla_deduction"], -320000.0)
        self.assertEqual(result["summary"]["net_assessed_loss"], 1676500.0 - 320000.0)

    def test_r1_confirm(self):
        case = build_demo_case()
        case["items"]["R1-03"]["params"]["p1"] = 50000
        case["items"]["R1-03"]["params"]["p2"] = "否"
        case["items"]["R1-03"]["voucher"] = 0
        r1 = compute(case)
        by = {i["code"]: i for i in r1["items"]}
        self.assertEqual(by["R1-03"]["assessed_loss"], 0.0)

        case["items"]["R1-03"]["params"]["p2"] = "是"
        r2 = compute(case)
        by2 = {i["code"]: i for i in r2["items"]}
        self.assertEqual(by2["R1-03"]["assessed_loss"], 50000.0)


class TestCatalog(unittest.TestCase):
    def test_size(self):
        cat = get_catalog()
        self.assertEqual(len(cat["items"]), 69)
        self.assertEqual(len(cat["categories"]), 15)
        self.assertTrue(cat["column_headers"]["name"])
        self.assertTrue(cat["summary_headers"]["net_label"])


if __name__ == "__main__":
    unittest.main()
