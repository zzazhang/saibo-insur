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

    return {
      case_id: document.getElementById("case-id").value,
      case_name: document.getElementById("case-name").value,
      calc_date: document.getElementById("calc-date").value,
      s1_method: document.getElementById("s1-method").value,
      sla_compensation: document.getElementById("sla").value,
      categories: categories,
      items: items,
    };
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

  /* ---------- Apply case / demo ---------- */
  function fillCaseMeta(caseData) {
    document.getElementById("case-id").value = valOrEmpty(caseData.case_id);
    document.getElementById("case-name").value = valOrEmpty(caseData.case_name);
    document.getElementById("calc-date").value = valOrEmpty(caseData.calc_date);
    document.getElementById("s1-method").value =
      valOrEmpty(caseData.s1_method) || "公式外推法";
    document.getElementById("sla").value = valOrEmpty(caseData.sla_compensation);
  }

  function applyCaseToForm(caseData) {
    fillCaseMeta(caseData);
    var catalog = state.catalog;
    catalog.categories.forEach(function (cat) {
      var sw = (caseData.categories && caseData.categories[cat.code]) || {};
      var el = document.getElementById("csw-" + cat.code);
      if (el) el.value = sw.switch || cat.switch_default || "ON";
    });
    catalog.items.forEach(function (meta) {
      var entry = (caseData.items && caseData.items[meta.code]) || {};
      var params = entry.params || {};
      (meta.params || []).forEach(function (p) {
        var el = document.getElementById("p-" + meta.code + "-" + p.key);
        if (!el) return;
        var v = params[p.key];
        if (v === null || v === undefined) v = p.default;
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
        applyCaseToForm(demo);
        applyDemoModulesFromCase(demo);
        showView(1);
        setStatus("演示案已加载");
      });
    });

    Promise.all([api("/api/catalog"), api("/api/demo")])
      .then(function (pair) {
        state.catalog = pair[0];
        buildShell();
        buildModulePicker();
        applyCaseTypePreset(true);
        applyCaseToForm(pair[1]);
        applyDemoModulesFromCase(pair[1]);
        showView(1);
        setStatus("演示案已加载");
      })
      .catch(function (err) {
        setStatus("启动失败");
        showWarnings(["无法加载：" + (err && err.message ? err.message : err)]);
      });
  }

  boot();
})();
