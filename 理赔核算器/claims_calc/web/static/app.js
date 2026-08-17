/* 理赔核算器 v2：分步录入 + 报告输出；计算仍走原 /api/compute */
(function () {
  "use strict";

  function detectBasePath() {
    var path = window.location.pathname || "/";
    if (path.endsWith("/")) path = path.slice(0, -1);
    if (path.endsWith("/index.html")) path = path.slice(0, -"/index.html".length);
    if (!path || path === "/") return "";
    return path;
  }

  var BASE = detectBasePath();

  var SUMMARY_NOTE =
    "净核定损失为承保过滤后的计入口径（所选模块及明细开关均为 ON 才进入合计），" +
    "再减去已获 SLA 赔偿（抵扣上限不超过 S1 计入小计）。" +
    "间接损失口径目前统计品牌修复费（F8-01）与财务对照法下的营业中断（S1-03）；" +
    "直接损失 = 计入合计 − 间接小计。" +
    "事实口径汇总全部科目核定损失，不受开关影响，便于对照实际发生额与本次计入额。" +
    "未选择的损失模块在本次核算中不计入合计；两级开关只影响是否计入，不改变科目核定损失本身。";

  var CASE_TYPES = [
    {
      id: "ransomware",
      name: "勒索软件事件",
      modules: ["F1", "F2", "F3", "F6", "S1", "S2", "S3"],
      tip: "常见组合：响应取证、恢复重建、漏洞修复、通知、营业中断、资源损失与赎金。",
    },
    {
      id: "breach",
      name: "数据泄露",
      modules: ["F1", "F4", "F5", "F6", "R1", "R2", "R3"],
      tip: "侧重法律合规、公关通知与第三方/卡组织责任相关费用。",
    },
    {
      id: "interruption",
      name: "业务中断 / 可用性攻击",
      modules: ["F1", "F2", "F7", "S1", "S2"],
      tip: "侧重应急替代、系统恢复与营业中断收入损失。",
    },
    {
      id: "custom",
      name: "自定义组合",
      modules: [],
      tip: "不预勾模块，请按保单与案件事实自行勾选。",
    },
  ];

  var TIPS = {
    "case-type": "案件基础类型只用于预勾损失模块，不改变计算公式；可随时增删模块。",
  };

  var state = {
    catalog: null,
    caseData: null,
    result: null,
    timer: null,
    view: 1,
    selectedModules: {},
    caseTypeId: "ransomware",
    policies: [],
    policyId: "",
    policyDetail: null,
    coverageMode: "policy",
    policyFlags: {},
    narrative: null,
    includeOverrides: {},   // 科目编号 -> true，表示该项由案例显式覆盖条款判定
  };

  var COVERAGE_BADGE = {
    covered: { text: "承保", cls: "cov-ok" },
    limited: { text: "有限承保", cls: "cov-warn" },
    conditional: { text: "附条件承保", cls: "cov-warn" },
    excluded: { text: "明确除外", cls: "cov-no" },
    nominal_only: { text: "名义承保·实际不可赔", cls: "cov-nominal" },
    unmapped: { text: "条款无对应责任", cls: "cov-none" },
  };

  function api(url, options) {
    return fetch(BASE + url, options).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok && data && data.error) throw new Error(data.error);
        return data;
      });
    });
  }

  function money(n) {
    var x = Number(n);
    if (!isFinite(x)) return "0";
    return x.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  }

  function valOrEmpty(v) {
    if (v === null || v === undefined) return "";
    return String(v);
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(text) {
    var el = document.getElementById("status");
    if (el) el.textContent = text;
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function showWarnings(list) {
    var box = document.getElementById("warnings");
    if (!box) return;
    if (!list || !list.length) {
      box.classList.add("d-none");
      box.textContent = "";
      return;
    }
    box.classList.remove("d-none");
    box.textContent = "提示：" + list.join("；");
  }

  function currentCaseType() {
    for (var i = 0; i < CASE_TYPES.length; i++) {
      if (CASE_TYPES[i].id === state.caseTypeId) return CASE_TYPES[i];
    }
    return CASE_TYPES[CASE_TYPES.length - 1];
  }

  function selectedModuleList() {
    var catalog = state.catalog;
    var list = [];
    catalog.categories.forEach(function (cat) {
      if (state.selectedModules[cat.code]) list.push(cat);
    });
    return list;
  }

  /* ---------- View switching ---------- */
  function showView(n) {
    state.view = n;
    document.querySelectorAll(".view").forEach(function (el) {
      var id = Number(el.getAttribute("data-view"));
      if (id === n) el.classList.remove("d-none");
      else el.classList.add("d-none");
    });
    document.querySelectorAll("#step-nav .breadcrumb-item").forEach(function (el) {
      var step = Number(el.getAttribute("data-step"));
      el.classList.toggle("active", step === n);
      el.classList.toggle("done", step < n);
    });
    if (n === 2) {
      applyModuleVisibility();
      scheduleCompute();
    }
    if (n === 3) {
      runCompute(true).then(function () {
        renderReport();
      });
    }
    window.scrollTo(0, 0);
  }

  /* ---------- Module selection ---------- */
  function buildModulePicker() {
    var root = document.getElementById("module-picker");
    root.innerHTML = "";
    state.catalog.categories.forEach(function (cat) {
      var col = document.createElement("div");
      col.className = "col-md-4 col-lg-3";
      var box = document.createElement("label");
      box.className = "form-check module-check";
      var input = document.createElement("input");
      input.className = "form-check-input";
      input.type = "checkbox";
      input.id = "mod-" + cat.code;
      input.setAttribute("data-module", cat.code);
      input.checked = !!state.selectedModules[cat.code];
      input.addEventListener("change", function () {
        state.selectedModules[cat.code] = input.checked;
        var sw = document.getElementById("csw-" + cat.code);
        if (sw) sw.value = input.checked ? "ON" : "OFF";
      });
      var lab = document.createElement("span");
      lab.className = "form-check-label";
      lab.innerHTML =
        "<span class='mod-code'>" +
        escapeHtml(cat.code) +
        "</span>" +
        escapeHtml(cat.name);
      box.appendChild(input);
      box.appendChild(lab);
      col.appendChild(box);
      root.appendChild(col);
    });
  }

  function buildCaseTypeSelect() {
    var sel = document.getElementById("case-type");
    sel.innerHTML = "";
    CASE_TYPES.forEach(function (t) {
      var opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      sel.appendChild(opt);
    });
    sel.value = state.caseTypeId;
    sel.addEventListener("change", function () {
      state.caseTypeId = sel.value;
      applyCaseTypePreset(true);
    });
  }

  function applyCaseTypePreset(overwrite) {
    var t = currentCaseType();
    var preset = {};
    if (t.id === "custom") {
      if (overwrite) {
        state.catalog.categories.forEach(function (cat) {
          preset[cat.code] = false;
        });
        state.selectedModules = preset;
      }
    } else {
      state.catalog.categories.forEach(function (cat) {
        preset[cat.code] = t.modules.indexOf(cat.code) >= 0;
      });
      state.selectedModules = preset;
    }
    state.catalog.categories.forEach(function (cat) {
      var box = document.getElementById("mod-" + cat.code);
      if (box) box.checked = !!state.selectedModules[cat.code];
      var sw = document.getElementById("csw-" + cat.code);
      if (sw) sw.value = state.selectedModules[cat.code] ? "ON" : "OFF";
    });
  }

  function applyModuleVisibility() {
    state.catalog.categories.forEach(function (cat) {
      var on = !!state.selectedModules[cat.code];
      var block = document.getElementById("cat-" + cat.code);
      if (block) {
        if (on) block.classList.remove("module-hidden");
        else block.classList.add("module-hidden");
      }
      var sw = document.getElementById("csw-" + cat.code);
      if (sw && !on) sw.value = "OFF";
      if (sw && on && sw.value !== "ON" && sw.value !== "OFF") sw.value = "ON";
    });
    var s1on = !!state.selectedModules.S1;
    document.getElementById("s1-method-wrap").classList.toggle("d-none", !s1on);
    document.getElementById("sla-wrap").classList.toggle("d-none", !s1on);
  }

  /* ---------- Shell / items (reuse binding ids) ---------- */
  function buildShell() {
    var catalog = state.catalog;
    var headers = catalog.column_headers || {};
    var sh = catalog.summary_headers || {};

    var sel = document.getElementById("s1-method");
    sel.innerHTML = "";
    (catalog.s1_methods || []).forEach(function (m) {
      var opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      sel.appendChild(opt);
    });
    document.getElementById("s1-method-label").textContent =
      catalog.s1_method_label || "测法选择";
    var slaRow = catalog.sla_row || {};
    document.getElementById("sla-label").textContent =
      slaRow.param_label || "已获SLA赔偿(元)";

    var root = document.getElementById("items-root");
    root.innerHTML = "";
    catalog.categories.forEach(function (cat) {
      var block = document.createElement("div");
      block.className = "cat-block";
      block.id = "cat-" + cat.code;
      block.setAttribute("data-module", cat.code);

      var head = document.createElement("div");
      head.className = "cat-head";
      head.innerHTML =
        "<strong>" +
        escapeHtml(cat.code) +
        " " +
        escapeHtml(cat.name) +
        "</strong>" +
        "<label class='mb-0'>计入开关 " +
        "<select id='csw-" +
        cat.code +
        "'><option value='ON'>ON</option><option value='OFF'>OFF</option></select></label>" +
        "<span class='cat-meta' id='cat-meta-" +
        cat.code +
        "'></span>";
      block.appendChild(head);

      catalog.items
        .filter(function (it) {
          return it.category === cat.code;
        })
        .forEach(function (meta) {
          block.appendChild(renderItemCard(meta, headers));
        });
      root.appendChild(block);
    });

    bindInputs(document.body);
    var panel = document.querySelector("#help-panel .help-body");
    if (panel) panel.textContent = (catalog.notes || []).join("\n\n");
    document.getElementById("rpt-note").textContent = SUMMARY_NOTE;
  }

  function renderItemCard(meta, headers) {
    var card = document.createElement("div");
    card.className = "item-card";
    card.id = "item-" + meta.code;
    card.setAttribute("data-module", meta.category);

    var head = document.createElement("div");
    head.className = "item-head";
    var title = document.createElement("div");
    title.className = "item-title";
    title.innerHTML =
      "<span class='code'>" +
      escapeHtml(meta.code) +
      "</span><span class='name'>" +
      escapeHtml(meta.name) +
      "</span>";
    head.appendChild(title);

    if (meta.formula_desc || meta.hint) {
      var fold = document.createElement("details");
      fold.className = "item-meta";
      var sum = document.createElement("summary");
      sum.innerHTML = "计算式与提示 <span class='fold-hint'>点击展开</span>";
      fold.appendChild(sum);
      var body = document.createElement("div");
      body.className = "item-meta-body";
      if (meta.formula_desc) {
        body.innerHTML +=
          "<div class='meta-row'><span class='meta-k'>" +
          escapeHtml(headers.formula_desc || "计算式") +
          "</span>" +
          escapeHtml(meta.formula_desc) +
          "</div>";
      }
      if (meta.hint) {
        body.innerHTML +=
          "<div class='meta-row'><span class='meta-k'>" +
          escapeHtml(headers.hint || "提示") +
          "</span>" +
          escapeHtml(meta.hint) +
          "</div>";
      }
      fold.appendChild(body);
      head.appendChild(fold);
    }

    var grid = document.createElement("div");
    grid.className = "grid";

    (meta.params || []).forEach(function (p) {
      var isConfirm = meta.formula_type === "r1_confirm" && p.key === "p2";
      var label = document.createElement("label");
      label.appendChild(document.createTextNode(p.label || p.key));
      if (isConfirm) {
        var s = document.createElement("select");
        s.id = "p-" + meta.code + "-" + p.key;
        s.innerHTML = "<option value='是'>是</option><option value='否'>否</option>";
        label.appendChild(s);
      } else {
        var inp = document.createElement("input");
        inp.type = "text";
        inp.inputMode = "decimal";
        inp.id = "p-" + meta.code + "-" + p.key;
        label.appendChild(inp);
      }
      grid.appendChild(label);
    });

    function addTextField(id, text, readonly) {
      var label = document.createElement("label");
      if (readonly) label.className = "readonly";
      label.appendChild(document.createTextNode(text));
      var inp = document.createElement("input");
      inp.type = "text";
      inp.inputMode = "decimal";
      inp.id = id;
      if (readonly) inp.readOnly = true;
      label.appendChild(inp);
      grid.appendChild(label);
    }

    function addIncludeField(id, text) {
      var label = document.createElement("label");
      label.appendChild(document.createTextNode(text));
      var sel = document.createElement("select");
      sel.id = id;
      sel.innerHTML = "<option value='ON'>ON</option><option value='OFF'>OFF</option>";
      label.appendChild(sel);
      grid.appendChild(label);
    }

    addTextField("v-" + meta.code, headers.voucher || "凭证直接核定金额(元,优先)", false);
    addIncludeField("i-" + meta.code, headers.include || "计入?(承保过滤)");
    addTextField("o-" + meta.code, headers.loss || "核定损失(元,自动)", true);
    addTextField("q-" + meta.code, headers.covered || "计入金额(元,自动)", true);

    card.appendChild(head);
    card.appendChild(grid);
    return card;
  }

  function bindInputs(root) {
    root.querySelectorAll("input, select").forEach(function (el) {
      if (el.readOnly) return;
      if (el.id && el.id.indexOf("mod-") === 0) return;
      if (el.id === "case-type") return;
      el.addEventListener("input", scheduleCompute);
      el.addEventListener("change", scheduleCompute);
    });
  }

  /* ---------- Collect / compute ---------- */
  function collectCase() {
    var catalog = state.catalog;
    var items = {};
    catalog.items.forEach(function (meta) {
      var params = {};
      (meta.params || []).forEach(function (p) {
        var el = document.getElementById("p-" + meta.code + "-" + p.key);
        if (!el) return;
        params[p.key] = el.value;
      });
      var voucherEl = document.getElementById("v-" + meta.code);
      var includeEl = document.getElementById("i-" + meta.code);
      var entry = {
        params: params,
        voucher: voucherEl ? voucherEl.value : "",
        include: includeEl ? includeEl.value : "ON",
      };
      if (state.includeOverrides[meta.code]) entry.include_override = true;
      if (meta.formula_type === "r1_confirm") entry.legal_confirm = params.p2;
      items[meta.code] = entry;
    });

    var categories = {};
    catalog.categories.forEach(function (cat) {
      var selected = !!state.selectedModules[cat.code];
      var el = document.getElementById("csw-" + cat.code);
      var sw = selected ? (el ? el.value : "ON") : "OFF";
      categories[cat.code] = { switch: sw };
    });

    var out = {
      schema_version: "1.0",
      case_id: document.getElementById("case-id").value,
      case_name: document.getElementById("case-name").value,
      calc_date: document.getElementById("calc-date").value,
      policy_id: state.policyId || null,
      coverage_mode: state.policyId ? state.coverageMode : "manual",
      policy_flags: state.policyFlags,
      s1_method: document.getElementById("s1-method").value,
      sla_compensation: document.getElementById("sla").value,
      categories: categories,
      items: items,
    };
    if (state.narrative) out.narrative = state.narrative;
    return out;
  }

  function scheduleCompute() {
    if (state.view !== 2 && state.view !== 3) return;
    setStatus("核算中…");
    if (state.timer) clearTimeout(state.timer);
    state.timer = setTimeout(function () {
      runCompute(false);
    }, 280);
  }

  function runCompute(force) {
    var caseData = collectCase();
    state.caseData = caseData;
    return api("/api/compute", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(caseData),
    })
      .then(function (result) {
        state.result = result;
        renderLiveResult(result);
        if (force || state.view === 3) renderReport();
        setStatus("已更新");
        return result;
      })
      .catch(function (err) {
        setStatus("核算失败（已保持上次结果）");
        showWarnings(["请求失败：" + (err && err.message ? err.message : err)]);
      });
  }

  function renderLiveResult(result) {
    showWarnings(result.warnings || (result.error ? [result.error] : []));
    var byCode = {};
    (result.items || []).forEach(function (it) {
      byCode[it.code] = it;
    });
    Object.keys(byCode).forEach(function (code) {
      var it = byCode[code];
      var o = document.getElementById("o-" + code);
      var q = document.getElementById("q-" + code);
      if (o) o.value = money(it.assessed_loss);
      if (q) q.value = money(it.covered_amount);
      var card = document.getElementById("item-" + code);
      if (card) card.classList.toggle("off", it.include !== "ON");
    });
    (result.categories || []).forEach(function (cat) {
      var meta = document.getElementById("cat-meta-" + cat.code);
      if (meta) {
        meta.textContent =
          "核定小计 " +
          money(cat.assessed_subtotal) +
          " · 计入 " +
          money(cat.covered_subtotal) +
          " · 已填 " +
          cat.filled_count;
      }
    });
    var s = result.summary || {};
    setText("net-pill", "净核定损失：" + money(s.net_assessed_loss));
  }

  /* ---------- Report ---------- */
  function renderReport() {
    var result = state.result;
    var caseData = state.caseData || collectCase();
    if (!result) return;
    var s = result.summary || {};
    var t = currentCaseType();

    setText("rpt-case-id", caseData.case_id || "—");
    setText("rpt-case-name", caseData.case_name || "—");
    setText("rpt-calc-date", caseData.calc_date || "—");
    setText("rpt-case-type", t.name);
    setText(
      "rpt-modules",
      selectedModuleList()
        .map(function (c) {
          return c.code + " " + c.name;
        })
        .join("；") || "（未选择）"
    );

    setText("rpt-net", money(s.net_assessed_loss));
    setText("rpt-covered", money(s.covered_total));
    setText("rpt-sla", money(s.sla_deduction));
    setText("rpt-indirect", money(s.indirect_subtotal));
    setText("rpt-direct", money(s.direct_subtotal));
    setText("rpt-fact", money(s.fact_total));
    setText("rpt-fact-kpi", money(s.fact_total));
    setText("rpt-policy", (result.policy && result.policy.name) || "（未指定保单）");
    renderSettlement(result);

    setText("rpt-s1-method", caseData.s1_method || "—");
    setText("rpt-sla-input", money(caseData.sla_compensation) + " 元");
    setText("rpt-key-params", buildKeyParamsSummary(result, caseData));

    var tbody = document.querySelector("#rpt-module-table tbody");
    tbody.innerHTML = "";
    (result.categories || []).forEach(function (cat) {
      if (!state.selectedModules[cat.code] && cat.covered_subtotal === 0 && cat.assessed_subtotal === 0) {
        return;
      }
      if (!state.selectedModules[cat.code]) return;
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        escapeHtml(cat.code) +
        "</td><td>" +
        escapeHtml(cat.name) +
        "</td><td class='text-end'>" +
        money(cat.assessed_subtotal) +
        "</td><td class='text-end'>" +
        money(cat.covered_subtotal) +
        "</td><td class='text-end'>" +
        cat.filled_count +
        "</td>";
      tbody.appendChild(tr);
    });
  }

  function renderSettlement(result) {
    var stl = result.settlement || {};
    var section = document.getElementById("rpt-settlement-section");
    var stepsBody = document.querySelector("#rpt-steps-table tbody");
    var subBody = document.querySelector("#rpt-sublimit-table tbody");
    var policyBox = document.getElementById("rpt-policy-box");
    var biBox = document.getElementById("rpt-bi-box");
    var blockedBox = document.getElementById("rpt-blocked-box");

    if (!stl.applied) {
      section.classList.add("d-none");
      setText("rpt-payable", "—");
      setText("rpt-payable-sub", "未指定保单，结算层未启用");
      return;
    }
    section.classList.remove("d-none");
    setText("rpt-payable", money(stl.payable));
    setText(
      "rpt-payable-sub",
      "赔付率 " + (stl.payout_ratio_vs_fact * 100).toFixed(1) + "% · 自留 " +
        money(stl.self_retention) + " 元"
    );

    var p = result.policy || {};
    var html =
      "<div class='policy-name'>" + escapeHtml(stl.policy_name || "") + "</div>" +
      "<div class='policy-sum'>承保人 " + escapeHtml(stl.insurer || "—") +
      " · 累计限额 " + money(stl.aggregate_limit) + " 元" +
      " · 免赔额 " + money(stl.deductible_amount) + " 元（" + escapeHtml(stl.deductible_scope) + "）" +
      " · 条款来源 " + escapeHtml(p.source_file || "—") + "</div>";
    if (p.parameters_are_assumed) {
      html +=
        "<div class='policy-warn'>限额与免赔额为演示用假设值，条款原文表述为" +
        "「由投保人与保险人协商确定」。</div>";
    }
    (stl.conditional_notes || []).forEach(function (n) {
      html += "<div class='policy-note'>已触发条件条款 — " + escapeHtml(n) + "</div>";
    });
    policyBox.innerHTML = html;

    stepsBody.innerHTML = "";
    (stl.steps || []).forEach(function (st) {
      var d = Number(st.delta || 0);
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + escapeHtml(st.step) + "</td>" +
        "<td class='text-end'>" + money(st.amount) + "</td>" +
        "<td class='text-end " + (d < 0 ? "delta-cut" : "") + "'>" +
        (Math.abs(d) < 0.005 ? "—" : money(d)) + "</td>" +
        "<td class='small text-secondary'>" + escapeHtml(st.note || "") + "</td>";
      stepsBody.appendChild(tr);
    });

    subBody.innerHTML = "";
    var rows = (stl.sublimits || []).filter(function (r) { return r.before > 0; });
    if (!rows.length) {
      subBody.innerHTML = "<tr><td colspan='6' class='text-secondary'>本案没有科目落入分项限额组。</td></tr>";
    }
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      if (r.cut > 0) tr.className = "row-cut";
      tr.innerHTML =
        "<td>" + escapeHtml(r.name || r.id) +
        (r.shares_aggregate ? "" : " <span class='cov-chip cov-warn'>不占用累计限额</span>") + "</td>" +
        "<td class='small text-secondary'>" + escapeHtml(r.clause || "—") + "</td>" +
        "<td class='text-end'>" + money(r.limit) + "</td>" +
        "<td class='text-end'>" + money(r.before) + "</td>" +
        "<td class='text-end'>" + money(r.after) + "</td>" +
        "<td class='text-end delta-cut'>" + (r.cut > 0 ? money(r.cut) : "—") + "</td>";
      subBody.appendChild(tr);
    });

    var bi = stl.bi || {};
    if (bi.gross > 0) {
      biBox.innerHTML =
        "<h3>营业中断口径拆解</h3>" +
        "<table class='table report-table'><tbody>" +
        "<tr><th>中断毛损失（未扣等待期）</th><td class='text-end'>" + money(bi.gross) + "</td></tr>" +
        "<tr><th>等待期自留额</th><td class='text-end'>" + money(bi.waiting_retention) + "</td></tr>" +
        "<tr><th>约定免赔额</th><td class='text-end'>" + money(bi.deductible) + "</td></tr>" +
        "<tr><th>实际自留（口径：" + escapeHtml(bi.mode) + "）</th><td class='text-end'>" +
        money(bi.retention_applied) + "</td></tr>" +
        "<tr><th>SLA 抵扣</th><td class='text-end'>" + money(bi.sla_deduction) + "</td></tr>" +
        "<tr><th>可赔基数</th><td class='text-end'><strong>" + money(bi.base) + "</strong></td></tr>" +
        "</tbody></table>" +
        "<p class='report-note'>等待期自留额与约定免赔额按保单口径处理，" +
        "不会在 S1 公式已扣等待期的基础上再扣一次免赔额。</p>";
    } else {
      biBox.innerHTML = "";
    }

    var blocked = (result.items || []).filter(function (it) {
      return it.assessed_loss > 0 && !it.effective_covered;
    });
    if (blocked.length) {
      var h =
        "<h3>已核定但不予赔付的科目</h3>" +
        "<table class='table report-table'><thead><tr><th>编号</th><th>科目</th>" +
        "<th class='text-end'>核定损失</th><th>原因</th></tr></thead><tbody>";
      blocked.forEach(function (it) {
        h +=
          "<tr><td>" + escapeHtml(it.code) + "</td><td>" + escapeHtml(it.name) + "</td>" +
          "<td class='text-end'>" + money(it.assessed_loss) + "</td>" +
          "<td class='small'>" + escapeHtml(it.coverage_label || "本案未纳入该损失模块") +
          (it.coverage_clause ? "（" + escapeHtml(it.coverage_clause) + "）" : "") +
          (it.coverage_note ? "：" + escapeHtml(it.coverage_note) : "") + "</td></tr>";
      });
      h += "</tbody></table>";
      blockedBox.innerHTML = h;
    } else {
      blockedBox.innerHTML = "";
    }
  }

  function buildKeyParamsSummary(result, caseData) {
    var parts = [];
    var by = {};
    (result.items || []).forEach(function (it) {
      by[it.code] = it;
    });
    var highlights = ["F1-01", "F3-01", "F6-02", "S1-01", "S1-03", "S3-01", "S2-05"];
    highlights.forEach(function (code) {
      var it = by[code];
      if (!it) return;
      if (!state.selectedModules[it.category]) return;
      if (!(it.assessed_loss > 0)) return;
      parts.push(code + " 核定 " + money(it.assessed_loss) + " 元");
    });
    if (!parts.length) return "所选模块暂无已填有效科目，或金额均为 0。";
    return parts.join("；");
  }

  /* ---------- Policy ---------- */
  function buildPolicySelect() {
    var sel = document.getElementById("policy-select");
    sel.innerHTML = "";
    var none = document.createElement("option");
    none.value = "";
    none.textContent = "（不指定保单 · 只算事实口径）";
    sel.appendChild(none);
    state.policies.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      sel.appendChild(opt);
    });
    sel.value = state.policyId || "";
    sel.addEventListener("change", function () {
      setPolicy(sel.value);
    });

    var modeSel = document.getElementById("coverage-mode");
    modeSel.value = state.coverageMode;
    modeSel.addEventListener("change", function () {
      state.coverageMode = modeSel.value;
      if (state.coverageMode === "policy" && state.policyDetail) {
        applyCoverageToForm(state.policyDetail);
      }
      renderCoverageBadges();
      scheduleCompute();
    });
  }

  function setPolicy(id) {
    state.policyId = id || "";
    state.policyFlags = {};
    var info = document.getElementById("policy-info");
    var flagsBox = document.getElementById("policy-flags");
    if (!state.policyId) {
      state.policyDetail = null;
      info.classList.add("d-none");
      flagsBox.classList.add("d-none");
      renderCoverageBadges();
      scheduleCompute();
      return Promise.resolve(null);
    }
    return api("/api/policies/" + encodeURIComponent(state.policyId)).then(function (p) {
      state.policyDetail = p;
      renderPolicyInfo(p);
      renderPolicyFlags(p);
      if (state.coverageMode === "policy") applyCoverageToForm(p);
      renderCoverageBadges();
      scheduleCompute();
      return p;
    });
  }

  function renderPolicyInfo(p) {
    var box = document.getElementById("policy-info");
    var st = p.settlement || {};
    var stats = p.coverage_stats || {};
    var chips = Object.keys(COVERAGE_BADGE)
      .filter(function (k) { return stats[k]; })
      .map(function (k) {
        return "<span class='cov-chip " + COVERAGE_BADGE[k].cls + "'>" +
          COVERAGE_BADGE[k].text + " " + stats[k] + "</span>";
      })
      .join("");
    var bi = st.bi || {};
    var ded = st.deductible || {};
    var html =
      "<div class='policy-name'>" + escapeHtml(p.name) + "</div>" +
      "<div class='policy-sum'>" + escapeHtml(p.summary || "") + "</div>" +
      "<div class='cov-chips'>" + chips + "</div>" +
      "<table class='policy-table'><tbody>" +
      "<tr><th>累计赔偿限额</th><td>" + money(st.aggregate_limit) + " 元</td>" +
      "<th>免赔额</th><td>" + money(ded.amount) + " 元（" + escapeHtml(ded.scope || "") + "）</td></tr>" +
      "<tr><th>营业中断口径</th><td>" + escapeHtml(bi.deductible_mode || "—") + "</td>" +
      "<th>赔偿期上限</th><td>" + (bi.max_indemnity_days ? bi.max_indemnity_days + " 天" : "—") + "</td></tr>" +
      "<tr><th>条款依据</th><td colspan='3'>" + escapeHtml(bi.clause || "—") + "</td></tr>" +
      "<tr><th>条款来源</th><td colspan='3'>" + escapeHtml(p.source_file || "—") + "</td></tr>" +
      "</tbody></table>";
    if (p.parameters_are_assumed) {
      html +=
        "<div class='policy-warn'>限额与免赔额为演示用假设值——条款原文对这些数值的表述为" +
        "「由投保人与保险人协商确定」，无公开数字。引用时必须标明该假设。</div>";
    }
    (p.settlement_notes || []).forEach(function (n) {
      html += "<div class='policy-note'>" + escapeHtml(n) + "</div>";
    });
    box.innerHTML = html;
    box.classList.remove("d-none");
  }

  function renderPolicyFlags(p) {
    var box = document.getElementById("policy-flags");
    var conds = ((p.settlement || {}).conditional_deductible) || [];
    if (!conds.length) {
      box.classList.add("d-none");
      box.innerHTML = "";
      return;
    }
    var html = "<div class='flags-title'>本保单的条件性免赔条款（按案情勾选）</div>";
    conds.forEach(function (c) {
      html +=
        "<label class='form-check'><input class='form-check-input' type='checkbox' " +
        "data-flag='" + escapeHtml(c.flag) + "' /><span class='form-check-label'>" +
        escapeHtml(c.desc || c.flag) + "</span></label>";
    });
    box.innerHTML = html;
    box.classList.remove("d-none");
    box.querySelectorAll("input[data-flag]").forEach(function (el) {
      el.addEventListener("change", function () {
        state.policyFlags[el.getAttribute("data-flag")] = el.checked;
        scheduleCompute();
      });
    });
  }

  /**
   * 按保单条款映射刷新各科目的「计入」开关。
   *
   * state.includeOverrides 里的科目是案例显式声明要偏离条款判定的
   * （如模块化产品中未投保的模块），必须跳过，否则案例的核心设计会被抹掉。
   */
  function applyCoverageToForm(p) {
    var map = p.coverage_map || {};
    Object.keys(map).forEach(function (code) {
      if (state.includeOverrides[code]) return;
      var el = document.getElementById("i-" + code);
      if (el) el.value = map[code].include;
    });
  }

  function renderCoverageBadges() {
    var map = (state.policyDetail && state.policyDetail.coverage_map) || null;
    (state.catalog ? state.catalog.items : []).forEach(function (meta) {
      var card = document.getElementById("item-" + meta.code);
      if (!card) return;
      var old = card.querySelector(".cov-badge");
      if (old) old.parentNode.removeChild(old);
      if (!map || !map[meta.code]) return;
      var cov = map[meta.code];
      var badge = COVERAGE_BADGE[cov.status] || COVERAGE_BADGE.unmapped;
      var span = document.createElement("span");
      span.className = "cov-badge " + badge.cls;
      span.textContent = badge.text;
      if (cov.clause || cov.note) {
        span.title = (cov.clause ? cov.clause + "\n" : "") + (cov.note || "");
      }
      var title = card.querySelector(".item-title");
      if (title) title.appendChild(span);
    });
    // 保单模式下「计入」由条款映射决定，但允许人工覆盖（如模块化产品未投保的模块）。
    // 一旦人工改动，记入 includeOverrides，之后不再被条款映射刷掉，
    // 提交时带上 include_override 标记，引擎会在 warnings 里留痕。
    (state.catalog ? state.catalog.items : []).forEach(function (meta) {
      var el = document.getElementById("i-" + meta.code);
      if (!el || el.dataset.ovBound) return;
      el.dataset.ovBound = "1";
      el.addEventListener("change", function () {
        if (!state.policyId || state.coverageMode !== "policy") return;
        var cov = (state.policyDetail && state.policyDetail.coverage_map) || {};
        var expected = cov[meta.code] ? cov[meta.code].include : null;
        if (expected && el.value !== expected) {
          state.includeOverrides[meta.code] = true;
        } else {
          delete state.includeOverrides[meta.code];
        }
        scheduleCompute();
      });
    });
  }

  /* ---------- Import / export / case library ---------- */
  function downloadBlob(filename, text, mime) {
    var blob = new Blob([text], { type: (mime || "application/json") + ";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  function slugify(text) {
    var t = String(text || "").trim().replace(/[^A-Za-z0-9_\-]+/g, "-").replace(/^-+|-+$/g, "");
    return t || "case";
  }

  function exportCase() {
    var caseData = collectCase();
    var name = slugify(caseData.case_id || caseData.case_name || "case");
    downloadBlob(name + ".json", JSON.stringify(caseData, null, 2));
    setStatus("案例 JSON 已导出");
  }

  function importCaseFile(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var data;
      try {
        data = JSON.parse(String(reader.result));
      } catch (e) {
        showWarnings(["案例文件不是合法 JSON：" + e.message]);
        return;
      }
      api("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(data),
      }).then(function (res) {
        if (res.issues && res.issues.length) {
          showWarnings(["案例校验提示：" + res.issues.join("；")]);
        } else {
          showWarnings([]);
        }
        loadCaseObject(data);
      });
    };
    reader.readAsText(file, "utf-8");
  }

  function loadCaseObject(data) {
    state.narrative = data.narrative || null;
    state.policyFlags = data.policy_flags || {};
    state.coverageMode = data.coverage_mode || (data.policy_id ? "policy" : "manual");
    document.getElementById("coverage-mode").value = state.coverageMode;
    state.includeOverrides = {};
    Object.keys(data.items || {}).forEach(function (code) {
      if ((data.items[code] || {}).include_override) {
        state.includeOverrides[code] = true;
      }
    });
    applyCaseToForm(data, true);
    applyModulesFromCase(data);
    var sel = document.getElementById("policy-select");
    if (sel) sel.value = data.policy_id || "";
    return setPolicy(data.policy_id || "").then(function () {
      if (state.coverageMode === "manual") applyIncludesFromCase(data);
      Object.keys(state.policyFlags).forEach(function (k) {
        var el = document.querySelector("#policy-flags input[data-flag='" + k + "']");
        if (el) el.checked = !!state.policyFlags[k];
      });
      showView(1);
      setStatus("案例已载入：" + (data.case_name || data.case_id || ""));
    });
  }

  function applyIncludesFromCase(caseData) {
    (state.catalog.items || []).forEach(function (meta) {
      var entry = (caseData.items && caseData.items[meta.code]) || {};
      var el = document.getElementById("i-" + meta.code);
      if (el && entry.include) el.value = entry.include;
    });
  }

  function applyModulesFromCase(caseData) {
    state.caseTypeId = "custom";
    var sel = document.getElementById("case-type");
    if (sel) sel.value = "custom";
    state.catalog.categories.forEach(function (cat) {
      var sw = (caseData.categories && caseData.categories[cat.code]) || {};
      var on = sw.switch ? sw.switch === "ON" : false;
      state.selectedModules[cat.code] = on;
      var box = document.getElementById("mod-" + cat.code);
      if (box) box.checked = on;
      var csw = document.getElementById("csw-" + cat.code);
      if (csw) csw.value = on ? "ON" : "OFF";
    });
  }

  function refreshCaseList() {
    var box = document.getElementById("cases-list");
    box.textContent = "加载中…";
    return api("/api/cases").then(function (res) {
      var list = res.cases || [];
      if (!list.length) {
        box.innerHTML = "<div class='text-secondary'>案例库为空。填好案件后点右上「保存当前案件」。</div>";
        return;
      }
      box.innerHTML = "";
      list.forEach(function (c) {
        var row = document.createElement("div");
        row.className = "case-row";
        row.innerHTML =
          "<div class='case-meta'><strong>" + escapeHtml(c.case_name || c.name) + "</strong>" +
          "<span class='case-sub'>" + escapeHtml(c.name) +
          (c.policy_id ? " · " + escapeHtml(c.policy_id) : "") + "</span></div>";
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-sm btn-outline-primary";
        btn.textContent = "载入";
        btn.addEventListener("click", function () {
          api("/api/cases/" + encodeURIComponent(c.name)).then(function (data) {
            loadCaseObject(data).then(function () {
              document.getElementById("cases-panel").classList.add("d-none");
            });
          });
        });
        row.appendChild(btn);
        box.appendChild(row);
      });
    });
  }

  function saveCurrentCase() {
    var nameEl = document.getElementById("case-save-name");
    var caseData = collectCase();
    var name = slugify(nameEl.value || caseData.case_id || caseData.case_name);
    api("/api/cases/" + encodeURIComponent(name), {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ case: caseData, minimize: true }),
    })
      .then(function (res) {
        setStatus("已保存：" + res.saved + ".json");
        if (res.issues && res.issues.length) showWarnings(res.issues);
        else showWarnings([]);
        refreshCaseList();
      })
      .catch(function (err) {
        showWarnings(["保存失败：" + (err && err.message ? err.message : err)]);
      });
  }

  function exportMarkdown() {
    var caseData = collectCase();
    api("/api/export/markdown", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(caseData),
    }).then(function (res) {
      var name = slugify(caseData.case_id || caseData.case_name || "case");
      downloadBlob(name + ".md", res.markdown, "text/markdown");
      setStatus("Markdown 报告已导出");
    });
  }

  /* ---------- Apply case / demo ---------- */
  function fillCaseMeta(caseData) {
    document.getElementById("case-id").value = valOrEmpty(caseData.case_id);
    document.getElementById("case-name").value = valOrEmpty(caseData.case_name);
    document.getElementById("calc-date").value = valOrEmpty(caseData.calc_date);
    document.getElementById("s1-method").value =
      valOrEmpty(caseData.s1_method) || "公式外推法";
    document.getElementById("sla").value = valOrEmpty(caseData.sla_compensation);
  }

  /**
   * 把案例填进表单。
   *
   * strictItems 为 true 时（载入已保存的案例），案例中未声明的科目一律留空，
   * 不回落到 catalog 的演示默认值。否则一个写明「未支付赎金」的案例
   * 会凭空多出 80 万核定损失，而且从界面上完全看不出来。
   * 演示案（/api/demo）提交全部 69 项，走 strictItems=false 保持原行为。
   */
  function applyCaseToForm(caseData, strictItems) {
    fillCaseMeta(caseData);
    var catalog = state.catalog;
    var declared = caseData.items || {};
    catalog.categories.forEach(function (cat) {
      var sw = (caseData.categories && caseData.categories[cat.code]) || {};
      var el = document.getElementById("csw-" + cat.code);
      if (el) el.value = sw.switch || cat.switch_default || "ON";
    });
    catalog.items.forEach(function (meta) {
      var has = Object.prototype.hasOwnProperty.call(declared, meta.code);
      var entry = declared[meta.code] || {};
      var params = entry.params || {};
      (meta.params || []).forEach(function (p) {
        var el = document.getElementById("p-" + meta.code + "-" + p.key);
        if (!el) return;
        var v = params[p.key];
        if (v === null || v === undefined) {
          v = strictItems && !has ? "" : p.default;
        }
        el.value = valOrEmpty(v);
      });
      var voucherEl = document.getElementById("v-" + meta.code);
      if (voucherEl) voucherEl.value = valOrEmpty(entry.voucher);
      var includeEl = document.getElementById("i-" + meta.code);
      if (includeEl) includeEl.value = entry.include || meta.include_default || "ON";
    });
  }

  function applyDemoModulesFromCase(caseData) {
    state.caseTypeId = "ransomware";
    document.getElementById("case-type").value = "ransomware";
    applyCaseTypePreset(true);
    // keep demo category switches that are ON with filled items
    state.catalog.categories.forEach(function (cat) {
      var sw = (caseData.categories && caseData.categories[cat.code]) || {};
      if (sw.switch === "OFF") {
        state.selectedModules[cat.code] = false;
        var box = document.getElementById("mod-" + cat.code);
        if (box) box.checked = false;
      }
    });
  }

  /* ---------- Tips ---------- */
  function bindTips() {
    document.querySelectorAll(".tip-btn[data-tip]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var key = btn.getAttribute("data-tip");
        var text = TIPS[key] || "";
        var layer = document.getElementById("tip-layer");
        layer.textContent = text;
        layer.className = "popover-panel";
        layer.style.position = "fixed";
        var rect = btn.getBoundingClientRect();
        layer.style.left = Math.min(rect.left, window.innerWidth - 320) + "px";
        layer.style.top = rect.bottom + 8 + "px";
        layer.classList.remove("d-none");
      });
    });

    var tipBtn = document.getElementById("s1-tip-btn");
    var tipPop = document.getElementById("s1-popover");
    if (tipBtn && tipPop) {
      tipBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        tipPop.classList.toggle("d-none");
        tipBtn.setAttribute(
          "aria-expanded",
          tipPop.classList.contains("d-none") ? "false" : "true"
        );
      });
    }

    document.addEventListener("click", function () {
      var tipPop = document.getElementById("s1-popover");
      if (tipPop) {
        tipPop.classList.add("d-none");
        var tipBtn = document.getElementById("s1-tip-btn");
        if (tipBtn) tipBtn.setAttribute("aria-expanded", "false");
      }
      var layer = document.getElementById("tip-layer");
      if (layer) {
        layer.classList.add("d-none");
        layer.classList.remove("popover-panel");
      }
    });
  }

  /* ---------- Boot ---------- */
  function boot() {
    setStatus("加载中…");
    buildCaseTypeSelect();
    bindTips();

    document.getElementById("btn-next-1").addEventListener("click", function () {
      if (!selectedModuleList().length) {
        showWarnings(["请至少选择一个损失模块"]);
        return;
      }
      showWarnings([]);
      showView(2);
    });
    document.getElementById("btn-prev-2").addEventListener("click", function () {
      showView(1);
    });
    document.getElementById("btn-next-2").addEventListener("click", function () {
      showView(3);
    });
    document.getElementById("btn-prev-3").addEventListener("click", function () {
      showView(2);
    });
    document.getElementById("btn-print").addEventListener("click", function () {
      window.print();
    });
    document.getElementById("btn-export-md").addEventListener("click", exportMarkdown);
    document.getElementById("btn-export").addEventListener("click", exportCase);
    document.getElementById("btn-import").addEventListener("click", function () {
      document.getElementById("import-file").click();
    });
    document.getElementById("import-file").addEventListener("change", function (e) {
      var f = e.target.files && e.target.files[0];
      if (f) importCaseFile(f);
      e.target.value = "";
    });
    document.getElementById("btn-cases").addEventListener("click", function () {
      var panel = document.getElementById("cases-panel");
      panel.classList.toggle("d-none");
      if (!panel.classList.contains("d-none")) refreshCaseList();
    });
    document.getElementById("btn-case-save").addEventListener("click", saveCurrentCase);
    document.getElementById("btn-modules-all").addEventListener("click", function () {
      state.catalog.categories.forEach(function (cat) {
        state.selectedModules[cat.code] = true;
        var box = document.getElementById("mod-" + cat.code);
        if (box) box.checked = true;
        var sw = document.getElementById("csw-" + cat.code);
        if (sw) sw.value = "ON";
      });
      state.caseTypeId = "custom";
      document.getElementById("case-type").value = "custom";
    });
    document.getElementById("btn-modules-none").addEventListener("click", function () {
      state.catalog.categories.forEach(function (cat) {
        state.selectedModules[cat.code] = false;
        var box = document.getElementById("mod-" + cat.code);
        if (box) box.checked = false;
        var sw = document.getElementById("csw-" + cat.code);
        if (sw) sw.value = "OFF";
      });
      state.caseTypeId = "custom";
      document.getElementById("case-type").value = "custom";
    });
    document.getElementById("btn-help").addEventListener("click", function () {
      document.getElementById("help-panel").classList.toggle("d-none");
    });
    document.getElementById("btn-demo").addEventListener("click", function () {
      api("/api/demo").then(function (demo) {
        state.narrative = null;
        state.includeOverrides = {};
        applyCaseToForm(demo, false);
        applyDemoModulesFromCase(demo);
        renderCoverageBadges();
        showView(1);
        setStatus("演示案已加载");
      });
    });

    Promise.all([api("/api/catalog"), api("/api/demo"), api("/api/policies")])
      .then(function (triple) {
        state.catalog = triple[0];
        state.policies = (triple[2] || {}).policies || [];
        buildShell();
        buildModulePicker();
        buildPolicySelect();
        applyCaseTypePreset(true);
        applyCaseToForm(triple[1], false);
        applyDemoModulesFromCase(triple[1]);
        showView(1);
        setStatus("演示案已加载（未指定保单，可在「投保产品」中选择）");
      })
      .catch(function (err) {
        setStatus("启动失败");
        showWarnings(["无法加载：" + (err && err.message ? err.message : err)]);
      });
  }

  boot();
})();
