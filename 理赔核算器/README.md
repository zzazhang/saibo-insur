# 理赔核算器

网络安全保险事件后的损失核定与保单结算工具。

```bash
python -m claims_calc            # 启动 Web，浏览器打开 http://127.0.0.1:8765/
python -m claims_calc.cli list   # 查看保单库
```

Web 端按「案件与损失项 → 参数填写 → 结果报告」三步完成，可打印或另存 PDF。

---

> 上手与新保单接入见 **[使用指南.md](使用指南.md)**。
> 保单库预加载了 10 款，但不限于这 10 款——新保单可加进库、可在案例中内联、
> 也可完全不指定保单只做损失核定，三条路都不需要改代码。

## 三层口径

工具把「赔多少」拆成三个互相独立的问题，每一层的结论意义完全不同：

| 层 | 回答什么 | 性质 | 实现 |
| --- | --- | --- | --- |
| ① 事实口径核定损失 | 这场事故到底造成了多少钱的损失 | 不看保单 | `formulas.py` + `engine.py` |
| ② 承保过滤计入金额 | 这些损失里哪些属于这张保单管的事 | **定性**，二值判断 | `policies.py` + 两级开关 |
| ③ 保单结算赔付额 | 属于管的那部分，最后实际打多少钱 | **定量**裁剪 | `settlement.py` |

② 少赔说明**买错了产品**，③ 少赔说明**保额买少了**——这是两个不同的结论，不能混在一起说。

未指定保单时只输出 ①②，`settlement.applied` 为 `false`。

## 承保状态六档

| 状态 | 含义 | 是否计入 |
| --- | --- | :---: |
| `covered` | 条款明确承保 | ✓ |
| `limited` | 有限承保 / 需特约 | ✓ |
| `conditional` | 附条件承保（须事先同意、须用指定机构等） | ✓ |
| `excluded` | 条款明确列为责任免除 | ✗ |
| `nominal_only` | 条款字面列明，但国内监管实践下实际不可赔 | ✗ |
| `unmapped` | 条款中没有对应责任项 | ✗ |

`nominal_only` 是本项目的关键设计：把「条款写了」与「实际赔得出来」分开记录。
典型如赎金——多数条款都写了网络勒索责任，但普遍带「在中国法律允许范围内」之类
的限定语，实践中不可赔。这一档让案例能同时展示两个数字。

## 结算顺序

顺序固定，颠倒会得到不同结果：

1. 取各科目计入金额为基数
2. 营业中断按保单口径重算 + SLA 抵扣
3. 分项限额裁剪
4. 免赔额（BI 若已在第 2 步自留则不重复扣）
5. 条件免赔额调整
6. 累计赔偿限额封顶

### 三个已知的坑

**坑① 等待期重复扣减。** `S1-01/S1-02` 的公式里 `p3` 已经扣过一次等待期。
若保单是「免赔额与等待期自留额取高者」（苏黎世 6.3、泰康第八条第四款），
在核定损失上再减一次免赔额就是错的。`settlement.py` 把 BI 拆成
`gross / waiting_retention / net` 三个量，按 `bi.deductible_mode` 重新组装：

| 模式 | 可赔基数 | 适用 |
| --- | --- | --- |
| `waiting_only` | Σnet | 只有等待期，无额外 BI 免赔额 |
| `deductible_only` | Σgross − D | 只有免赔额，条款无等待期概念 |
| `higher_of` | Σgross − MAX(Σwaiting, D) | 取高者（苏黎世 / 泰康） |
| `both` | Σnet − D | 二者叠加，少数条款 |

**坑② 分项限额是否占用累计限额。** 苏黎世 5.3 明确分项限额是累计限额的一部分、
不额外增加；中远海运第七条的安全服务包则独立于现金赔付限额。由
`sublimit.shares_aggregate` 显式声明，免赔额按占比分摊回两侧。

**坑③ 免赔额的适用范围。** 每次事故一个免赔额 / 每项责任各自免赔额，两种结构
结果不同，由 `deductible.scope` 声明（`per_occurrence` / `per_sublimit`）。
条件性免赔额（如中远海运第四条「隐患未整改则免赔额增加 10%」）通过
`policy_flags` 触发。

