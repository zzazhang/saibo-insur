# -*- coding: utf-8 -*-
"""
生成 claims_calc/data/parameter_sources.json —— 案例参数的来源库。

## 为什么需要这一层

条款只管「赔什么」，不管「多少钱」。案例里的工时、费率、日均收入这些数字，
条款文本一个都给不了，必须来自外部。没有出处的数字，案例就只是格式样例，
不能当研究成果引用。

## 本土化原则（这一层的方法论立场）

**工时与服务成本类科目一律优先使用 GB/T 42461-2023 国标口径，只有在国内确无
对应数据源时才退而援引国际报告，且必须显式标注口径差异。**

理由：IBM、Sophos 的数字是全球或美国口径、以美元计。拿 444 万美元的全球均值
去核定一家中国冷链物流企业的损失，本身就是本项目所批判的「直接移植国际标准」。
参数层如果不本土化，损失分类框架的本土化就是半截子工程。

GB/T 42461-2023 恰好补上了这一块：它是与 GB/T 20986-2023（本项目 6 模块框架的
依据）同一标准族的国标，专为网络安全服务的成本预算、招投标、决算而设，
给出分省市、分级别的服务人员成本单价，且由 CCIA 每年更新。

## 可信度四档（必须如实标注，不许含糊）

  verified   在可靠来源中找到了明确数字，可直接引用
  derived    由公开方法 + 公开输入推算得出，方法可复核
  pending    方法已确认，但具体数值需查阅原始文件（标准附录、CCIA 附件等）
  assumed    无来源，编者估计——案例中必须显著标注，不得用于对外结论

用法：  python tools/build_parameter_sources.py
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_PATH = os.path.join(ROOT, "claims_calc", "data", "parameter_sources.json")


# ==========================================================================
# 来源目录
# ==========================================================================
SOURCES = [
    {
        "id": "gbt-42461-2023",
        "kind": "national_standard",
        "priority": "primary_domestic",
        "title": "GB/T 42461-2023《信息安全技术 网络安全服务成本度量指南》",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会；TC260 归口",
        "date": "2023-03-17 发布，2023-10-01 实施",
        "url": "https://std.samr.gov.cn/gb/search/gbDetailed?id=F789206610AEB223E05397BE0A0AE533",
        "scope": "网络安全服务成本预算、项目招投标、项目决算及合同编制；成本不含利润",
        "applies_to": ["F1", "F2", "F3", "F7"],
        "method": (
            "人力成本 L = Σ(Pᵢ × Qᵢ)，其中 Pᵢ 为第 i 级服务人员成本单价（元/人日），"
            "Qᵢ 为该级别总体工作量（人日）。人员日平均工资 S = 年平均工资 AS ÷ 年工作天数，"
            "每月工作天数取 20.67（依人社部发〔2025〕2 号）。"
            "再乘以人员级别调整系数 Kᵢ（分 4 级）与人力成本调整系数 H。"
        ),
        "update_mechanism": (
            "中国网络安全产业联盟（CCIA）每年依据国家统计局各省市"
            "「信息传输、软件和信息技术服务业」平均工资更新各省市各级别成本单价，"
            "以《网络安全服务成本度量实施参考》形式发布"
        ),
        "verification_status": "method_verified_values_pending",
        "caveat": (
            "本项目已确认标准的计算方法与更新机制，但尚未取得标准附录 A 的分省市"
            "单价表原文，也未取得 CCIA 年度附件。案例中所有引用该标准的单价均标为"
            "pending 或 derived，须以原始文件核对后方可对外引用。"
        ),
    },
    {
        "id": "gbt-20986-2023",
        "kind": "national_standard",
        "priority": "primary_domestic",
        "title": "GB/T 20986-2023《信息安全技术 网络安全事件分类分级指南》",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会",
        "scope": "网络安全事件分类分级；本项目 6 模块、13 项可保损失框架的依据",
        "applies_to": ["*"],
        "verification_status": "verified",
        "note": "用于事件分类与定级，不提供成本参数",
    },
    {
        "id": "stats-bureau-it-wage",
        "kind": "official_statistics",
        "priority": "primary_domestic",
        "title": "国家统计局 分省市「信息传输、软件和信息技术服务业」城镇单位就业人员平均工资",
        "publisher": "国家统计局",
        "scope": "GB/T 42461-2023 人力成本测算的基础输入",
        "applies_to": ["F1", "F2", "F3", "F7", "S4"],
        "verification_status": "pending",
        "caveat": "需按案例被保险人所在省份取对应年度数值；本项目尚未取得具体数字",
    },
    {
        "id": "ibm-cost-data-breach-2025",
        "kind": "industry_report",
        "priority": "international_benchmark",
        "title": "IBM《Cost of a Data Breach Report 2025》（Ponemon 执行）",
        "publisher": "IBM Security / Ponemon Institute",
        "sample": "17 个行业、16 个国家的 600 家发生泄露的组织，观察期 2024-03 至 2025-02",
        "url": "https://www.ibm.com/reports/data-breach",
        "applies_to": ["F6", "R1", "R2"],
        "verification_status": "verified",
        "caveat": (
            "全球/美国口径、以美元计，不可直接用于中国境内被保险人的损失核定。"
            "仅可用于：① 损失结构比例的横向参照；② 说明国际基准与本土实际的差异。"
            "2026 版已发布（全球均值升至约 499 万美元，同比 +12%），引用时须注明版本年度。"
        ),
    },
    {
        "id": "sophos-ransomware-2025",
        "kind": "industry_report",
        "priority": "international_benchmark",
        "title": "Sophos《The State of Ransomware 2025》",
        "publisher": "Sophos",
        "sample": "3,400 家过去一年内遭勒索软件攻击的组织",
        "url": "https://www.sophos.com/en-us/blog/the-state-of-ransomware-2025",
        "applies_to": ["F1", "F2", "S1", "S3"],
        "verification_status": "verified",
        "caveat": (
            "美元口径、全球样本。恢复时长分布（如 53% 一周内恢复）跨市场可比性较强，"
            "可用于校验案例设定的中断天数是否落在合理区间；但恢复「成本」金额不可直接换算。"
        ),
    },
]


# ==========================================================================
# 参数条目
# ==========================================================================
PARAMETERS = [
    # ---- 服务人员费率（本土国标口径）----
    {
        "id": "sec-service-rate-senior",
        "label": "网络安全服务人员费率·高级/专家级",
        "unit": "元/小时",
        "source_id": "gbt-42461-2023",
        "confidence": "pending",
        "point": None,
        "range": None,
        "applies_to": ["F1-01.p2", "F1-02.p2"],
        "derivation": (
            "国标口径为元/人日，本工具 catalog 的费率参数单位为元/小时，"
            "换算按 1 人日 = 8 小时。取值 = Pᵢ(高级/专家级，按被保险人所在省份) ÷ 8。"
        ),
        "action_required": (
            "需取得 GB/T 42461-2023 附录 A 或 CCIA《年度网络安全服务成本度量实施参考》"
            "附件中被保险人所在省份的对应级别单价"
        ),
    },
    {
        "id": "sec-service-rate-mid",
        "label": "网络安全服务人员费率·中级",
        "unit": "元/小时",
        "source_id": "gbt-42461-2023",
        "confidence": "pending",
        "point": None,
        "range": None,
        "applies_to": ["F2-01.p2", "F2-02.p2", "F2-04.p2", "F3-01.p4"],
        "derivation": "同上，取中级单价 ÷ 8",
        "action_required": "同 sec-service-rate-senior",
    },
    {
        "id": "sec-service-monthly-wage-anchor",
        "label": "信息传输、软件和信息技术服务业月平均工资（省际锚点）",
        "unit": "元/月",
        "source_id": "gbt-42461-2023",
        "confidence": "derived",
        "range": [10300, 36300],
        "applies_to": ["*"],
        "derivation": (
            "据 CCIA 2025 年度实施参考的公开转述：省际最高为上海约 36.3 千元/月，"
            "最低为黑龙江约 10.3 千元/月。日均工资 S = 月工资 ÷ 20.67。"
        ),
        "action_required": (
            "该区间为二手转述，须以 CCIA 原始附件核对；"
            "各级别成本单价还需再乘级别调整系数 Kᵢ 与人力成本调整系数 H"
        ),
    },
    # ---- 中断时长（国际报告可跨市场参照）----
    {
        "id": "ransomware-recovery-days",
        "label": "勒索软件事件恢复时长分布",
        "unit": "天",
        "source_id": "sophos-ransomware-2025",
        "confidence": "verified",
        "distribution": {
            "1天内完全恢复": 0.16,
            "1周内完全恢复": 0.53,
            "3个月内完全恢复": 0.97,
        },
        "applies_to": ["S1-01.p2"],
        "note": (
            "16% 一日内恢复（2024 年为 7%），53% 一周内恢复（2024 年为 35%），"
            "97% 三个月内完全恢复。案例设定的中断天数应落在该分布的合理位置并说明理由。"
        ),
    },
    {
        "id": "ransomware-recovery-cost-global",
        "label": "勒索软件恢复成本（不含赎金，全球均值）",
        "unit": "美元",
        "source_id": "sophos-ransomware-2025",
        "confidence": "verified",
        "point": 1530000,
        "note": (
            "全样本均值 153 万美元（2024 年为 273 万美元）；"
            "大型企业细分样本为 184 万美元（2024 年为 312 万美元）。"
            "两个数字口径不同，引用时须说明取的是哪个细分。"
        ),
        "applies_to": [],
        "caveat": "美元口径，仅用于量级校验，不可直接换算为人民币核定值",
    },
    {
        "id": "ransom-payment-refusal-rate",
        "label": "拒付赎金比例",
        "unit": "比例",
        "source_id": "sophos-ransomware-2025",
        "confidence": "verified",
        "point": 0.63,
        "applies_to": ["S3-01"],
        "note": (
            "2025 年 63% 的受害组织拒绝支付赎金（2024 年为 59%）。"
            "该数据支持案例设定「未支付赎金」为主流情形；"
            "在国内监管环境下，拒付比例预计更高，但缺乏公开的中国分样本。"
        ),
    },
    {
        "id": "breach-lifecycle-days",
        "label": "泄露事件识别与遏制总时长",
        "unit": "天",
        "source_id": "ibm-cost-data-breach-2025",
        "confidence": "verified",
        "point": 241,
        "note": "241 天（识别 181 天 + 遏制 60 天），为九年来最短",
        "applies_to": [],
        "caveat": "全球均值，用于校验案例时间线的合理性",
    },
    # ---- 无来源的编者估计（必须显著标注）----
    {
        "id": "editor-estimate",
        "label": "编者估计（无来源）",
        "unit": "—",
        "source_id": None,
        "confidence": "assumed",
        "applies_to": [],
        "note": (
            "用于标记所有由编者按量级设定、暂无外部出处的参数。"
            "凡引用该标记的参数，案例中必须显著声明，且不得用于对外结论。"
        ),
    },
]


def main() -> None:
    payload = {
        "schema_version": "1.0",
        "principle": (
            "工时与服务成本类科目优先使用 GB/T 42461-2023 国标口径；"
            "仅在国内确无对应数据源时才援引国际报告，且必须标注口径差异。"
            "参数层不本土化，损失分类框架的本土化就是半截子工程。"
        ),
        "confidence_levels": {
            "verified": "在可靠来源中找到明确数字，可直接引用",
            "derived": "由公开方法与公开输入推算，方法可复核",
            "pending": "方法已确认，具体数值需查阅原始文件",
            "assumed": "无来源，编者估计，不得用于对外结论",
        },
        "sources": SOURCES,
        "parameters": PARAMETERS,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("已生成 %s（%d 个来源，%d 个参数条目）"
          % (OUT_PATH, len(SOURCES), len(PARAMETERS)))


if __name__ == "__main__":
    main()
