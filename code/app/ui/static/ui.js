const DEFAULT_RULES = {
  allow_agent: true,
  allow_kpi: true,
  allow_sql: true,
  allow_schema: true,
  allow_definition: true,
  sql_limit: 500,
};

let activeRules = { ...DEFAULT_RULES };
let showTrace = false;

function getDateContext() {
  const start = document.getElementById("dash-start")?.value || "2017-01-01";
  const end = document.getElementById("dash-end")?.value || "2018-12-31";
  return { start_date: start, end_date: end };
}

async function callJson(url, method = "GET", payload) {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (payload !== undefined) {
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({ detail: "Invalid JSON response" }));
  if (!response.ok) {
    throw body;
  }
  return body;
}

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function formatInt(value) {
  const num = toNumber(value);
  if (num === null) return "-";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(num);
}

function formatMoney(value) {
  const num = toNumber(value);
  if (num === null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(num);
}

function formatPercent(value) {
  const num = toNumber(value);
  if (num === null) return "-";
  const ratio = num > 1 ? num / 100 : num;
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(ratio);
}

function renderRules() {
  document.getElementById("out-rules").textContent = JSON.stringify(activeRules, null, 2);
}

function renderTable(columns, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";

  const table = document.createElement("table");
  table.className = "chat-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  for (const row of rows.slice(0, 200)) {
    const tr = document.createElement("tr");
    for (const col of columns) {
      const td = document.createElement("td");
      const value = row?.[col];
      td.textContent = value === null || value === undefined ? "" : String(value);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }

  table.appendChild(thead);
  table.appendChild(tbody);
  wrapper.appendChild(table);
  return wrapper;
}

function renderFigure(block) {
  const points = block?.payload?.series;
  if (!Array.isArray(points) || points.length < 2) {
    return null;
  }

  const card = document.createElement("div");
  card.className = "figure-card";

  const title = document.createElement("p");
  title.className = "figure-title";
  title.textContent = block.title || "Figure";
  card.appendChild(title);

  const chart = document.createElement("div");
  chart.className = "mini-chart";

  const values = points.map((p) => toNumber(p.y) ?? 0);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const span = Math.max(maxV - minV, 1);

  for (const point of points.slice(0, 24)) {
    const col = document.createElement("div");
    col.className = "mini-col";

    const val = document.createElement("div");
    val.className = "mini-val";
    val.textContent = formatInt(point.y);

    const bar = document.createElement("div");
    bar.className = "mini-bar";
    bar.style.height = `${Math.max(8, Math.round(((toNumber(point.y) ?? 0) - minV) / span * 110))}px`;

    const label = document.createElement("div");
    label.className = "mini-label";
    label.textContent = String(point.x || "");

    col.appendChild(val);
    col.appendChild(bar);
    col.appendChild(label);
    chart.appendChild(col);
  }

  card.appendChild(chart);
  return card;
}

function appendMessage(role, text, blocks = [], trace = null) {
  const log = document.getElementById("chat-log");
  const row = document.createElement("div");
  row.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);

  if (role === "assistant" && Array.isArray(blocks)) {
    for (const block of blocks) {
      if (!block || typeof block !== "object") continue;

      if (block.type === "table") {
        const columns = block?.payload?.columns;
        const rows = block?.payload?.rows;
        if (Array.isArray(columns) && Array.isArray(rows)) {
          row.appendChild(renderTable(columns, rows));
        }
        continue;
      }

      if (block.type === "figure") {
        const figure = renderFigure(block);
        if (figure) row.appendChild(figure);
        continue;
      }

      if (block.type === "warnings") {
        const warnings = block?.payload?.warnings;
        const box = document.createElement("pre");
        box.textContent = Array.isArray(warnings) ? warnings.join("\n") : "Warning";
        row.appendChild(box);
        continue;
      }
    }
  }

  if (role === "assistant" && showTrace && trace) {
    const tracePre = document.createElement("pre");
    tracePre.textContent = JSON.stringify(trace, null, 2);
    row.appendChild(tracePre);
  }

  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

function resetChat() {
  const log = document.getElementById("chat-log");
  log.innerHTML = "";
  appendMessage("assistant", "Xin chào. Hỏi tự nhiên trước, rồi dùng /rule để giới hạn hành vi bot khi cần.");
}

function renderQuickCommands(commands) {
  const holder = document.getElementById("cmd-examples");
  holder.innerHTML = "";
  for (const cmd of commands || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cmd-chip secondary";
    btn.textContent = cmd.label || cmd.command;
    btn.onclick = () => {
      const input = document.getElementById("cmd-prompt");
      input.value = cmd.command || "";
      input.focus();
    };
    holder.appendChild(btn);
  }
}

async function sendPrompt(rawInput = null) {
  const inputEl = document.getElementById("cmd-prompt");
  const input = (rawInput ?? inputEl.value).trim();
  if (!input) return;

  appendMessage("user", input);
  inputEl.value = "";

  try {
    const data = await callJson("/ui/proxy/chat", "POST", {
      message: input,
      context: getDateContext(),
      rules: activeRules,
    });

    if (data.active_rules) {
      activeRules = { ...activeRules, ...data.active_rules };
      renderRules();
    }

    appendMessage("assistant", data.assistant_message || "Done.", data.blocks || [], data.trace || null);
  } catch (error) {
    appendMessage("assistant", error?.detail || "Unexpected error.");
  }
}

function renderKpiTiles(overview) {
  const o = overview || {};
  document.getElementById("kpi-total-orders").textContent = formatInt(o.total_orders);
  document.getElementById("kpi-delivered-rate").textContent = formatPercent(o.delivered_order_rate);
  document.getElementById("kpi-gmv").textContent = formatMoney(o.gmv);
  document.getElementById("kpi-aov").textContent = formatMoney(o.avg_order_value);
}

function renderTrend(series) {
  const root = document.getElementById("dash-trend");
  const note = document.getElementById("dash-trend-note");
  root.innerHTML = "";

  const rows = Array.isArray(series) ? series.slice(-12) : [];
  if (!rows.length) {
    note.textContent = "No trend data available.";
    return;
  }

  const points = rows.map((row) => ({
    month: String(row.month || "").slice(0, 7),
    gmv: toNumber(row.gmv) ?? 0,
  }));
  const maxValue = Math.max(...points.map((x) => x.gmv), 1);

  for (const point of points) {
    const col = document.createElement("div");
    col.className = "trend-col";

    const value = document.createElement("div");
    value.className = "trend-val";
    value.textContent = formatMoney(point.gmv);

    const bar = document.createElement("div");
    bar.className = "trend-bar";
    bar.style.height = `${Math.max(8, Math.round(point.gmv / maxValue * 150))}px`;

    const label = document.createElement("div");
    label.className = "trend-label";
    label.textContent = point.month;

    col.appendChild(value);
    col.appendChild(bar);
    col.appendChild(label);
    root.appendChild(col);
  }

  note.textContent = `Showing ${points.length} monthly points.`;
}

function renderTopCategories(rows, warnings) {
  const body = document.getElementById("dash-category-body");
  const note = document.getElementById("dash-category-note");
  body.innerHTML = "";

  const items = Array.isArray(rows) ? rows : [];
  if (!items.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 3;
    td.textContent = "No category data available.";
    tr.appendChild(td);
    body.appendChild(tr);
  } else {
    for (const row of items) {
      const tr = document.createElement("tr");
      const c = document.createElement("td");
      c.textContent = row.category_name_en || "-";
      const o = document.createElement("td");
      o.textContent = formatInt(row.total_orders);
      const r = document.createElement("td");
      r.textContent = formatMoney(row.total_revenue);
      tr.appendChild(c);
      tr.appendChild(o);
      tr.appendChild(r);
      body.appendChild(tr);
    }
  }

  note.textContent = Array.isArray(warnings) && warnings.length
    ? warnings.join(" | ")
    : "Category ranking is computed from serving marts.";
}

async function loadDashboard() {
  try {
    const data = await callJson("/ui/proxy/dashboard", "POST", {
      ...getDateContext(),
      top_categories_limit: 8,
    });
    renderKpiTiles(data.overview);
    renderTrend(data.series);
    renderTopCategories(data.top_categories, data.warnings);
  } catch (error) {
    renderKpiTiles({});
    renderTrend([]);
    renderTopCategories([], [error?.detail || "Dashboard data not ready"]);
  }
}

async function loadCapabilities() {
  try {
    const data = await callJson("/ui/proxy/capabilities");
    document.getElementById("capability-hint").textContent = data.description || "Capabilities loaded.";
    renderQuickCommands(data.quick_commands || []);
  } catch (_error) {
    document.getElementById("capability-hint").textContent = "Could not load capabilities.";
  }
}

async function checkReadiness() {
  try {
    await callJson("/health/readiness");
    document.getElementById("bootstrap-status").textContent = "Ready.";
  } catch (error) {
    document.getElementById("bootstrap-status").textContent = error?.detail || "Not ready";
  }
}

function bindEvents() {
  document.getElementById("btn-send").onclick = () => { void sendPrompt(); };
  document.getElementById("btn-help").onclick = () => { void sendPrompt("/help"); };
  document.getElementById("btn-rules").onclick = () => { void sendPrompt("/rules"); };
  document.getElementById("btn-clear").onclick = () => { resetChat(); };
  document.getElementById("btn-refresh-dashboard").onclick = () => {
    void loadDashboard();
    void checkReadiness();
  };

  document.getElementById("dash-start").addEventListener("change", () => {
    void loadDashboard();
  });
  document.getElementById("dash-end").addEventListener("change", () => {
    void loadDashboard();
  });

  document.getElementById("cmd-prompt").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      void sendPrompt();
    }
  });

  document.getElementById("toggle-debug").addEventListener("change", (event) => {
    showTrace = Boolean(event.target?.checked);
  });
}

function init() {
  bindEvents();
  renderRules();
  resetChat();
  void loadDashboard();
  void loadCapabilities();
  void checkReadiness();
}

document.addEventListener("DOMContentLoaded", init);