**坑④ 保单参数漏进事实层。** `S3-01` 的赎金分项限额、`F8-01` 的品牌修复分项限额
是结算层引入前遗留的**行内公式变量**。填「支付 60 万、限额 50 万」，事实口径记的是
50 万而非实际支付额——事实层被保单参数污染了。限额裁剪现在归第③层，这两个行内
限额应留空；指定保单后若仍填了，引擎会告警。

### 案例文件的「没写 = 没发生」

`catalog.json` 里的 `default` 是给 Web 端预填演示数据用的（`S3-01` 赎金默认 80 万、
`S1-01` 中断收入默认 32 万）。案例文件是**已写明的事实**，部分提交时未声明的科目
必须记 0，否则一个写明「未支付赎金」的案子会凭空多出 80 万核定损失，而且从结果上
完全看不出来。

引擎据此自动选择模式：`items` 非空且少于 69 项 → 严格模式（未声明记 0）；
全量提交或不给 `items` → 沿用 catalog 默认，Web 端行为不变。
可用 `strict_items` 字段显式覆盖。

---

## 保单库

`claims_calc/data/policies.json`，由 `tools/build_policies.py` 生成——判断依据写在
可读的 Python 里，改的时候能看见理由。当前 5 款：

| id | 产品 | 结构特点 |
| --- | --- | --- |
| `zurich-cn-2020` | 苏黎世中国 2020 | 分项限额不额外增加累计限额；BI 取高者；承保社工诈骗与 PCI |
| `taikang-online` | 泰康在线综合保险 | BI 取高者（第八条第四款）；承保从属营业收入损失 |
| `pingan-cyber-b` | 平安网络安全企业财产险 B 款 | 明确除外外包商责任；多项费用须事先同意 |
| `zhufeng-detect-repair` | 珠峰检测与修复费用险 | 纯费用重置型，承保面极窄；强制指定服务机构 |
| `cosco-emergency-service` | 中远海运应急响应服务险 | 服务给付型 + 条件免赔额上浮 10% |

> **参数假设声明**：责任映射（`coverage`）严格依据条款分析文件；但结算参数
> （`settlement`）中的限额与免赔额全部是**演示用假设值**。条款原文对这些数值的
> 表述普遍为「由投保人与保险人协商确定」，并无公开数字。每款保单的
> `parameters_are_assumed` 均为 `true`，前端与报告都会显示该标记。
> 任何引用本工具输出的场合都必须标明该假设。

修改后重新生成：

```bash
python tools/build_policies.py
```

## 案例文件

案例 JSON 就是 `/api/compute` 的入参，落盘后即可复现。最小可用的案例只需要
`policy_id` + 涉及科目的参数——`include` 交给 `coverage_mode: "policy"` 由条款
责任映射自动决定，不必手写 69 行开关。

```json
{
  "schema_version": "1.0",
  "case_id": "CASE-01",
  "case_name": "某电商平台遭黑客入侵致系统与数据破坏",
  "calc_date": "2026-03-15",
  "narrative": {
    "insured": "被保险人画像",
    "incident": "事故经过",
    "timeline": ["2026-03-01 首次发现异常"],
    "disputes": ["争议点与本土化提示"]
  },
  "policy_id": "pingan-cyber-b",
  "coverage_mode": "policy",
  "policy_flags": { "unremediated_finding": false },
  "s1_method": "公式外推法",
  "categories": { "F1": { "switch": "ON" } },
  "items": { "F1-01": { "params": { "p1": 40, "p2": 1500 } } }
}
```

`narrative` 是纯描述，不参与计算，只进 Markdown 报告。
个别科目需要偏离条款判定时（论证特约扩展等），加 `"include_override": true`
并显式给出 `include`——引擎会照做，同时在 warnings 里留痕。

## 参数来源层

条款只管「赔什么」，不管「多少钱」。案例里的工时、费率、日均收入这些数字，
条款文本一个都给不了。没有出处的数字，案例就只是格式样例。

### 本土化原则

**工时与服务成本类科目一律优先使用 GB/T 42461-2023 国标口径，只有在国内确无
对应数据源时才援引国际报告，且必须显式标注口径差异。**

IBM、Sophos 的数字是全球或美国口径、以美元计。拿 444 万美元的全球均值去核定
一家中国物流企业的损失，本身就是本项目所批判的「直接移植国际标准」。
参数层不本土化，损失分类框架的本土化就是半截子工程。

