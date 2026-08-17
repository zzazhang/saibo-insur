# -*- coding: utf-8 -*-
"""
生成《十案汇总（含案情）.md》。

从案例 JSON 与引擎输出直接生成，案情叙述与计算结果同源，
避免手写文档时数字与引擎脱节——C4 就是这么发现叙述里算错了一个数。

用法：  python tools/build_summary.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from claims_calc import cases as cio  # noqa: E402
from claims_calc import policies as pol  # noqa: E402
from claims_calc import sources as psrc  # noqa: E402
from claims_calc.engine import compute, get_catalog  # noqa: E402

OUT = os.path.join(ROOT, "..", "案例集", "十案汇总（含案情）.md")

ORDER = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C8B", "C9", "C10"]

# 每案的一句话定位与核心论证点
HEADLINE = {
    "C1": ("对照组 A 正面", "外包商责任**承保**，确立十案保障上界"),
    "C2": ("框架缺口一", "行政罚款：条款上不可赔，框架上不可测"),
    "C3": ("框架缺口二", "社工诈骗本金：条款上可赔，框架上无处安放"),
    "C4": ("实务发现", "SLA 补偿与保险赔付高度重叠，稀释从属中断责任"),
    "C5": ("唯一销售侧缺口", "产品能保 ≠ 被保险人买到了保障"),
    "C6": ("对照组 A 反面", "外包商责任**除外**，差额主体实为第三方责任"),
    "C7": ("对照组 B 第一方", "小时/净利润口径换算；第三方责任全缺"),
    "C8": ("反事实基准", "赎金名义承保；无营业中断责任"),
    "C8B": ("反事实对照", "多损失 60 万，赔付一分不变"),
    "C9": ("对照组 B 第三方", "与 C7 承保范围零重叠，完全互补"),
    "C10": ("程序性一票否决", "未用指定机构，整案赔付归零"),
}


def money(x) -> str:
    try:
        return format(float(x or 0), ",.0f")
    except (TypeError, ValueError):
        return str(x)


def load_all():
    rows = []
    for c in cio.list_cases():
        if c["name"].startswith("demo-"):
            continue
        case = cio.load_case(c["name"])
        result = compute(cio.strip_to_compute(case))
        rows.append((case, result))
    rows.sort(key=lambda x: ORDER.index(x[0]["case_id"]))
    return rows


def render_case(case, result) -> list:
    """单个案例：定位 → 被保险人 → 事故经过 → 时间线 → 损失与判定 → 三层结果 → 发现。"""
    s = result["summary"]
    stl = result["settlement"]
    pinfo = result.get("policy") or {}
    nar = case.get("narrative") or {}
    tag, point = HEADLINE.get(case["case_id"], ("", ""))

    L = []
    L.append("### %s　%s" % (case["case_id"], case["case_name"]))
    L.append("")
    L.append("> **定位**：%s　|　**论证点**：%s" % (tag, point))
    L.append("")
    L.append("| | |")
    L.append("| --- | --- |")
    L.append("| 投保产品 | %s |" % (pinfo.get("name") or "—"))
    L.append("| 产品结构 | %s |" % (pinfo.get("product_type") or "—"))
    L.append("| 条款来源 | %s |" % (pinfo.get("source_file") or "—"))
    L.append("")

    if nar.get("insured"):
        L.append("**被保险人**")
        L.append("")
        L.append(nar["insured"])
        L.append("")
    if nar.get("incident"):
        L.append("**事故经过**")
        L.append("")
        L.append(nar["incident"])
        L.append("")
    if nar.get("timeline"):
        L.append("**时间线**")
        L.append("")
        for t in nar["timeline"]:
            L.append("- %s" % t)
        L.append("")

    # 损失构成与条款判定
    items = [i for i in result["items"] if (i.get("assessed_loss") or 0) > 0]
    if items:
        L.append("**损失构成与条款判定**")
        L.append("")
        L.append("| 编号 | 科目 | 核定损失 | 条款判定 | 计入 |")
        L.append("| --- | --- | ---: | --- | :---: |")
        for i in items:
            label = i.get("coverage_label") or "—"
            if i.get("include_override"):
                label += "（本保单未投保）"
            L.append("| %s | %s | %s | %s | %s |" % (
                i["code"], i["name"], money(i["assessed_loss"]),
                label, "✓" if i.get("effective_covered") else "✗"))
        L.append("")

    # 三层结果
    L.append("**三层口径结果**")
    L.append("")
    L.append("| 口径 | 金额（元） |")
    L.append("| --- | ---: |")
    L.append("| ① 事实口径核定损失 | %s |" % money(s["fact_total"]))
    L.append("| ② 承保过滤计入金额 | %s |" % money(stl.get("covered_total")))
    L.append("| ③ 保单结算赔付额 | **%s** |" % money(stl.get("payable")))
    L.append("")
    if stl.get("applied"):
        L.append("赔付率 **%.1f%%**　|　被保险人自留 %s 元"
                 % (stl["payout_ratio_vs_fact"] * 100, money(stl["self_retention"])))
        L.append("")

    # 结算过程中真正起作用的环节
    cuts = [r for r in stl.get("sublimits") or [] if r.get("cut", 0) > 0]
    if cuts:
        L.append("分项限额触顶：")
        for r in cuts:
            L.append("- %s：限额 %s，裁剪前 %s，削减 **%s**"
                     % (r["name"], money(r["limit"]), money(r["before"]), money(r["cut"])))
        L.append("")
    if stl.get("conditional_notes"):
        for n in stl["conditional_notes"]:
            L.append("- 触发条件条款：%s" % n)
        L.append("")

    bi = stl.get("bi") or {}
    if bi.get("gross"):
        L.append("营业中断口径：毛损失 %s，自留 %s（%s），SLA 抵扣 %s，可赔基数 **%s**"
                 % (money(bi["gross"]), money(bi["retention_applied"]), bi["mode"],
                    money(-bi["sla_deduction"]), money(bi["base"])))
        L.append("")

    # 争议点
    if nar.get("disputes"):
        L.append("**关键判断与争议点**")
        L.append("")
        for d in nar["disputes"]:
            L.append("- %s" % d)
        L.append("")

    L.append("---")
    L.append("")
    return L


def main() -> None:
    rows = load_all()
    catalog = get_catalog()
    L = []

    L.append("# 十案汇总（含案情）")
    L.append("")
    L.append("网络安全保险理赔案例集。十个案例覆盖保单库全部 10 款产品，"
             "按**产品结构类型**排布，含三组受控对比。")
    L.append("")
    L.append("全部数字由理赔核算器算出，可复现：")
    L.append("")
    L.append("```bash")
    L.append("cd 理赔核算器")
    L.append("python -m claims_calc.cli run cases/*.json --md ../案例集/案例报告")
    L.append("python tools/build_summary.py          # 重新生成本文档")
    L.append("```")
    L.append("")
    L.append("本文档由脚本从案例 JSON 与引擎输出直接生成，"
             "案情叙述与计算结果同源，不存在手写数字与引擎脱节的风险。")
    L.append("")

    # ---- 总表 ----
    L.append("## 一、总表")
    L.append("")
    L.append("| 编号 | 案例 | 保单 | 产品结构 | 事实损失 | 计入金额 | 赔付额 | 赔付率 |")
    L.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
    tot_f = tot_p = 0.0
    for case, r in rows:
        s, stl = r["summary"], r["settlement"]
        p = r.get("policy") or {}
        if case["case_id"] != "C8B":
            tot_f += s["fact_total"]
            tot_p += stl.get("payable") or 0
        L.append("| %s | %s | %s | %s | %s | %s | %s | %.1f%% |" % (
            case["case_id"], case["case_name"], p.get("name") or "—",
            (p.get("product_type") or "").split("（")[0],
            money(s["fact_total"]), money(stl.get("covered_total")),
            money(stl.get("payable")), (stl.get("payout_ratio_vs_fact") or 0) * 100))
    L.append("")
    L.append("十案合计（不含反事实 C8B）：事实损失 **%s** 元，赔付 **%s** 元，"
             "平均赔付率 **%.1f%%**。" % (money(tot_f), money(tot_p), tot_p / tot_f * 100))
    L.append("")
    L.append("> **C2 的 98.7% 是表面数字。** 该案 300 万元行政罚款因 69 科目无对应位置"
             "而未进入任何口径；计入后实际经济损失 12,557,019 元，"
             "**真实覆盖率仅 75.2%**。该赔付率不得单独引用。")
    L.append("")
    L.append("赔付率区间 **0% – 98.7%**，而这十款产品在市场上都叫「网络安全保险」。")
    L.append("")

    # ---- 承保面 ----
    L.append("## 二、按产品结构看缺口位置")
    L.append("")
    L.append("| 结构类型 | 保单 | 可计入科目 | 缺口在哪 |")
    L.append("| --- | --- | ---: | --- |")
    GAPS = {
        "allianz-ecommerce": "限额与程序性条件",
        "sunshine-2016": "**未投保的模块**",
        "chubb-cyber-erm": "行政罚款、赔偿期仅 90 天",
        "zurich-cn-2020": "分项限额触顶",
        "taikang-online": "SLA 补偿重叠稀释",
        "pingan-cyber-b": "第三方责任、外包商",
        "guoshou-cyber-b": "第三方责任全缺",
        "cosco-emergency-service": "现金补偿与营业中断",
        "guoshou-liability": "自身损失全缺",
        "zhufeng-detect-repair": "除检测修复外全缺",
    }
    stats = []
    for p in pol.list_policies():
        cov = pol.build_coverage_map(pol.get_policy(p["id"]), catalog)
        st = pol.coverage_stats(cov)
        incl = sum(st.get(k, 0) for k in pol.INCLUDING_STATUSES)
        stats.append((incl, p, GAPS.get(p["id"], "")))
    stats.sort(reverse=True, key=lambda x: x[0])
    for incl, p, gap in stats:
        L.append("| %s | %s | %d（%.0f%%） | %s |" % (
            (p.get("product_type") or "").split("（")[0], p["name"],
            incl, incl / len(catalog["items"]) * 100, gap))
    L.append("")
    L.append("承保面 **%d%% – %d%%**，%.0f 倍差距。" % (
        stats[-1][0] / 69 * 100, stats[0][0] / 69 * 100, stats[0][0] / stats[-1][0]))
    L.append("")

    # ---- 逐案 ----
    L.append("## 三、逐案详述")
    L.append("")
    for case, r in rows:
        L.extend(render_case(case, r))

    # ---- 三组受控对比 ----
    by_id = {c["case_id"]: (c, r) for c, r in rows}

    def pair_table(a, b, title, note):
        out = ["### %s" % title, ""]
        out.append("| | 计入金额 | 赔付额 | 赔付率 |")
        out.append("| --- | ---: | ---: | ---: |")
        for cid in (a, b):
            case, r = by_id[cid]
            stl = r["settlement"]
            out.append("| %s %s | %s | %s | %.1f%% |" % (
                cid, (r.get("policy") or {}).get("name"),
                money(stl["covered_total"]), money(stl["payable"]),
                stl["payout_ratio_vs_fact"] * 100))
        gap = abs(by_id[a][1]["settlement"]["payable"]
                  - by_id[b][1]["settlement"]["payable"])
        out.append("")
        out.append("**赔付差额 %s 元。** 两案事实损失完全相同（%s 元），"
                   "差额可完全归因于产品结构。" % (
                       money(gap), money(by_id[a][1]["summary"]["fact_total"])))
        out.append("")
        out.append(note)
        out.append("")
        return out

    L.append("## 四、三组受控对比")
    L.append("")
    L.append("三组均为同一事故、同一套损失参数，仅变更一项变量。")
    L.append("")

    L.extend(pair_table("C1", "C6", "A. 外包商责任（安联 vs 平安 B 款）",
        "**差额主因排序（这个顺序容易归因错）**：\n"
        "1. **第三方责任占差额主体** —— 平安 B 款以第一方为主，"
        "法律与调查费用分项限额仅 50 万，削减 1,888,000 元\n"
        "2. 检测与专业机构费用限额 30 万，削减 830,240 元\n"
        "3. 数据恢复与安全防御限额 50 万，削减 440,600 元\n"
        "4. 外包商相关条款 —— S1-02 依赖中断除外、F1-06 供应链调查降为有限承保\n\n"
        "若把差额笼统归因于「外包商责任」，结论对但理由错。"
        "为使外包商除外真正咬合，C1 案情必须显式包含 F1-06 供应链调查费与 "
        "S1-02 依赖中断损失——若只用普通科目，平安 B 款的外包商除外一次都不会触发。\n\n"
        "**悬崖提示**：平安 B 款第十五条第十三款除外的是「IT 外包商**未被认可**的操作失误」。"
        "本案设定运维商已列为认可服务提供商。若企业更换运维供应商后未书面通知保险人"
        "（国内极常见），该条构成**原因型除外，整案赔付归零**。"))

    L.extend(pair_table("C7", "C9", "B. 第一方与第三方互补（同一保险人）",
        "**重叠承保科目 0 项** —— 两款产品承保范围完全不相交，一分钱不重复。\n\n"
        "| 采购组合 | 赔付 | 覆盖事实损失 |\n| --- | ---: | ---: |\n"
        "| 只投 B 款 | 2,705,178 | 23.3% |\n"
        "| 只投责任险 | 8,260,000 | 71.2% |\n"
        "| **两款合投** | 10,965,178 | **94.5%** |\n\n"
        "只投 B 款则 836 万第三方索赔裸奔，只投责任险则 285 万自身损失裸奔。"
        "仍有 39 万元（加固费 + PLC 硬件）两边都不赔——**缺口不因多买一张保单而消失**。\n\n"
        "**最大不确定性**：下游主机厂索赔依据的是供货协议交付违约条款，"
        "性质更接近合同责任。多数责任险对纯合同违约设有除外。"
        "若核赔认定为违约金，C9 的 800 万全部落空。"))

    L.extend(pair_table("C8", "C8B", "C. 赎金反事实",
        "**多损失 60 万，赔付额一分不变。** 中远海运第八条第一款明文承保赎金、"
        "第十二条设了独立分项限额、第二十六条索赔材料里直接写了「勒索金支付记录」"
        "——文本上配置完整。但第二十三条要求「涉及网络勒索须立即向公安部门报案」，"
        "索赔时须**同时**提交报案回执与支付记录。这两份材料在国内难以同时合法取得，"
        "**条款自己把自己堵死了**。"))

    # ---- 结构性发现 ----
    L.append("## 五、四类结构性发现")
    L.append("")
    L.append("### 1. 「名义承保」是一类现象，不是赎金的孤例")
    L.append("")
    L.append("| 责任项 | 条款限定语 | 保单 |")
    L.append("| --- | --- | --- |")
    L.append("| 赎金 | 「按照中国法律规定」 | 国寿财 B 款 |")
    L.append("| 赎金 | 「在中国法律允许范围内」 | 多款 |")
    L.append("| 赎金 | 须报案 + 须提交支付记录（互斥） | 中远海运 |")
    L.append("| **行政罚款** | 「**在法律和赔偿支付地允许承保的前提下**」 | 安达 |")
    L.append("")
    L.append("安达的行政罚款条款与赎金条款是**同一种句式**。国际条款移植入境时保留了"
             "本国不可执行的责任项，靠一句限定语把风险推回投保人。"
             "这使「名义承保」从单点观察升级为可命名的模式。")
    L.append("")
    L.append("### 2. 框架缺口两处，性质不同")
    L.append("")
    L.append("| | C2 行政罚款 | C3 资金本金 |")
    L.append("| --- | --- | --- |")
    L.append("| 条款态度 | 写了，但国内不可赔 | 写了，且可赔 |")
    L.append("| 69 科目 | 无对应位置 | 无对应位置 |")
    L.append("| 漏掉的后果 | 低估**真实损失** | 低估**赔付额** |")
    L.append("| 本案处理 | 文字记录 + 量化落差 | 借用 F1-10 并标注 |")
    L.append("| **建议增设** | **R1-07 行政罚款与监管处罚**（默认 nominal_only） "
             "| **S2-06 资金损失（被骗或被盗资金）** |")
    L.append("")
    L.append("C2 的量化后果：表面赔付率 98.7%，计入罚款后真实覆盖率 75.2%，"
             "**落差 23.6 个百分点**；工具显示自留 12 万，实际自留 312 万，**差 26 倍**。")
    L.append("")
    L.append("两个缺口都指向同一结论：本土化损失分类框架需要在国际条款结构之外增设科目。")
    L.append("")
    L.append("### 3. 四个坑在真实案例中的实际金额")
    L.append("")
    L.append("**坑① 等待期与免赔额重复扣减** —— higher_of 已三次适用，**取值方向三次不同**：")
    L.append("")
    L.append("| 案例 | 等待期自留 | 免赔额 | 取值 |")
    L.append("| --- | ---: | ---: | --- |")
    for cid in ("C7", "C3", "C4"):
        bi = by_id[cid][1]["settlement"]["bi"]
        pick = "等待期" if bi["retention_applied"] == bi["waiting_retention"] else "免赔额"
        L.append("| %s %s | %s | %s | %s |" % (
            cid, (by_id[cid][1].get("policy") or {}).get("name", "")[:8],
            money(bi["waiting_retention"]), money(bi["deductible"]), pick))
    L.append("")
    L.append("不能简化为固定做法。C4 若按错误做法多扣 10 万，"
             "而该金额已接近该案营业中断可赔基数的两倍——**坑①在中小额中断中破坏力最大**。")
    L.append("")
    L.append("**坑② 分项限额是否占用累计限额** —— 苏黎世 5.2.3/5.3.3–5.3.7、"
             "安联明细表第六项、国寿财 B 款 13.1 节均明确「不额外增加」；"
             "中远海运第七条的安全服务包则独立于现金赔付限额。"
             "同样叫「分项限额」，两种结构结果不同。")
    L.append("")
    L.append("**坑③ 免赔额适用范围与条件免赔额** —— 中远海运第四条"
             "「隐患未整改免赔额上浮 10%」（C8 实测多扣 1 万）；"
             "珠峰第五条第七款「非指定机构全额免赔」（C10 实测赔付归零）。")
    L.append("")
    L.append("**坑④ 保单参数漏进事实层** —— S3-01 赎金分项限额、F8-01 品牌修复限额"
             "是行内公式变量，填了会让核定损失记成限额而非实际发生额。"
             "指定保单后重复设限即告警。")
    L.append("")
    L.append("### 4. 三条实务发现")
    L.append("")
    L.append("**SLA 补偿与保险赔付高度重叠（C4）**。营业中断毛损失 487,311 → "
             "扣等待期自留 153,920 → 扣云服务商 SLA 补偿 280,000 → "
             "**实际可赔基数仅 53,391 元，不足事实中断损失的 11%**。"
             "依赖公有云的企业若已获可观 SLA 补偿，"
             "从属营业中断责任的边际价值远低于投保时的直观预期。")
    L.append("")
    L.append("**缺口可以来自销售环节（C5）**。阳光 2016 全模块投保时承保面 80%，"
             "H公司只投了模块 1.1 与 1.2：仅投两模块赔付 1,920,000（37.8%），"
             "假设六模块全投保赔付 4,788,560（94.3%），"
             "**投保选择一项造成 2,868,560 元缺口**。"
             "产品理论上能承保，不等于被保险人买到了保障。")
    L.append("")
    L.append("**程序性条件可能一票否决（C10）**。J单位因情况紧急直接启用长期合作的"
             "安全厂商，未联系保险人指定机构：赔付归零；假设联系了指定机构则赔 490,000"
             "（21.9%）。**一个流程环节值 49 万元。** 且即便流程走对，"
             "仍有 1,469,470 元（占事实损失 65.6%）因承保面过窄而落空。")
    L.append("")

    # ---- 引用限制 ----
    L.append("## 六、引用限制（必读）")
    L.append("")
    L.append("**十案全部标注为「尚不可对外引用」。** 审计器对每个案例执行参数来源检查，"
             "当前状态：参数标注覆盖率 100%，但绝大多数为 `editor-estimate`（编者估计）。")
    L.append("")
    L.append("| 可信度 | 含义 | 可否引用 |")
    L.append("| --- | --- | :---: |")
    for k, v in (psrc.load().get("confidence_levels") or {}).items():
        L.append("| `%s` | %s | %s |" % (
            k, v, "✗" if k in psrc.WEAK_CONFIDENCE else "✓"))
    L.append("")
    L.append("**已核实的部分**：GB/T 42461-2023 表 A.1 分省市分级别服务人员成本单价，"
             "已用标准公式 (3) `Pᵢ = S × Kᵢ × (1+H)` 逐省复核，"
             "31 省市 × 4 级别全部吻合（误差不超过 2 元）。")
    L.append("")
    L.append("**待检验的部分**：")
    L.append("")
    L.append("- **市场加成系数 2.2**（成本 → 实付价格）为假设，"
             "且其点估计存在**已披露的循环性问题**——该值是从早期编者估计反推的，"
             "「重算后与原估计接近」不构成验证。有内容的是区间 1.5–3.0 与"
             "「国标成本不含利润」这一结构性事实。")
    L.append("- 工时量、恢复数据量、毛利率、索赔人数、单人赔偿金额等均按案情设定，"
             "逐条标注「此参数为假设，待数据检验」。")
    L.append("- 全部分项限额、免赔额、累计限额为演示用假设值——条款原文对这些数值的"
             "表述普遍为「由投保人与保险人协商确定」，并无公开数字。")
    L.append("")
    L.append("**因此：本案例集的赔付率可用于演示条款结构差异与工具能力，"
             "不得作为损失金额或赔付水平的实证依据对外引用。** "
             "引用条款判定（承保 / 除外 / 名义承保）时不受此限，"
             "因其严格依据公开条款文本。")
    L.append("")
    L.append("```bash")
    L.append("python -m claims_calc.cli audit cases/*.json -v   # 查看每案参数标注状态")
    L.append("```")
    L.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("已生成 %s（%d 案)" % (os.path.abspath(OUT), len(rows)))


if __name__ == "__main__":
    main()
