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
            "F1-06": {"status": "excluded", "clause": "第十六条第六款",
                      "note": "服务外包商自身的损失、费用和责任明确除外"},
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
                      "note": "外包商失误责任与服务外包商自身损失均除外，"
                              "故第三方/云服务商中断导致的依赖性损失不予赔付"},
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
        "conditional_deductible": [],
    },
    "settlement_notes": [
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


ALL_POLICIES = [ZURICH, TAIKANG, PINGAN, ZHUFENG, COSCO]


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