GB/T 42461-2023 恰好补上这一块：与 GB/T 20986-2023（本项目 6 模块框架的依据）
同属一个标准族，专为网络安全服务的成本预算、招投标、决算而设，给出分省市、
分级别的服务人员成本单价，由 CCIA 每年更新。其人力成本公式为：

```
L = Σ(Pᵢ × Qᵢ)      Pᵢ 第 i 级人员成本单价（元/人日），Qᵢ 该级别工作量（人日）
S = AS ÷ 年工作天数   每月工作天数取 20.67（人社部发〔2025〕2 号）
```

catalog 的费率参数单位是元/小时，换算按 1 人日 = 8 小时。

### 可信度四档

| 档位 | 含义 | 可否对外引用 |
| --- | --- | :---: |
| `verified` | 在可靠来源中找到明确数字 | ✓ |
| `derived` | 由公开方法与公开输入推算，方法可复核 | ✓ |
| `pending` | 方法已确认，具体数值需查阅原始文件 | ✗ |
| `assumed` | 无来源，编者估计 | ✗ |

**标注了来源不等于有出处。** 标为 `editor-estimate` 的参数照样计入「待查证」，
审计器不会因为填了标注就放行。

### 案例中的标注方式

```json
"param_sources": {
  "F1-01.p2": {"ref": "sec-service-rate-senior", "note": "按高级级别单价 ÷8 折算"},
  "S1-01.p1": {"ref": "editor-estimate", "note": "按年营收 6.6 亿 ÷ 365 取整"}
}
```

键为 `科目编号.参数键`，凭证类科目直接用 `科目编号`。该块不参与计算，只进报告。

```bash
python -m claims_calc.cli sources              # 列出来源库
python -m claims_calc.cli audit cases/*.json -v # 检查标注覆盖
```

来源库由 `tools/build_parameter_sources.py` 生成。

## 命令行

```bash
python -m claims_calc.cli list                          # 保单库
python -m claims_calc.cli mapping <保单id> --out x.md    # 69 项条款责任对应表
python -m claims_calc.cli sources                       # 参数来源库
python -m claims_calc.cli audit cases/*.json -v         # 参数来源标注审计
python -m claims_calc.cli validate cases/*.json         # 只校验结构
python -m claims_calc.cli run cases/*.json              # 批量跑数
python -m claims_calc.cli run cases/*.json --md out/    # 导出 Markdown 报告与结果 JSON
python -m claims_calc.cli compare cases/case-01.json \
       --policies pingan-cyber-b,taikang-online         # 同一事故跑多张保单
```

`compare` 是案例集做平行对照的主力：同一套案件事实换保单，直接得到赔付率对照表。

## Web 端新增

- **投保产品**下拉：选定后自动按条款责任映射填充 69 个科目的计入开关，
  每个科目标题旁显示承保状态徽标（悬停看条款出处与理由）
- **条件条款勾选**：保单若有条件免赔额，按案情勾选即可生效
- **导入/导出案例 JSON**、**导出 Markdown 报告**
- **案例库**面板：保存到 `cases/` 目录、一键载入，与 CLI 共用同一批文件
- 报告页新增「保单结算过程」：逐步结算表、分项限额适用情况、
  营业中断口径拆解、已核定但不予赔付的科目清单

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/catalog` | 69 科目与 15 大类定义 |
| GET | `/api/demo` | 演示案入参 |
| POST | `/api/compute` | 核算，返回三层结果 |
| GET | `/api/policies` | 保单库列表 |
| GET | `/api/policies/<id>` | 单个保单 + 69 项完整责任映射 |
| GET | `/api/cases` | 案例库列表 |
| GET/POST/DELETE | `/api/cases/<name>` | 读取 / 保存 / 删除案例 |
| POST | `/api/validate` | 校验案例结构 |
| POST | `/api/export/markdown` | 生成 Markdown 报告 |

案例名只允许字母、数字、下划线、连字符；含路径分隔符或 `..` 的直接报错，
不做静默截断。

## 测试

```bash
python -m pytest tests/ -q
```

`tests/test_settlement.py` 覆盖三个坑的回归、承保状态映射、SLA 抵扣边界、
案例文件读写与穿越防护，并确保 `cases/` 目录下每个案例都能跑通。
`tests/test_engine.py` 是改造前的黄金用例，用于保证第①②层无回归。
