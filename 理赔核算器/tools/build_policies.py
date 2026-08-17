# -*- coding: utf-8 -*-
"""
生成 claims_calc/data/policies.json。

把 5 款真实条款的责任映射与结算参数写成可读代码，而不是手搓 JSON——
每条判断的条款出处都跟在旁边，改的时候能看见理由。

用法：  python tools/build_policies.py

重要声明
--------
条款文本里的限额、免赔额几乎全是「由投保人与保险人协商确定」，没有具体数字。
本文件中所有 settlement 数值均为**演示用假设值**，不是任何真实保单的实际条件，
每款保单的 parameters_are_assumed 均置为 true，前端与报告都会显示该标记。
责任映射（coverage）则严格依据条款分析文件，来源写在 source_file 字段。
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_PATH = os.path.join(ROOT, "claims_calc", "data", "policies.json")


# ==========================================================================
# 01 苏黎世中国网络安全保险 2020 版
# ==========================================================================
ZURICH = {
    "id": "zurich-cn-2020",
    "name": "苏黎世中国网络安全保险（2020版）",
    "insurer": "苏黎世财产保险（中国）",
    "product_type": "综合型（责任保障 + 第一方保障）",
    "source_file": "01_苏黎世中国网络安全保险2020版_analysis.md",
    "summary": "外资在华综合型产品，第一方与第三方责任齐备，含声誉损害与社工诈骗扩展；"
               "分项限额明确不额外增加累计限额（5.3），营业中断免赔额与等待期取大者（6.3）。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "covered", "clause": "条款1.7 事故响应费用",
                   "note": "涵盖调查取证、法律与合规建议、通知、公关、信用监控、呼叫中心"},
            "F2": {"status": "covered", "clause": "条款1.12 数字资产重置费用",
                   "note": "重新收集、恢复、替换、重建数字资产的合理必要费用"},
            "F3": {"status": "limited", "clause": "条款1.7 / 条款4",
                   "note": "整改加固不属独立承保项，仅在事故响应必要范围内认可"},
            "F4": {"status": "covered", "clause": "条款1.7 / 条款3.4",
                   "note": "事故响应费用含法律与合规建议"},
            "F5": {"status": "covered", "clause": "条款1.7", "note": "危机公关属事故响应费用组成部分"},
            "F6": {"status": "covered", "clause": "条款1.7", "note": "主动通知、信用监控、呼叫中心"},
            "F7": {"status": "limited", "clause": "条款1.8 减损费用与额外费用",
                   "note": "以不超过因此减少的营业收入损失为限"},
            "S1": {"status": "covered", "clause": "条款1.8 营业收入损失"},
            "S2": {"status": "unmapped"},
            "S4": {"status": "unmapped"},
            "R1": {"status": "covered", "clause": "条款1.1 安全责任 / 1.2 隐私责任"},
            "R2": {"status": "covered", "clause": "条款3.15 抗辩费用"},
        },
        "items": {
            # —— 第一方保障中的特殊项 ——
            "F1-06": {"status": "limited", "clause": "条款1.7 / 3.33.1.2",
                      "note": "服务提供商相关调查在隐私责任定义内，但供应链取证非列明项"},
            "F1-10": {"status": "covered", "clause": "条款1.16–1.18 社会工程学诈骗",
                      "note": "苏黎世少见地承保社工资金转账诈骗、信托资金与高管个人资金盗窃"},
            "F1-11": {"status": "unmapped"},
            "F2-11": {"status": "excluded", "clause": "条款4.1",
                      "note": "有形财产损害除外（隐私事件引起的人身伤害除外情形不适用于此）"},
            "F3-04": {"status": "unmapped"},
            "F3-05": {"status": "unmapped"},
            "F5-04": {"status": "unmapped"},
            "F5-05": {"status": "unmapped"},
            # —— 声誉损害：条款有责任，但口径与本模型不一致 ——
            "F8-01": {"status": "limited", "clause": "条款1.15 声誉损害 / 3.45",
                      "note": "条款承保的是声誉损害「收入损失」（赔偿期最长6个月），"
                              "口径为净利润减损，与本模型的品牌价值降幅法不一致，"
                              "使用时须改按 S1-03 财务对照口径重算"},
            # —— 营业中断 ——
            "S1-02": {"status": "covered", "clause": "条款1.9 连带营业收入损失",
                      "note": "承保服务提供商系统中断导致的连带损失；分项限额属主险保额一部分"},
            # —— 自有财产 ——
            "S2-01": {"status": "excluded", "clause": "条款4.1 / 4.15",
                      "note": "有形财产损害及照管财产遗失除外"},
            "S2-05": {"status": "unmapped"},
            # —— 赎金 ——
            "S3-01": {"status": "nominal_only", "clause": "条款1.13 网络勒索 / 3.25.1",
                      "note": "条款列明承保勒索款项，但支付前须经保险人书面同意，"
                              "且国内监管实践下向攻击者支付赎金不具可赔性"},
            # —— 第三方 ——
            "R1-06": {"status": "excluded", "clause": "条款4.2 合同违约除外"},
            "R3-01": {"status": "covered", "clause": "条款1.6 PCI-DSS 违规",
                      "note": "承保卡组织评估与调查费用及罚金，适用分项限额"},
            "R3-02": {"status": "limited", "clause": "条款1.6",
                      "note": "费率调整属后续经营损失，条款未列明，需个案协商"},
        },
    },
    "settlement": {
        "aggregate_limit": 20000000,
        "deductible": {"scope": "per_occurrence", "amount": 200000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "higher_of",
            "deductible": 200000,
            "max_indemnity_days": 180,
            "clause": "条款6.3 免赔额与等待期免赔额适用大者原则；条款3.46 恢复期不超过180天",
        },
        "sublimits": [
            {"id": "SL-IR", "name": "事故响应费用", "items": ["F1", "F4", "F5", "F6"],
             "limit": 3000000, "shares_aggregate": True, "clause": "条款5.2 / 1.7"},
            {"id": "SL-DA", "name": "数字资产重置费用", "items": ["F2", "F3"],
             "limit": 3000000, "shares_aggregate": True, "clause": "条款5.2 / 1.12"},
            {"id": "SL-BI", "name": "营业收入损失（含连带）", "items": ["S1", "F7"],
             "limit": 8000000, "shares_aggregate": True, "clause": "条款5.3.3 分项限额属主险保额一部分"},
            {"id": "SL-LIAB", "name": "责任保障（安全/隐私/抗辩）", "items": ["R1", "R2"],
             "limit": 10000000, "shares_aggregate": True, "clause": "条款5.1"},
            {"id": "SL-PCI", "name": "PCI-DSS 违规", "items": ["R3"],
             "limit": 1000000, "shares_aggregate": True, "clause": "条款5.2.3 属监管调查诉讼保额一部分"},
            {"id": "SL-REP", "name": "声誉损害", "items": ["F8"],
             "limit": 2000000, "shares_aggregate": True, "clause": "条款1.15 / 3.45"},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "条款5.3 明确：连带营业、操作失误连带营业、报酬支付、社工盗窃等分项限额"
        "均属于各自主险保额的一部分，不额外增加保额——故所有分项组 shares_aggregate 均为 true。",
        "条款6.3 营业收入损失采用「免赔额与等待期免赔额取大者」，"
        "本工具已按 higher_of 口径处理，不会在 S1 公式已扣等待期的基础上再扣一次免赔额。",
    ],
}


# ==========================================================================
# 07/11 泰康在线网络安全综合保险
# ==========================================================================
TAIKANG = {
    "id": "taikang-online",
    "name": "泰康在线网络安全综合保险",
    "insurer": "泰康在线财产保险",
    "product_type": "综合型（六项可选责任）",
    "source_file": "11_泰康在线网络安全综合保险_analysis.md",
    "summary": "国内综合型产品，六项责任可分别投保；承保从属营业收入损失与社会工程学损失；"
               "营业收入损失免赔额与等待时间自留额取较高者（第八条），恢复期限最长270天。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "covered", "clause": "第五条第一款 事故响应费用",
                   "note": "取证分析、确定合规义务、通知、建立新账号、公关、信用监控"},
            "F2": {"status": "covered", "clause": "第五条第二款 数字资产重置费用"},
            "F3": {"status": "limited", "clause": "第五条第二款 硬件改善成本 / 第三十七条第十九款",
                   "note": "须事先取得保险人同意，且以防止同类事件再次发生为限"},
            "F4": {"status": "covered", "clause": "第五条第一款 / 第三十七条第六款 法律费用"},
            "F5": {"status": "covered", "clause": "第五条第一款", "note": "公关费属事故响应费用"},
            "F6": {"status": "covered", "clause": "第五条第一款", "note": "通知、建立新账号、信用监控"},
            "F7": {"status": "limited", "clause": "第五条第三款 额外费用",
                   "note": "以不超过可防范的营业损失为限"},
            "S1": {"status": "covered", "clause": "第五条第三款 营业收入损失"},
            "S2": {"status": "unmapped"},
            "S4": {"status": "unmapped"},
            "R1": {"status": "covered", "clause": "第三十七条第五款 赔偿金"},
            "R2": {"status": "covered", "clause": "第三十七条第六款 法律费用"},
        },
        "items": {
            "F1-10": {"status": "covered", "clause": "第五条第六款 网络欺诈损失 / 社会工程学损失",
                      "note": "承保受冒名转账指令直接导致的资金损失，本科目用于归集追回费用"},
            "F1-11": {"status": "unmapped"},
            "F2-11": {"status": "excluded", "clause": "第六条第二项 财产损害除外"},
            "F3-04": {"status": "unmapped"},
            "F3-05": {"status": "unmapped"},
            "F5-04": {"status": "unmapped"},
            "F5-05": {"status": "unmapped"},
            "F6-04": {"status": "limited", "clause": "第五条第一款",
                      "note": "条款列明「建立新账号」费用，换卡成本可类推但非明示"},
            "F8-01": {"status": "unmapped", "clause": "—",
                      "note": "本条款无声誉损害或品牌修复责任项"},
            "S1-02": {"status": "covered", "clause": "第五条第三款 从属营业收入损失 / 第三十七条第二十七款",
                      "note": "承保服务提供商系统中断导致的连带损失"},
            "S2-01": {"status": "excluded", "clause": "第六条第二项 / 第八项",
                      "note": "财产损害及正常磨损除外"},
            "S2-05": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "第五条第四款 勒索支付款项 / 第八条第五款",
                      "note": "条款明文承保勒索款项且不适用免赔额，但须事先取得保险人同意，"
                              "国内监管实践下赎金支付不具可赔性；本案按不可赔处理"},
            "R1-06": {"status": "excluded", "clause": "第六条第四项"},
            "R3-01": {"status": "unmapped"},
            "R3-02": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 10000000,
        "deductible": {"scope": "per_occurrence", "amount": 100000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "higher_of",
            "deductible": 100000,
            "max_indemnity_days": 270,
            "clause": "第八条第四款 免赔额与等待时间自留额取较高者；第三十七条第三十款 恢复期限不超过270天",
        },
        "sublimits": [
            {"id": "SL-IR", "name": "事故响应费用", "items": ["F1", "F4", "F5", "F6"],
             "limit": 2000000, "shares_aggregate": True, "clause": "第七条第二款"},
            {"id": "SL-DA", "name": "数字资产重置及硬件改善", "items": ["F2", "F3"],
             "limit": 2000000, "shares_aggregate": True, "clause": "第七条第三款"},
            {"id": "SL-BI", "name": "营业收入损失及从属营业", "items": ["S1", "F7"],
             "limit": 4000000, "shares_aggregate": True, "clause": "第七条第四款"},
            {"id": "SL-EXT", "name": "网络勒索", "items": ["S3"],
             "limit": 1000000, "shares_aggregate": True, "clause": "第七条第五款"},
            {"id": "SL-LIAB", "name": "第三方赔偿与抗辩", "items": ["R1", "R2"],
             "limit": 5000000, "shares_aggregate": True, "clause": "第七条"},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "第八条第四款是本工具 higher_of 口径的直接来源：营业收入损失的免赔额"
        "以「免赔额金额」与「等待时间自留额」两者较高者为准，二者不叠加。",
        "第八条第五款规定勒索支付款项不适用免赔额；但本工具按 nominal_only 处理赎金，"
        "该条在国内实践中无适用空间。",
    ],
}


# ==========================================================================
# 09 平安网络安全企业财产保险 B 款
# ==========================================================================
PINGAN = {
    "id": "pingan-cyber-b",
    "name": "平安网络安全企业财产保险（B款）",
    "insurer": "中国平安财产保险",
    "product_type": "第一方为主的财产型",
    "source_file": "09_平安网络安全企业财产保险B款_analysis.md",
    "summary": "国内第一方产品，十项列明责任；明确除外外包商责任与知识产权侵权；"
               "多项费用须事先书面同意，检测机构须为合同列明的第三方专业机构。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "conditional", "clause": "第六条 指定专业机构 / 第七条 检测费用",
                   "note": "须聘请保险合同列明的第三方专业机构，且在联络后24小时内通知保险人"},
            "F2": {"status": "covered", "clause": "第八条 数据恢复费用",
                   "note": "备份数据重新输入、原有程序重输、置换标准程序数据"},
            "F3": {"status": "limited", "clause": "第九条 网络安全防御费用",
                   "note": "限于事故发生后避免损失恶化的加固与漏洞修补，不含超出原状态的升级"},
            "F5": {"status": "conditional", "clause": "第十一条 媒体公关费用",
                   "note": "须经保险人事先书面同意"},
            "F6": {"status": "covered", "clause": "第十二条 通知费用"},
            "S1": {"status": "covered", "clause": "第五条 营业中断损失",
                   "note": "毛利润损失 + 必要且合理的维持费用"},
            "R2": {"status": "conditional", "clause": "第十条 法律费用 / 第十四条 调查费用",
                   "note": "须经保险人事先书面同意"},
        },
        "items": {
            "F1-06": {"status": "limited", "clause": "第十六条第六款 / 第十五条第十三款",
                      "note": "被保险人为查明外包商侧责任而支出的调查费属自身费用，"
                              "非「外包商自身的损失费用」，可主张计入；"
                              "但边界模糊，实务中易被援引第十六条第六款抗辩"},
            "F1-10": {"status": "unmapped"},
            "F1-11": {"status": "unmapped"},
            "F2-11": {"status": "unmapped"},
            "F3-01": {"status": "covered", "clause": "第九条 网络安全防御费用"},
            "F3-04": {"status": "unmapped"},
            "F3-05": {"status": "unmapped"},
            "F4-01": {"status": "limited", "clause": "第十条 法律费用",
                      "note": "条款限于仲裁或诉讼产生的费用，非诉法律服务未列明"},
            "F4-02": {"status": "unmapped"},
            "F5-04": {"status": "unmapped"},
            "F5-05": {"status": "unmapped"},
            "F6-03": {"status": "unmapped"},
            "F6-04": {"status": "unmapped"},
            "F6-05": {"status": "unmapped"},
            "F7-01": {"status": "limited", "clause": "第九条",
                      "note": "应急防护可归入防御费用，但DDoS缓解未明示"},
            "F7-03": {"status": "limited", "clause": "第五条 维持费用"},
            "F8-01": {"status": "unmapped", "clause": "—", "note": "本条款无品牌修复责任项"},
            "S1-02": {"status": "excluded", "clause": "第十五条第十三款 / 第十六条第六款",
                      "note": "第三方或云服务商中断导致的依赖性收入损失不予赔付"},
            "S2-01": {"status": "unmapped"},
            "S2-05": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "第十三条 网络勒索损失",
                      "note": "条款列明赎金、顾问费、奖励与谈判差旅费，"
                              "但赎金在国内监管实践下不具可赔性"},
            "S4-01": {"status": "limited", "clause": "第五条 维持费用",
                      "note": "内部人力成本仅在构成维持费用时认可，通常不含普通工资"},
            "S4-02": {"status": "limited", "clause": "第五条 维持费用"},
            "R1-01": {"status": "limited", "clause": "第四十二条 信息安全事件 / 第三十一条",
                      "note": "B款以第一方保障为主，第三者赔偿责任建议另投责任险；"
                              "条款仅在索赔材料条中提及第三者索赔"},
            "R1-02": {"status": "limited", "clause": "第二十九条",
                      "note": "未经保险人书面同意不得承认责任或达成和解"},
            "R3-01": {"status": "unmapped"},
            "R3-02": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 5000000,
        "deductible": {"scope": "per_occurrence", "amount": 50000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "waiting_only",
            "deductible": 0,
            "max_indemnity_days": 90,
            "clause": "第五条 / 第十八条 免赔期（等待期）后承担赔偿责任，赔偿期以合同列明为限",
        },
        "sublimits": [
            {"id": "SL-DET", "name": "检测与专业机构费用", "items": ["F1"],
             "limit": 300000, "shares_aggregate": True, "clause": "第六条 / 第七条 / 第十八条"},
            {"id": "SL-REC", "name": "数据恢复与安全防御费用", "items": ["F2", "F3", "F7"],
             "limit": 500000, "shares_aggregate": True, "clause": "第八条 / 第九条"},
            {"id": "SL-PR", "name": "媒体公关费用", "items": ["F5"],
             "limit": 200000, "shares_aggregate": True, "clause": "第十一条"},
            {"id": "SL-NOTIF", "name": "通知费用", "items": ["F6"],
             "limit": 200000, "shares_aggregate": True, "clause": "第十二条"},
            {"id": "SL-BI", "name": "营业中断损失", "items": ["S1", "S4"],
             "limit": 2000000, "shares_aggregate": True, "clause": "第五条 / 第十八条"},
            {"id": "SL-LEGAL", "name": "法律与调查费用", "items": ["F4", "R1", "R2"],
             "limit": 500000, "shares_aggregate": True, "clause": "第十条 / 第十四条"},
        ],
        "conditional_deductible": [
            {"id": "COND-UNAPPROVED-VENDOR", "flag": "unapproved_outsourcer",
             "type": "exclude_all", "value": 1.0,
             "desc": "IT外包商未被认可的操作失误（第十五条第十三款原因型除外）"},
        ],
    },
    "settlement_notes": [
        "**认可外包商是本保单的悬崖式条件**：第十五条第十三款除外的是"
        "「IT外包商**未被认可**的操作失误」，而条款术语库中的「外包商数据责任」"
        "适用于「被保险人雇员或**认可外包商**疏忽失误导致数据被窃或泄露」。"
        "即：同一场外包商误操作事故，外包商是否在保单中被列为认可，"
        "决定整场事故赔还是不赔——这是原因型除外，一旦成立，"
        "所有损失科目一并落空，不是某几项不赔。"
        "国内企业更换运维供应商时极少书面通知保险人，该条构成高发的程序性陷阱。"
        "案例中可用 policy_flags.unapproved_outsourcer 触发该情形。",
        "**框架结构性提示**：本工具的承保映射层按「损失类型」组织，"
        "而第十五条第十三款是按「事故原因」除外的。原因型除外无法用逐项开关表达，"
        "须整案触发。这是 69 科目框架的一个已知边界，"
        "案例中涉及原因型除外时必须显式说明。",
        "条款同时约定了「免赔额（率/期）」，但未明示营业中断是否在等待期之外"
        "再适用一次免赔额。本配置按 waiting_only 处理（仅等待期自留），"
        "属保守解释；实务核赔中此点应在保单明细表中写清，否则易生争议。",
        "第二十九条要求危险程度显著增加（如未通过投保时申报的等级保护或等级降级）"
        "应及时书面通知，否则保险人不承担赔偿责任——属可能整单拒赔的前置条件，"
        "不在本结算层建模，须在案例的程序性合规检查中单独核对。",
    ],
}


# ==========================================================================
# 13 珠峰财产网络安全检测与修复费用保险
# ==========================================================================
ZHUFENG = {
    "id": "zhufeng-detect-repair",
    "name": "珠峰财产网络安全检测与修复费用保险",
    "insurer": "珠峰财产保险",
    "product_type": "纯费用重置型（单一责任）",
    "source_file": "13_珠峰财产网络安全检测与修复费用保险_analysis.md",
    "summary": "只承保一件事：聘请保险人指定的网络安全服务机构，把境内网站服务器恢复到"
               "正常访问状态所支出的检测与维修费用。数据恢复、营业中断、第三方责任、"
               "系统升级、非指定机构修复费全部明确除外。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {},
        "items": {
            "F1-01": {"status": "conditional", "clause": "第三条 / 第五条第七款",
                      "note": "必须聘请保险人指定的网络安全服务机构，"
                              "自行修复或聘请非指定第三方的费用一律不赔"},
            "F1-02": {"status": "limited", "clause": "第三条 / 第二十一条",
                      "note": "条款用语为「检测」，须由指定机构出具书面原因与修复说明；"
                              "独立取证调查是否属检测范畴存在解释空间"},
            "F2-01": {"status": "conditional", "clause": "第三条",
                      "note": "以恢复到「正常访问状态」为限，超出部分不赔"},
            "F2-02": {"status": "conditional", "clause": "第三条"},
            "F2-03": {"status": "excluded", "clause": "第五条第三款",
                      "note": "被保险人为恢复电子数据而发生的费用明确除外"},
            "F2-04": {"status": "excluded", "clause": "第五条第三款"},
            "F2-08": {"status": "limited", "clause": "第三条", "note": "以恢复正常访问为限"},
            "F2-09": {"status": "conditional", "clause": "第三条"},
            "F3-01": {"status": "limited", "clause": "第三条 / 第四条第五款",
                      "note": "修复费本身可赔，但操作系统或软件自有及未及时升级导致的"
                              "缺陷或漏洞属除外原因，须先过因果关系这一关"},
            "F3-02": {"status": "excluded", "clause": "第五条第六款",
                      "note": "为升级网络安全系统支出的额外费用明确除外"},
            "S1-01": {"status": "excluded", "clause": "第五条第四款 营业中断损失除外"},
            "S1-02": {"status": "excluded", "clause": "第五条第四款"},
            "S1-03": {"status": "excluded", "clause": "第五条第四款"},
            "S2-01": {"status": "excluded", "clause": "第五条第二款 硬件损坏及衍生损失除外"},
            "S3-01": {"status": "unmapped", "clause": "—", "note": "本条款完全无网络勒索责任项"},
            "R1-01": {"status": "excluded", "clause": "第五条第五款 第三方信息泄露赔偿责任除外"},
            "R1-02": {"status": "excluded", "clause": "第五条第五款"},
        },
    },
    "settlement": {
        "aggregate_limit": 500000,
        "deductible": {"scope": "per_occurrence", "amount": 10000},
        "bi": {"items": ["S1-01", "S1-02", "S1-03"],
               "deductible_mode": "waiting_only", "deductible": 0,
               "clause": "本条款无营业中断责任，无免赔期与赔偿期间概念"},
        "sublimits": [
            {"id": "SL-REPAIR", "name": "检测与修复费用", "items": ["F1", "F2", "F3"],
             "limit": 500000, "shares_aggregate": True,
             "clause": "第七条 累计赔偿限额及各事故类别分项限额"},
        ],
        "conditional_deductible": [
            {"id": "COND-NONDESIGNATED", "flag": "non_designated_vendor",
             "type": "exclude_all", "value": 1.0,
             "desc": "未聘请保险人指定的网络安全服务机构（第五条第七款）"},
        ],
    },
    "settlement_notes": [
        "本产品是检验损失分类框架边界的极端样本：69 个标准科目中只有个位数落在"
        "承保范围内，赔付率天然极低。用它做案例的价值不在赔得多，"
        "而在于直观呈现「买了网络安全保险」与「买到了保障」之间的差距。",
        "第七条把限额按事故类别（有害程序事件 / 网络攻击事件 / 信息破坏事件）"
        "分设，本配置未按事故类别拆分限额；若案例需要区分事故类别，"
        "应在 sublimits 中按类别再拆一层。",
    ],
}


# ==========================================================================
# 14 中远海运网络安全应急响应服务保险
# ==========================================================================
COSCO = {
    "id": "cosco-emergency-service",
    "name": "中远海运网络安全应急响应服务保险",
    "insurer": "中远海运财产保险自保",
    "product_type": "服务给付型 + 有限费用赔付型",
    "source_file": "14_中远海运网络安全应急响应服务保险_analysis.md",
    "summary": "结构特殊：第七条的安全服务在总服务限额内以「服务」形式给付而非现金报销，"
               "第八条的赎金、公关、法律费用才走传统限额减免赔的现金赔付。"
               "第四条设有条件免赔额——安全检测发现隐患未整改导致事故的，免赔额额外增加10%。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {},
        "items": {
            "F1-01": {"status": "covered", "clause": "第七条 应急响应服务",
                      "note": "以服务包形式给付，须立即通知指定专业服务机构并在24小时内通知保险人"},
            "F1-02": {"status": "limited", "clause": "第七条",
                      "note": "应急响应服务内含初步排查，独立取证鉴定未单列"},
            "F2-01": {"status": "covered", "clause": "第七条 主机及系统数据库加固服务"},
            "F2-02": {"status": "covered", "clause": "第七条"},
            "F2-03": {"status": "covered", "clause": "第七条 数据恢复服务"},
            "F2-04": {"status": "limited", "clause": "第七条"},
            "F3-01": {"status": "covered", "clause": "第七条 代码安全加固服务"},
            "F3-02": {"status": "limited", "clause": "第七条 / 第十条第十二款",
                      "note": "加固服务承保，但任何超过事故发生前状态的升级、"
                              "重新设计或重新配置费用明确除外"},
            "F3-03": {"status": "covered", "clause": "第四条 安全检测服务",
                      "note": "含不同频次的安全监测与漏洞扫描，属事前防范服务"},
            "F5-01": {"status": "conditional", "clause": "第八条第二款 / 第二十四条",
                      "note": "方案与费用须向保险人无保留披露，保险人有权审核合理性"},
            "F5-02": {"status": "limited", "clause": "第八条第二款"},
            "F7-01": {"status": "covered", "clause": "第七条 DDOS应急防护服务"},
            "R2-01": {"status": "conditional", "clause": "第八条第三款",
                      "note": "须事先经保险人书面同意"},
            "R2-02": {"status": "limited", "clause": "第八条第三款"},
            "S1-01": {"status": "unmapped", "clause": "—",
                      "note": "术语库明确本条款无营业中断相关约定"},
            "S1-02": {"status": "unmapped"},
            "S1-03": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "第八条第一款 / 第二十三条 / 第二十六条",
                      "note": "条款明文承保赎金，且索赔材料清单里直接列了「勒索金支付记录」，"
                              "同时要求必须立即向公安部门报案并取得报案回执——"
                              "报案回执与赎金支付在国内是互斥的，条款自身即构成实践闭环障碍"},
            "R1-01": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 3000000,
        "deductible": {"scope": "per_occurrence", "amount": 100000},
        "bi": {"items": ["S1-01", "S1-02", "S1-03"],
               "deductible_mode": "waiting_only", "deductible": 0,
               "clause": "本条款无免赔期与赔偿期间约定"},
        "sublimits": [
            {"id": "SL-SVC", "name": "安全服务赔付（服务包）", "items": ["F1", "F2", "F3", "F7"],
             "limit": 1000000, "shares_aggregate": False,
             "clause": "第七条 总服务限额内按约定方案扣减使用，独立于现金赔付限额"},
            {"id": "SL-RANSOM", "name": "网络勒索赎金", "items": ["S3"],
             "limit": 500000, "shares_aggregate": True, "clause": "第八条第一款 / 第十二条"},
            {"id": "SL-PR", "name": "危机公关费用", "items": ["F5"],
             "limit": 300000, "shares_aggregate": True, "clause": "第八条第二款"},
            {"id": "SL-LEGAL", "name": "法律费用", "items": ["F4", "R1", "R2"],
             "limit": 300000, "shares_aggregate": True, "clause": "第八条第三款"},
        ],
        "conditional_deductible": [
            {"id": "COND-UNREMEDIATED", "flag": "unremediated_finding",
             "type": "pct_uplift", "value": 0.10,
             "desc": "安全检测已发现隐患但未整改，导致相关网络安全事故发生（第四条）"},
        ],
    },
    "settlement_notes": [
        "第七条的安全服务赔付是「服务给付」而非现金报销：保险人直接派服务，"
        "在总服务限额内扣减使用。本配置把该组的 shares_aggregate 设为 false，"
        "使其不占用现金赔付的累计限额——这与其他保单的结构不同，案例中值得单独说明。",
        "第四条的条件免赔额通过 flags.unremediated_finding 触发。"
        "案例中若事故与已发现未整改的隐患有因果关系，务必打开该标记。",
    ],
}




# ==========================================================================
# 国寿财 网络安全保险条款 B（纯第一方）
# ==========================================================================
# 口径换算约定（重要，不改代码的前提下如何表达本条款的营业中断口径）
# ---------------------------------------------------------------------
# 本条款的营业中断口径与本工具 S1-01 的公式外推法有三处不一致：
#   条款：赔偿期间(小时) × (日均净利润 ÷ 24) − 实际净利润 + 维持费用
#   工具：日均收入 × MAX(中断天数 − 等待期, 0) × 毛利率 × 影响比例
# 经确认不修改 formulas.py，改以填参约定表达，映射规则固定如下：
#   p1 日均收入   ← 填「日均净利润额」（口径已在此体现）
#   p2 中断天数   ← 中断小时数 ÷ 24
#   p3 等待期     ← 免赔期间小时数 ÷ 24
#   p4 毛利率     ← 固定填 1.0（因 p1 已是净利润，不再乘毛利率）
#   p5 影响比例   ← 1 − (赔偿期间实际净利润 ÷ 应得净利润)
#   维持费用      ← 计入 S4-01/S4-02，并在结算层归入营业中断分项组
# 该约定必须在每个引用本保单的案例中显式声明，否则参数含义会被误读。
GUOSHOU_B = {
    "id": "guoshou-cyber-b",
    "name": "中国人寿财产保险 网络安全保险条款 B",
    "insurer": "中国人寿财产保险股份有限公司",
    "product_type": "纯第一方网络安全损失保险",
    "source_file": "国寿_网络安全保险条款B_AI结构化摘要.md",
    "registration_no": "C00010830612020012322442",
    "summary": "第一方四大模块：营业中断、网络勒索、数据修复、应急响应（含声誉危机）。"
               "完全不设第三者责任。条款第十五节把赔偿计算顺序写成显式步骤，"
               "第十四节采用「每次事故免赔额与免赔期间取高者」。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "conditional", "clause": "责任模块D 12.2 外部网络安全团队费用",
                   "note": "外聘第三方安全团队处置，原则上需保险人书面同意"},
            "F2": {"status": "covered", "clause": "责任模块C 数据修复费用",
                   "note": "恢复系统、移除恶意软件、重建数据的必要合理成本；"
                           "允许包含向外部服务供应商分包的合理成本"},
            "F3": {"status": "limited", "clause": "责任模块D 12.2 / 第16.3节",
                   "note": "漏洞修复属应急响应费用，但性能提升部分明确除外"},
            "F4": {"status": "covered", "clause": "责任模块D 12.1 合规与咨询服务费用",
                   "note": "与政府部门沟通、网安法与个保法适用性判断、合规顾问咨询"},
            "F5": {"status": "conditional", "clause": "责任模块D 12.3 声誉危机处理费用",
                   "note": "**费用必须发生在保险事故发生后30日内**，超期原则上不属该项责任"},
            "S1": {"status": "covered", "clause": "责任模块A 营业中断损失"},
            "S4": {"status": "covered", "clause": "第6.4节 维持费用",
                   "note": "房租、员工工资、固定资产折旧等不随经营减少而减少的成本，"
                           "属营业中断损失组成部分，金额由双方约定并载明"},
        },
        "items": {
            "F1-10": {"status": "excluded", "clause": "第18.7节 金融机构账户资金或资产损失"},
            "F2-11": {"status": "excluded", "clause": "第17.6节 有形设备自身损失或机械故障"},
            "F2-05": {"status": "excluded", "clause": "第11.4节 研发数据"},
            "F2-06": {"status": "excluded", "clause": "第11.5节 数据经济价值"},
            "F3-02": {"status": "excluded", "clause": "第11.1节 Betterment / 超额改进 / 第16.3节",
                      "note": "超过事故前状态的改进与性能提升明确除外"},
            "F3-03": {"status": "limited", "clause": "责任模块D 12.2 风险评估"},
            "F6": {"status": "unmapped", "clause": "—",
                   "note": "本条款未设独立的数据泄露通知费用责任"},
            "F8-01": {"status": "unmapped", "clause": "—",
                      "note": "声誉相关仅有应急响应项下的危机处理费用，无品牌价值修复责任"},
            "S1-02": {"status": "limited", "clause": "第3.2节 计算机系统范围 / 第19.1节",
                      "note": "书面委托的第三方代管系统可纳入保障；"
                              "但外部服务商的欺诈、违法、故意、重大过失导致的损失除外"},
            "S2-01": {"status": "excluded", "clause": "第17.6节 / 第18.8节"},
            "S2-05": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "责任模块B 8.2 网络勒索赎金",
                      "note": "条款承保赎金，但同时要求「按照中国法律规定」且「经保险人书面同意」；"
                              "模块B另要求及时通知公安机关。「按照中国法律规定」这一限定语"
                              "在国内监管实践下使赎金实际不可赔"},
            "S3-02": {"status": "conditional", "clause": "责任模块B 8.3 网络勒索处理费用",
                      "note": "赎金不可赔不等于处理费用不可赔，二者须分列"},
            "R1": {"status": "unmapped", "clause": "第1.2节",
                   "note": "本条款明确未设置第三者数据泄露、隐私侵权、网络安全、媒体责任"},
            "R2": {"status": "unmapped", "clause": "第1.2节",
                   "note": "未设第三者诉讼法律辩护费用；与国寿财「网络安全责任保险」互补"},
            "R3": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 8000000,
        "deductible": {"scope": "per_occurrence", "amount": 150000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "higher_of",
            "deductible": 150000,
            "max_indemnity_days": 120,
            "clause": "第14.1节 每次事故免赔额与免赔期间同时存在时取较高者；"
                      "第7节 赔偿期间自事故发生至网络及主要系统功能恢复正常，每日按24小时计",
        },
        "sublimits": [
            {"id": "SL-BI", "name": "营业中断损失（含维持费用）", "items": ["S1", "S4"],
             "limit": 4000000, "shares_aggregate": True,
             "clause": "第13.1节 分项限额包含于累计限额内，非额外增加"},
            {"id": "SL-EXT", "name": "网络勒索事故", "items": ["S3"],
             "limit": 1000000, "shares_aggregate": True, "clause": "第13节"},
            {"id": "SL-DATA", "name": "数据修复费用", "items": ["F2"],
             "limit": 2000000, "shares_aggregate": True, "clause": "第13节"},
            {"id": "SL-IR", "name": "网络应急响应费用", "items": ["F1", "F3", "F4", "F5", "F7"],
             "limit": 1500000, "shares_aggregate": True, "clause": "第13节"},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "**营业中断口径换算约定**：本条款按小时计量、以净利润为基础，"
        "与本工具 S1-01 的公式外推法（按天、毛利率）不一致。经权衡决定不修改计算核心，"
        "改以填参约定表达：p1 填日均净利润额、p2 填中断小时数÷24、p3 填免赔期间小时数÷24、"
        "p4 固定填 1.0、p5 填 1−(实际净利润÷应得净利润)，维持费用记入 S4 并归入营业中断分项组。"
        "引用本保单的案例必须显式声明该约定，否则参数含义会被误读。",
        "第15节把赔偿计算顺序写成了显式步骤：确定实际损失 → 扣分项免赔额 → 受分项限额限制 "
        "→ 扣每次事故免赔额或免赔期间金额 → 受累计限额限制。"
        "这与本工具结算层的六步顺序一致，是该顺序的条款级印证。",
        "第14.1节的「取高者」是本项目 higher_of 口径的第三个来源"
        "（另两个为苏黎世6.3、泰康第八条第四款），说明该机制是行业惯例而非个别设计。",
        "声誉危机处理费用有30日时限（12.3节），是本保单库中唯一的费用发生期限制，"
        "案例中若公关费跨越30日须拆分。",
    ],
}


# ==========================================================================
# 国寿财 网络安全责任保险（纯第三方，与 B 款互补）
# ==========================================================================
GUOSHOU_LIABILITY = {
    "id": "guoshou-liability",
    "name": "中国人寿财产保险 网络安全责任保险",
    "insurer": "中国人寿财产保险股份有限公司",
    "product_type": "纯第三者责任保险（索赔提出制）",
    "source_file": "中国人寿财产保险网络安全责任保险_AI结构化摘要.md",
    "registration_no": "C00010830912020061800432",
    "summary": "只承保第三者责任与法律费用。数据恢复、系统修复、应急响应、赎金、"
               "营业中断、名誉恢复全部不属本产品保障范围。与同公司的"
               "《网络安全保险条款B》构成互补的一对：一个只赔别人的损失，一个只赔自己的。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "R1": {"status": "covered", "clause": "网络安全事故第三者责任 / 数字媒体责任",
                   "note": "因恶意软件、黑客入侵、拒绝服务攻击、非法使用或访问"
                           "导致第三者经济损失；含数字媒体内容疏忽或一般过失"},
            "R2": {"status": "conditional", "clause": "法律费用",
                   "note": "仲裁、诉讼及经保险人书面同意的必要合理费用"},
        },
        "items": {
            "F1-01": {"status": "excluded", "clause": "责任总览：应急响应费用 明确除外"},
            "F2-01": {"status": "excluded", "clause": "责任总览：系统恢复/IT修复费用 明确除外",
                      "note": "条款明确将信息技术服务费用列为除外"},
            "F2-03": {"status": "excluded", "clause": "责任总览：数据恢复费用 未作为保险责任承保"},
            "F5-01": {"status": "unmapped", "clause": "责任总览：名誉恢复费用 未设置独立责任"},
            "S1-01": {"status": "excluded", "clause": "责任总览：交易及交易中断类损失明确除外",
                      "note": "未设置独立利润损失责任"},
            "S3-01": {"status": "unmapped", "clause": "责任总览：网络敲诈赎金 未列入保险责任",
                      "note": "本产品连名义承保都没有，与多数国内产品不同"},
            "R3-01": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 10000000,
        "deductible": {"scope": "per_occurrence", "amount": 100000},
        "bi": {"items": ["S1-01", "S1-02", "S1-03"],
               "deductible_mode": "waiting_only", "deductible": 0,
               "clause": "本产品无营业中断责任，无免赔期与赔偿期间概念"},
        "sublimits": [
            {"id": "SL-LIAB", "name": "第三者赔偿责任", "items": ["R1"],
             "limit": 8000000, "shares_aggregate": True},
            {"id": "SL-LEGAL", "name": "法律费用", "items": ["R2", "F4"],
             "limit": 2000000, "shares_aggregate": True},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "本产品为索赔提出制（claims-made）并设追溯期，与保单库中多数事故发生制产品不同。"
        "案例中须同时核对「事故发生在追溯期后」与「索赔在保险期间内提出」两个时点，"
        "本结算层不对时效建模，须在程序性合规检查中单独核对。",
        "与 guoshou-cyber-b 是同一保险人的互补产品。企业若只买其一，"
        "出险后缺口位置完全不同——这是本保单库中最有教学价值的一组对照。",
    ],
}


# ==========================================================================
# 阳光 网络安全综合保险（2016版，模块化）
# ==========================================================================
SUNSHINE = {
    "id": "sunshine-2016",
    "name": "阳光财产保险 网络安全综合保险（2016版）",
    "insurer": "阳光财产保险股份有限公司",
    "product_type": "模块化综合险（六模块可选投）",
    "source_file": "阳光网络安全综合保险条款2016_AI结构化摘要.md",
    "summary": "六个模块可单选：1.1 数据恢复及其他费用、1.2 网络敲诈、1.3 名誉损失、"
               "1.4 利润损失、2.1 数据保密责任、法律费用。"
               "承保结果高度依赖保单实际勾选了哪些模块——这是本保单库中唯一"
               "「买什么才保什么」的产品，缺口可能来自销售环节而非条款设计。",
    "parameters_are_assumed": True,
    "modular": True,
    "modules": {
        "1.1": {"name": "数据恢复及其他费用损失保险", "items": ["F1", "F2", "F3", "F6", "F7"]},
        "1.2": {"name": "网络敲诈损失保险", "items": ["S3"]},
        "1.3": {"name": "名誉损失补偿保险", "items": ["F5", "F8"]},
        "1.4": {"name": "利润损失保险", "items": ["S1", "S4"]},
        "2.1": {"name": "数据保密责任保险", "items": ["R1"]},
        "legal": {"name": "法律费用", "items": ["R2", "F4"]},
    },
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "covered", "clause": "模块1.1 第4.5节 调查费用"},
            "F2": {"status": "covered", "clause": "模块1.1 第4.2/4.3节 数据恢复及重置、系统恢复费用"},
            "F3": {"status": "limited", "clause": "模块1.1 第4.4节 / 第14.6节",
                   "note": "其他IT相关费用可涵盖修复，但超标准升级明确除外"},
            "F4": {"status": "conditional", "clause": "模块2.1 第8.4节 法律费用"},
            "F5": {"status": "covered", "clause": "模块1.3 第6.3节 媒体危机管理及广告宣传费用"},
            "F6": {"status": "covered", "clause": "模块1.1 第4.6节 通知费用"},
            "F7": {"status": "covered", "clause": "模块1.1 第4.4节 其他IT相关费用"},
            "S1": {"status": "covered", "clause": "模块1.4 第7.2/7.3节 净利润损失及固定费用"},
            "S4": {"status": "covered", "clause": "模块1.4 第7.4/7.5节 固定费用、额外费用"},
            "R1": {"status": "covered", "clause": "模块2.1 数据保密责任",
                   "note": "第三者机密信息损坏、丢失、盗窃、泄露责任"},
            "R2": {"status": "conditional", "clause": "第8.4节 法律辩护费用"},
        },
        "items": {
            "F1-06": {"status": "excluded", "clause": "第12.1/12.2节 外包商自身损失、外包商转包"},
            "F1-10": {"status": "excluded", "clause": "第14.1节 金融交易和贸易损失"},
            "F2-11": {"status": "excluded", "clause": "第13.4/13.5节 硬件本身丢失盗抢、正常磨损"},
            "F3-02": {"status": "excluded", "clause": "第14.6节 超标准升级"},
            "F8-01": {"status": "limited", "clause": "模块1.3 第6.3节",
                      "note": "条款口径为媒体危机管理与广告宣传费用，"
                              "与本模型的品牌价值降幅法不一致，须按费用实报口径重算"},
            "S1-02": {"status": "excluded", "clause": "第13.2节 第三方基础设施/服务故障除外"},
            "S1-03": {"status": "limited", "clause": "第7.9节 审计费用 / 第7.7节 不足额保险比例赔偿",
                      "note": "条款设有比例赔偿机制，不足额投保时按比例赔付，"
                              "本结算层未建模该机制，案例中须单独说明"},
            "S2-01": {"status": "excluded", "clause": "第13.4节"},
            "S2-05": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "模块1.2 第5.2节 / 第14.4节",
                      "note": "第14.4节原则上赎金不赔，仅在投保模块1.2时例外承保；"
                              "且须事先经保险人书面同意、并及时通知公安机关。"
                              "通知公安与支付赎金在国内实践中互斥，实际不可赔。"
                              "另需注意：未投保模块1.2 时连名义承保都不存在"},
            "R1-06": {"status": "excluded", "clause": "第10.13节 商业合同暂停/取消/失效"},
            "R3-01": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 6000000,
        "deductible": {"scope": "per_occurrence", "amount": 80000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "higher_of",
            "deductible": 80000,
            "max_indemnity_days": 180,
            "clause": "第16.3节 免赔额与按免赔率计算金额取高者；第7.6节 赔偿期间",
        },
        "sublimits": [
            {"id": "SL-M11", "name": "模块1.1 数据恢复及其他费用", "items": ["F1", "F2", "F3", "F6", "F7"],
             "limit": 2000000, "shares_aggregate": True, "clause": "第16.2节"},
            {"id": "SL-M12", "name": "模块1.2 网络敲诈", "items": ["S3"],
             "limit": 800000, "shares_aggregate": True, "clause": "第16.2节"},
            {"id": "SL-M13", "name": "模块1.3 名誉损失", "items": ["F5", "F8"],
             "limit": 800000, "shares_aggregate": True, "clause": "第16.2节"},
            {"id": "SL-M14", "name": "模块1.4 利润损失", "items": ["S1", "S4"],
             "limit": 3000000, "shares_aggregate": True, "clause": "第16.1节"},
            {"id": "SL-M21", "name": "模块2.1 数据保密责任及法律费用", "items": ["R1", "R2", "F4"],
             "limit": 3000000, "shares_aggregate": True, "clause": "第16.2节"},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "**模块化是本产品的核心特征**：投保人可只选部分模块，未投保模块的损失完全不赔。"
        "本配置默认全部模块均已投保；若案例要演示「只买了部分模块」的缺口，"
        "应在案例中用 include_override 关闭对应科目，并在案情中说明未投保哪些模块。"
        "这类缺口来自销售环节而非条款设计，是国内市场特有的问题。",
        "第7.7节设有不足额保险的比例赔偿机制（利润损失保险金额低于应保金额时按比例赔付），"
        "本结算层未建模，案例中若涉及须单独说明。",
        "第15节的事故聚合规则（模块1.1与1.2合并计为一次事故）本结算层未建模，"
        "多起关联事故的案例须人工判断是否合并。",
    ],
}




# ==========================================================================
# 05 安联财产保险 电子商务和信息安全保障责任保险
# ==========================================================================
ALLIANZ = {
    "id": "allianz-ecommerce",
    "name": "安联财产保险 电子商务和信息安全保障责任保险",
    "insurer": "安联财产保险（中国）",
    "product_type": "综合型（第三方责任 + 营业中断 + 危机管理 + 第一方损失）",
    "source_file": "05_安联财产保险电子商务和信息安全保障责任保险_analysis.md",
    "summary": "承保面最宽的一款。关键差异点：明确承保**外包服务提供商**造成的泄密"
               "（与平安B款、阳光的除外形成正面对照）；承保工业控制系统扩展、"
               "人为错误与技术故障引发的营业中断、以及为遵守监管命令主动关停造成的中断。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "covered", "clause": "第二部分C项第一款 应急危机调查费用",
                   "note": "IT专家分析查明是否发生、起因、程度及如何减轻损失"},
            "F2": {"status": "covered", "clause": "第三部分第五项 修复费用",
                   "note": "将系统恢复至事故前功能水平、恢复读取重装数据或软件"},
            "F3": {"status": "limited", "clause": "第三部分第六项 改进费用",
                   "note": "纠正根本起因的升级改进费用，适用分项限额，须事先书面同意"},
            "F4": {"status": "conditional", "clause": "第二部分C项第二款",
                   "note": "泄露应对费用含法律监管建议，须事先书面同意"},
            "F5": {"status": "conditional", "clause": "第二部分C项第四款 名誉保护费用",
                   "note": "适用分项限额，须事先同意"},
            "F6": {"status": "covered", "clause": "第二部分C项第二款",
                   "note": "含消费者通知、呼叫中心、账户与信用监测（最长十二个月）"},
            "F7": {"status": "covered", "clause": "第三部分第三、四项 减轻损失费用"},
            "S1": {"status": "covered", "clause": "第二部分B项 营业中断损失",
                   "note": "税前净经营利润减少及持续消耗的固定成本"},
            "S4": {"status": "covered", "clause": "第二部分B项 / 第三部分第三、四项"},
            "R1": {"status": "covered", "clause": "第二部分A项 侵犯隐私、机密泄露、网络安全索赔"},
            "R2": {"status": "conditional", "clause": "第二部分A项 抗辩费用",
                   "note": "须经事先书面同意"},
        },
        "items": {
            # —— 外包商责任：本保单的标志性差异 ——
            "F1-06": {"status": "covered", "clause": "第二部分A项 及 第四部分定义",
                      "note": "**承保对外包服务提供商提出的侵犯隐私与机密泄露索赔**，"
                              "与平安B款第十六条第六款、阳光第12节的除外形成正面对照"},
            "S1-02": {"status": "covered", "clause": "第三部分第九、十项",
                      "note": "承保人为错误或技术故障引发的营业中断，"
                              "以及为遵守监管命令主动关停系统造成的中断"},
            "F1-10": {"status": "covered", "clause": "第二部分D项第一款 黑客盗窃资金损失",
                      "note": "承保第三方网络攻击导致被保险人支付本不应支付的资金，适用分项限额"},
            "F1-11": {"status": "limited", "clause": "第三部分第二项 紧急费用",
                      "note": "允许事后批准追认的应急支出，适用分项限额"},
            "F2-11": {"status": "excluded", "clause": "通用除外：人身伤害和财产损失",
                      "note": "数据和软件不属于有形财产，但有形财产损失除外"},
            "F3-05": {"status": "excluded", "clause": "通用除外：商业秘密及知识产权"},
            "F8-01": {"status": "limited", "clause": "第二部分C项第四款",
                      "note": "条款口径为名誉保护的公关顾问费用，"
                              "与本模型的品牌价值降幅法不一致，须按费用实报口径重算"},
            "S2-01": {"status": "excluded", "clause": "通用除外：人身伤害和财产损失"},
            "S2-05": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "第二部分D项第二款 网络敲诈损失",
                      "note": "条款承保为解除威胁实际支付的钱款与数字货币，"
                              "但须经保险人事先书面同意；国内监管实践下赎金不可赔"},
            "S3-02": {"status": "conditional", "clause": "第二部分D项第二款",
                      "note": "聘请安全专家协助的技术费与赎金须分列"},
            "R1-06": {"status": "excluded", "clause": "通用除外：合同责任",
                      "note": "但PCI与保密协议项下的责任不适用该除外"},
            "R3-01": {"status": "covered", "clause": "第二部分A项 PCI-DSS 责任",
                      "note": "承保卡组织罚金、抗辩费用及合同约定罚金，适用分项限额"},
            "R3-02": {"status": "limited", "clause": "第二部分A项"},
        },
    },
    "settlement": {
        "aggregate_limit": 15000000,
        "deductible": {"scope": "per_occurrence", "amount": 150000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "waiting_only",
            "deductible": 0,
            "max_indemnity_days": 180,
            "clause": "第二部分B项 等待期以小时计，营业中断损失含等待期内损失；"
                      "第四部分定义 赔偿期间自首次发生起最长180天",
        },
        "sublimits": [
            {"id": "SL-CRISIS", "name": "危机管理费用", "items": ["F1", "F5", "F6", "F7"],
             "limit": 4000000, "shares_aggregate": True, "clause": "明细表第六项"},
            {"id": "SL-REPAIR", "name": "修复与改进费用", "items": ["F2", "F3"],
             "limit": 3000000, "shares_aggregate": True, "clause": "第三部分第五、六项"},
            {"id": "SL-BI", "name": "营业中断损失", "items": ["S1", "S4"],
             "limit": 6000000, "shares_aggregate": True, "clause": "第二部分B项"},
            {"id": "SL-EXT", "name": "网络敲诈与黑客盗窃", "items": ["S3"],
             "limit": 1500000, "shares_aggregate": True, "clause": "第二部分D项"},
            {"id": "SL-LIAB", "name": "第三方责任与抗辩", "items": ["R1", "R2", "F4"],
             "limit": 10000000, "shares_aggregate": True, "clause": "明细表第六项"},
            {"id": "SL-PCI", "name": "PCI-DSS 责任", "items": ["R3"],
             "limit": 2000000, "shares_aggregate": True, "clause": "第二部分A项"},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "**外包商责任是本保单的标志性差异**：第二部分A项明确承保「对被保险人"
        "**或外包服务提供商**提出的侵犯隐私行为和机密泄露行为的索赔」。"
        "平安B款第十六条第六款、阳光第12节均将外包商相关损失除外。"
        "同一场外包商泄密事故，在这三款保单下的结果截然不同——建议做成对照案。",
        "明细表第六项载明各项分项限额「构成累计责任限额一部分」，"
        "故全部分项组 shares_aggregate 均为 true，与苏黎世 5.3 结构相同。",
        "营业中断的等待期以小时计，且条款明确「包含等待期内损失」——"
        "这与多数保单「扣除等待期」的做法相反，是罕见的宽口径设计。"
        "本配置按 waiting_only 处理，案例中 S1-01 的 p3 等待期应填 0 以体现该特点。",
        "第三部分第十项承保「为遵守监管命令或数据保护法强制规定而主动关停系统」"
        "造成的营业中断——国内监管要求企业配合调查时暂停服务的情形可直接适用，"
        "是本保单库中少见的、与国内监管实践直接契合的条款设计。",
    ],
}


# ==========================================================================
# 02 安达 企业网络风险管理保险
# ==========================================================================
CHUBB = {
    "id": "chubb-cyber-erm",
    "name": "安达 企业网络风险管理保险",
    "insurer": "安达保险（中国）",
    "product_type": "综合型（三大责任 + 第一方损失 + 扩展责任）",
    "source_file": "02_安达企业网络风险管理保险_analysis.md",
    "summary": "外资在华综合型产品。核心观察点是「监管程序罚金」：条款把行政罚款"
               "写入损害赔偿范围，但加了「在法律和赔偿支付地允许承保的前提下」这一限定语——"
               "与赎金条款的「在中国法律允许范围内」是同构句式。"
               "国内行政罚款依法不可保，故该项判定为名义承保、实际不可赔。",
    "parameters_are_assumed": True,
    "coverage": {
        "default": "unmapped",
        "categories": {
            "F1": {"status": "covered", "clause": "第一条第一、二、三款及第三条第十七款 应急响应费用",
                   "note": "第三方计算机取证公司确定网络安全失效原因和范围"},
            "F2": {"status": "covered", "clause": "第一条第五款 数据损失修复费用",
                   "note": "移除恶意软件、事故后重建数据"},
            "F3": {"status": "limited", "clause": "第二条第六款 改进费用",
                   "note": "纠正根本起因的升级改进，属事件后紧急漏洞修补与加固"},
            "F4": {"status": "conditional", "clause": "第三条第十七款",
                   "note": "应急响应费用含法律与合规顾问，须事先书面同意"},
            "F5": {"status": "conditional", "clause": "第三条第十七款 危机公关"},
            "F6": {"status": "covered", "clause": "第三条第十七款 / 第二条第七款",
                   "note": "遵守个人信息保护法规通知消费者、信用监测；另有自愿通知费用扩展"},
            "F7": {"status": "covered", "clause": "第二条第三、四款 减轻损失费用"},
            "S1": {"status": "covered", "clause": "第一条第六款 营业中断损失",
                   "note": "赔偿期内直接导致的税前净利润减少"},
            "S4": {"status": "covered", "clause": "第一条第六款 营业中断修复费用",
                   "note": "含借用外部设备、持续经营替代方案、劳动力成本增加"},
            "R1": {"status": "covered", "clause": "第一条第一、二、三款 保密/网络安全/媒体责任"},
            "R2": {"status": "conditional", "clause": "第三条第十四款 赔偿请求费用",
                   "note": "律师费、专家证人费；须经保险人事先书面同意"},
        },
        "items": {
            "F1-06": {"status": "covered", "clause": "第一条第一款 / 第三条第四十二款",
                      "note": "外包服务供应商在履行外包合同时导致泄露，"
                              "保险人对首次提出的索赔承担赔付"},
            "F1-10": {"status": "unmapped"},
            "F2-11": {"status": "excluded", "clause": "第四条 责任免除"},
            "F3-05": {"status": "excluded", "clause": "第四条 商业秘密及知识产权"},
            "F8-01": {"status": "unmapped", "clause": "—",
                      "note": "无独立的品牌价值修复责任，声誉相关仅在应急响应费用项下"},
            "S1-02": {"status": "covered", "clause": "第二条第九款",
                      "note": "承保人为错误或技术故障（静电、升级失败、软件错误等）"
                              "引发的营业中断"},
            "S2-01": {"status": "excluded", "clause": "第四条 责任免除"},
            "S2-05": {"status": "unmapped"},
            "S3-01": {"status": "nominal_only", "clause": "第一条第四款 网络勒索损害赔偿",
                      "note": "须经保险人事先书面同意；国内监管实践下赎金不可赔"},
            "S3-02": {"status": "conditional", "clause": "第一条第四款 网络勒索费用",
                      "note": "IT顾问、公关顾问、法律合规顾问、危机谈判专家费用"},
            "R1-04": {"status": "covered", "clause": "第一条第一款 保密责任损害赔偿",
                      "note": "第三方因敏感信息泄露向被保险人索赔的替代性赔偿责任"},
            "R2-02": {"status": "conditional", "clause": "第三条第十四款 赔偿请求费用",
                      "note": "监管程序的调查与抗辩**费用**可赔；但监管机构处以的"
                              "罚款本身另见 settlement_notes 中的框架缺口说明"},
            "R1-06": {"status": "excluded", "clause": "第四条 合同责任除外"},
            "R3-01": {"status": "unmapped"},
        },
    },
    "settlement": {
        "aggregate_limit": 12000000,
        "deductible": {"scope": "per_occurrence", "amount": 120000},
        "bi": {
            "items": ["S1-01", "S1-02", "S1-03"],
            "deductible_mode": "waiting_only",
            "deductible": 0,
            "max_indemnity_days": 90,
            "clause": "第三条第十一款 等待期以小时计，代替固定免赔额用于营业中断；"
                      "第一条第六款E项 赔偿期自等待期届满后起算，最长不超过三个月",
        },
        "sublimits": [
            {"id": "SL-IR", "name": "应急响应费用", "items": ["F1", "F4", "F5", "F6", "F7"],
             "limit": 3000000, "shares_aggregate": True, "clause": "明细表第六项"},
            {"id": "SL-DATA", "name": "数据修复与改进费用", "items": ["F2", "F3"],
             "limit": 2500000, "shares_aggregate": True, "clause": "第一条第五款 / 第二条第六款"},
            {"id": "SL-BI", "name": "营业中断损失及修复费用", "items": ["S1", "S4"],
             "limit": 4000000, "shares_aggregate": True, "clause": "第一条第六款"},
            {"id": "SL-EXT", "name": "网络勒索", "items": ["S3"],
             "limit": 1000000, "shares_aggregate": True, "clause": "第一条第四款 / 明细表第六项"},
            {"id": "SL-LIAB", "name": "三大责任与抗辩费用", "items": ["R1", "R2"],
             "limit": 8000000, "shares_aggregate": True, "clause": "一般条件第五条第四款E项"},
        ],
        "conditional_deductible": [],
    },
    "settlement_notes": [
        "**监管罚款是本保单的标志性观察点，同时暴露了本框架的一个缺口**："
        "条款第三条第九、三十八款把监管机构作出的金钱性质罚款和处罚写入损害赔偿范围，"
        "但附「在法律和赔偿支付地允许承保的前提下」这一限定语——"
        "与赎金条款的「在中国法律允许范围内」是同一种句式。"
        "我国行政处罚具有人身与财产制裁属性，依法不得通过保险转嫁，"
        "故该项在境内实际不可赔。",
        "**框架缺口（如实记录，不作掩饰）**：本工具的 69 项赔付科目中"
        "**没有「行政罚款与监管处罚」的独立位置**。R1-06 是合同违约罚金，"
        "R2-02 是监管程序的调查抗辩**费用**，均非行政罚款本身。"
        "曾一度将其硬塞进 R1-04「客户与伙伴补偿费」，但该科目的本义是"
        "第三方客户索赔，与行政罚款性质完全不同，已撤回该映射。"
        "后果是：行政罚款这笔损失既无法进入事实口径核定，也无法在承保过滤层显形。"
        "**建议在 R1 大类下增设「R1-07 行政罚款与监管处罚」，并默认标注 nominal_only**——"
        "这正是本土化损失分类框架需要区别于国际条款结构的一个具体位置。"
        "在增设之前，涉及行政罚款的案例须在案情与争议点中以文字记录金额与不可赔理由。",
        "营业中断的等待期以**小时**计（第三条第十一款），且明确「代替固定免赔额使用」——"
        "即等待期与免赔额是替代关系而非并列关系，本配置按 waiting_only 处理。"
        "案例中 S1-01 的 p3 应填「等待期小时数 ÷ 24」。",
        "赔偿期自等待期届满后起算且不超过三个月（90天），是保单库中最短的赔偿期，"
        "对长周期恢复的事故（如工控系统重建）会形成显著缺口。",
    ],
}


ALL_POLICIES = [ZURICH, TAIKANG, PINGAN, ZHUFENG, COSCO,
                GUOSHOU_B, GUOSHOU_LIABILITY, SUNSHINE,
                ALLIANZ, CHUBB]


def main() -> None:
    payload = {
        "schema_version": "1.0",
        "disclaimer": (
            "本保单库的责任映射（coverage）依据各产品公开条款的分析文件整理，"
            "结算参数（settlement）中的限额与免赔额为演示用假设值——"
            "条款文本中这些数值普遍表述为「由投保人与保险人协商确定」，并无公开数字。"
            "任何引用本库输出的场合都必须标明该假设。"
        ),
        "policies": ALL_POLICIES,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("已生成 %s（%d 款保单）" % (OUT_PATH, len(ALL_POLICIES)))


if __name__ == "__main__":
    main()
