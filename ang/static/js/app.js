/* Autonomous Network Guardian - dashboard client.
   Every page polls its JSON endpoint on the monitoring cadence and re-renders. */
(function () {
  "use strict";

  const POLL_MS = 4000;
  const page = document.body.dataset.page;

  // ---- helpers ----------------------------------------------------------
  async function api(path, opts) {
    const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw Object.assign(new Error(body.error || res.statusText), { body, status: res.status });
    return body;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function clock(iso) {
    if (!iso) return "--:--:--";
    const d = new Date(iso);
    if (isNaN(d)) return String(iso).slice(11, 19) || "--:--:--";
    return d.toLocaleTimeString([], { hour12: false });
  }

  function statusChip(status) {
    const map = {
      online: ["st-up", "Online"], offline: ["st-down", "Offline"],
      degraded: ["st-warn", "Degraded"], unknown: ["st-res", "Unknown"],
      open: ["st-down", "Open"], resolved: ["st-res", "Resolved"],
    };
    const [cls, label] = map[status] || ["st-res", status || "-"];
    return `<span class="st ${cls}">${esc(label)}</span>`;
  }

  function priorityChip(prio) {
    const cls = { Critical: "st-down", High: "st-warn", Medium: "st-warn", Low: "st-up", None: "st-up" }[prio] || "st-warn";
    return `<span class="st ${cls}">Priority ${esc(prio)}</span>`;
  }

  function flash(msg, isErr) {
    const el = document.getElementById("flash");
    if (!el) return;
    el.innerHTML = `<div class="flash${isErr ? " err" : ""}">${esc(msg)}</div>`;
    clearTimeout(flash._t);
    flash._t = setTimeout(() => { el.innerHTML = ""; }, 4000);
  }

  function set(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  // ---- header (all pages) --------------------------------------------
  let currentMode = null;

  async function refreshHeader() {
    try {
      const m = await api("/api/monitoring");
      const p = m.provider || {};
      currentMode = p.mode || "simulation";
      set("cycle-meta", `every ${m.cycle_seconds}s &middot; ` +
        (m.last_cycle_at ? `last ${clock(m.last_cycle_at)}` : "starting&hellip;"));
      const label = p.mode === "live" ? "Live monitoring" : (p.scenario_label || "-");
      const lab = document.getElementById("scenario-label");
      if (lab) lab.textContent = label;
      set("scenario-note", esc(p.mode === "live" ? "Real ICMP / socket probes" : (p.scenario_note || "")));
      const simBtn = document.getElementById("btn-mode-sim");
      const liveBtn = document.getElementById("btn-mode-live");
      if (simBtn && liveBtn) {
        simBtn.className = currentMode === "simulation" ? "btn btn-primary" : "btn btn-secondary";
        liveBtn.className = currentMode === "live" ? "btn btn-primary" : "btn btn-secondary";
      }
      set("mode-note", currentMode === "live"
        ? "Probing real devices with ICMP ping / sockets on your network."
        : "Using built-in sample scenarios, not your real network.");
    } catch (e) { /* header stays as-is */ }
  }

  async function setMode(mode) {
    try {
      await api("/api/monitoring/mode", { method: "POST", body: JSON.stringify({ mode }) });
      flash(mode === "live" ? "Switched to live network monitoring" : "Switched to simulation mode");
    } catch (e) { flash(e.message, true); }
    await refreshHeader();
  }

  // ---- dashboard ------------------------------------------------------
  // ---- dashboard & visual topology -------------------------------------
  let selectedNodeId = null;
  let cachedTopologyData = null;

  function renderHealth(h) {
    const factors = (h.factors || []).map((f) =>
      `<div class="kv"><span>${esc(f.name)}${f.note ? ` &mdash; ${esc(f.note)}` : ""}</span>` +
      `<span class="mono">${f.points} / ${f.max}</span></div>`).join("");
    
    const score = Number(h.score) || 0;
    const scoreColor = score >= 80 ? "#10b981" : (score >= 40 ? "#f59e0b" : "#ef4444");

    set("health-body",
      `<div style="display:flex;align-items:flex-end;gap:10px">
         <div class="bignum" style="font-size:82px;color:${scoreColor}">${h.score}</div>
         <div style="padding-bottom:10px">
           <div class="mono" style="color:var(--color-neutral-600)">/ 100</div>
           <div style="font-family:var(--font-heading);font-size:20px;letter-spacing:.08em;text-transform:uppercase;color:${scoreColor}">${esc(h.status)}</div>
         </div>
       </div>
       <div class="meter"><i style="width:${h.score}%;background:${scoreColor}"></i></div>
       <div style="display:flex;flex-direction:column;gap:4px;margin-top:6px">${factors}</div>` +
      ((h.reasons && h.reasons.length)
        ? `<div class="text-muted" style="font-size:11px;margin-top:6px">${esc(h.reasons.join(" · "))}</div>` : ""));
  }

  function renderDiagSummary(d) {
    set("diag-prio", priorityChip(d.priority));
    const isHealthy = d.priority === "None" || d.rule_name === "healthy" || !d.root_cause || d.root_cause === "Healthy network";
    const affected = (d.affected || []).map((a) => `<span class="devchip off" style="padding:2px 6px;font-size:10px;height:auto;display:inline-block">${esc(a.name)}</span>`).join(" ") || "—";
    const evidence = (d.evidence || []).map((e) =>
      `<div class="evidence"><span class="tick">✓</span><span>${esc(e.text)}</span>` +
      `<span class="spacer"></span><span class="mono" style="color:var(--color-neutral-600)">${esc(e.score)}</span></div>`).join("");

    if (isHealthy) {
      set("diag-body",
        `<div style="padding:10px 0;display:flex;align-items:center;gap:14px;">
           <div style="font-size:32px;color:#10b981;line-height:1;">✓</div>
           <div>
             <div style="font-family:var(--font-heading);font-weight:600;font-size:22px;color:#065f46;">All Systems Operational</div>
             <div class="text-muted" style="font-size:13px;margin-top:2px;">No root-cause faults or dependency bottlenecks detected across the monitored subnet.</div>
           </div>
         </div>`);
    } else {
      set("diag-body",
        `<div style="display:grid;grid-template-columns:minmax(0,1fr) 200px;gap:20px;align-items:start">
           <div>
             <div style="display:inline-block;background:#fee2e2;color:#991b1b;padding:2px 8px;font-size:10px;font-weight:700;border-radius:2px;margin-bottom:6px;letter-spacing:.05em;">
               ROOT CAUSE IDENTIFIED
             </div>
             <div style="font-family:var(--font-heading);font-weight:600;font-size:28px;line-height:1.1;color:#111827;">${esc(d.root_cause)}</div>
             <div class="text-muted" style="font-size:13px;margin-top:8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
               <span>Affected devices:</span> ${affected}
             </div>
             <div style="display:flex;flex-direction:column;gap:5px;margin-top:12px">${evidence}</div>
           </div>
           <div style="border-left:1px solid var(--color-divider);padding-left:16px">
             <div class="lbl">Confidence</div>
             <div class="bignum" style="font-size:44px;color:var(--color-accent);">${d.confidence}%</div>
             <div class="meter" style="height:6px;margin-top:6px"><i style="width:${d.confidence}%"></i></div>
             <div class="text-muted" style="font-size:11px;margin-top:8px">Deterministic DAG rule match with full upstream verification.</div>
           </div>
         </div>`);
    }
  }

  function renderVisualTopology(containerId, topData, isMini) {
    const el = document.getElementById(containerId);
    if (!el) return;

    cachedTopologyData = topData;
    const graph = topData.graph || {};
    const nodes = graph.nodes || [];
    const links = graph.links || [];

    if (!nodes.length) {
      // Fallback for older legacy schema
      const clients = (topData.clients || []).map((c) =>
        `<div class="node ${c.status === "offline" ? "off" : ""}" style="font-size:11px;padding:6px 0">${esc(c.name)}</div>`).join("");
      el.innerHTML = `
        <div class="topo">
          <div class="clients">${clients}</div>
          <div class="drop"></div>
          <div class="node ${topData.gateway && topData.gateway.ok ? "" : "off"}">Gateway ${topData.gateway && topData.gateway.ok ? "✓" : "✗"}</div>
          <div class="drop"></div>
          <div class="node ${topData.internet && topData.internet.ok ? "" : "off"}" style="border-style:dashed">Internet ${topData.internet && topData.internet.ok ? "✓" : "✗"}</div>
        </div>
        <div class="text-muted" style="font-size:11px;margin-top:8px">${esc(topData.note || "")}</div>`;
      return;
    }

    const width = isMini ? 290 : 800;
    const height = isMini ? 220 : 460;

    const tier0 = nodes.filter((n) => n.tier === 0);
    const tier1 = nodes.filter((n) => n.tier === 1);
    const tier2 = nodes.filter((n) => n.tier === 2);

    const pos = {};

    // Tier 0 (top: WAN & DNS)
    const y0 = isMini ? 30 : 60;
    const t0Count = tier0.length || 1;
    tier0.forEach((n, idx) => {
      pos[n.id] = { x: (width / (t0Count + 1)) * (idx + 1), y: y0, node: n };
    });

    // Tier 1 (center: Gateway)
    const y1 = isMini ? 105 : 190;
    const t1Count = tier1.length || 1;
    tier1.forEach((n, idx) => {
      pos[n.id] = { x: (width / (t1Count + 1)) * (idx + 1), y: y1, node: n };
    });

    // Tier 2 (bottom: Clients & Services)
    const y2 = isMini ? 180 : 365;
    const t2Count = tier2.length || 1;
    tier2.forEach((n, idx) => {
      pos[n.id] = { x: (width / (t2Count + 1)) * (idx + 1), y: y2, node: n };
    });

    let svgHtml = `<svg class="topo-svg" width="100%" height="${height}" viewBox="0 0 ${width} ${height}" style="display:block;">
      <defs>
        <marker id="arrow-ok" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10b981" />
        </marker>
        <marker id="arrow-broken" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#ef4444" />
        </marker>
      </defs>`;

    // Connector Lines
    links.forEach((l) => {
      const src = pos[l.source];
      const tgt = pos[l.target];
      if (src && tgt) {
        const isOk = l.ok !== false;
        const strokeColor = isOk ? "#5980a6" : "#ef4444";
        const strokeDash = isOk ? "" : 'stroke-dasharray="4 3"';
        const marker = isOk ? "url(#arrow-ok)" : "url(#arrow-broken)";
        svgHtml += `<line class="svg-link ${isOk ? 'active' : 'broken'}" 
          x1="${src.x}" y1="${src.y - (isMini ? 14 : 22)}" 
          x2="${tgt.x}" y2="${tgt.y + (isMini ? 14 : 22)}" 
          stroke="${strokeColor}" stroke-width="${isMini ? 1.5 : 2}" ${strokeDash} />`;
      }
    });

    // Node Cards
    const boxW = isMini ? 68 : 115;
    const boxH = isMini ? 28 : 50;

    nodes.forEach((n) => {
      const p = pos[n.id];
      if (!p) return;
      const x = p.x - boxW / 2;
      const y = p.y - boxH / 2;

      const isUp = (n.status === "online" || n.status === "degraded");
      const isRc = n.is_root_cause;
      const isAff = n.is_affected;
      const isSel = (n.id === selectedNodeId);

      let borderColor = isUp ? "#5980a6" : "#2b2b2d";
      let bgColor = isUp ? "#ffffff" : "#f1f5f9";
      let badgeHtml = "";

      if (isRc) {
        borderColor = "#ef4444";
        bgColor = "#fef2f2";
        badgeHtml = `<text x="${p.x}" y="${y - 4}" text-anchor="middle" font-size="${isMini ? '7' : '9'}" font-weight="700" fill="#ef4444">ROOT CAUSE</text>`;
      } else if (isAff) {
        borderColor = "#f59e0b";
        bgColor = "#fffbeb";
        badgeHtml = `<text x="${p.x}" y="${y - 4}" text-anchor="middle" font-size="${isMini ? '7' : '9'}" font-weight="600" fill="#f59e0b">IMPACTED</text>`;
      }

      let extraCls = isRc ? "root-cause" : (isAff ? "blast-radius" : "");
      if (isSel) extraCls += " selected";

      let icon = "💻";
      if (n.role === "Gateway" || n.type === "Router") icon = "🛡️";
      else if (n.role === "DNS" || n.type === "Service") icon = "🔍";
      else if (n.role === "External" || n.type === "Cloud") icon = "🌐";
      else if (n.type === "Server") icon = "🖧";
      else if (n.type === "Printer") icon = "🖨️";

      svgHtml += `
        <g class="svg-node ${extraCls}" data-id="${esc(n.id)}" style="cursor:pointer">
          ${badgeHtml}
          <rect x="${x}" y="${y}" width="${boxW}" height="${boxH}" rx="4" ry="4" 
            fill="${bgColor}" stroke="${borderColor}" stroke-width="${isSel ? '2.5' : (isRc ? '2.5' : '1.5')}" />
          <text x="${p.x}" y="${y + (isMini ? 12 : 18)}" text-anchor="middle" font-family="var(--font-heading)" font-size="${isMini ? '9' : '12'}" font-weight="600" fill="#1d1f20">
            ${isMini ? '' : icon + ' '}${esc(n.name)}
          </text>
          <text x="${p.x}" y="${y + (isMini ? 22 : 36)}" text-anchor="middle" font-family="monospace" font-size="${isMini ? '8' : '10'}" fill="#5d5d60">
            ${esc(n.ip_address || '')}
          </text>
        </g>
      `;
    });

    svgHtml += `</svg>`;

    if (isMini) {
      el.innerHTML = `
        <div class="mini-topo-wrap">${svgHtml}</div>
        <div class="text-muted" style="font-size:11px;margin-top:6px">${esc(topData.note || "")}</div>
      `;
    } else {
      el.innerHTML = svgHtml;
    }

    // Interactive Click Handler
    el.querySelectorAll(".svg-node").forEach((nodeEl) => {
      nodeEl.addEventListener("click", () => {
        const nid = nodeEl.dataset.id;
        selectedNodeId = nid;
        renderVisualTopology(containerId, topData, isMini);
        if (!isMini) {
          updateInspector(nid);
        }
      });
    });
  }

  function updateInspector(nodeId) {
    const insp = document.getElementById("topo-inspector-body");
    if (!insp || !cachedTopologyData) return;

    const graph = cachedTopologyData.graph || {};
    const nodes = graph.nodes || [];
    const node = nodes.find((n) => n.id === nodeId);

    if (!node) {
      insp.innerHTML = `<div class="text-muted" style="padding:16px 0;font-size:13px;text-align:center;">Select any node on the graph.</div>`;
      return;
    }

    const dependents = [];
    if (node.role === "Gateway" || node.type === "Router") {
      nodes.filter((n) => n.tier === 2).forEach((n) => dependents.push(n.name));
    } else {
      const links = graph.links || [];
      links.filter((l) => l.target === node.id).forEach((l) => {
        const child = nodes.find((n) => n.id === l.source);
        if (child) dependents.push(child.name);
      });
    }

    let bannerHtml = "";
    if (node.is_root_cause) {
      bannerHtml = `
        <div class="inspector-banner-rc">
          <strong style="color:#b91c1c;font-size:13px;">🚨 PRIMARY ROOT CAUSE</strong>
          <p style="margin:4px 0 0;font-size:12px;color:#7f1d1d;">
            ANG's correlation engine isolated this node as the primary failure point.
          </p>
        </div>
      `;
    } else if (node.is_affected) {
      bannerHtml = `
        <div class="inspector-banner-br">
          <strong style="color:#b45309;font-size:13px;">⚠️ IMPACTED IN BLAST RADIUS</strong>
          <p style="margin:4px 0 0;font-size:12px;color:#78350f;">
            Collateral failure caused by upstream dependency outage.
          </p>
        </div>
      `;
    }

    let statusCls = node.status === "online" ? "st-up" : (node.status === "degraded" ? "st-warn" : "st-down");

    insp.innerHTML = `
      ${bannerHtml}
      <div style="font-family:var(--font-heading);font-weight:600;font-size:22px;margin-bottom:8px;color:#1d1f20;">
        ${esc(node.name)}
      </div>
      <div class="inspector-prop"><span class="text-muted">Node ID</span><span class="mono">${esc(node.id)}</span></div>
      <div class="inspector-prop"><span class="text-muted">IP Address</span><span class="mono">${esc(node.ip_address || "—")}</span></div>
      <div class="inspector-prop"><span class="text-muted">Device Type</span><span>${esc(node.type || "Device")}</span></div>
      <div class="inspector-prop"><span class="text-muted">Network Role</span><span>${esc(node.role || "Client")}</span></div>
      <div class="inspector-prop"><span class="text-muted">Live Status</span><span class="st ${statusCls}">${esc(node.status)}</span></div>
      <div class="inspector-prop"><span class="text-muted">Round-trip Latency</span><span class="mono">${node.latency_ms != null ? node.latency_ms + " ms" : "—"}</span></div>
      <div class="inspector-prop"><span class="text-muted">Packet Loss</span><span class="mono">${node.packet_loss_pct != null ? node.packet_loss_pct + "%" : "—"}</span></div>
      
      <div style="margin-top:14px;padding-top:10px;border-top:1px solid var(--color-divider);">
        <div class="lbl">Downstream Blast Radius</div>
        <div style="font-size:13px;font-weight:600;margin-top:2px;">
          ${dependents.length ? `${dependents.length} dependent devices affected` : "Leaf node (No downstream dependents)"}
        </div>
        ${dependents.length ? `<div class="text-muted" style="font-size:11px;margin-top:4px;">Affected: ${esc(dependents.join(", "))}</div>` : ""}
      </div>
    `;
  }

  function renderTopology(t) {
    renderVisualTopology("topology", t, true);
  }

  function renderActiveIncidents(list, lastRecovery) {
    if (!list || !list.length) {
      set("active-incidents",
        `<div class="text-muted" style="font-size:13px;padding:10px 2px">No active incidents.` +
        (lastRecovery ? ` The last closed incident recovered in ${esc(lastRecovery)}.` : "") + `</div>`);
      return;
    }
    const rows = list.map((i) =>
      `<tr>
         <td class="mono">${esc(i.code)}</td>
         <td>${esc(i.root_cause)}</td>
         <td>${priorityChip(i.priority)}</td>
         <td class="mono">${esc((i.affected || []).join(", "))}</td>
         <td class="mono">${clock(i.started_at)}</td>
         <td>${statusChip(i.status)}</td>
         <td style="text-align:right"><a class="btn btn-ghost" href="/incidents/${i.id}">Open</a></td>
       </tr>`).join("");
    set("active-incidents",
      `<div class="table-wrap"><table class="table">
        <thead><tr><th>ID</th><th>Root cause</th><th>Priority</th><th>Affected</th><th>Started</th><th>Status</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div>`);
  }

  function renderEvents(events) {
    set("recent-events", (events || []).map((e) =>
      `<div style="display:flex;gap:10px;padding:6px 0;border-bottom:1px dotted var(--color-divider);font-size:12px">
         <span class="mono" style="color:var(--color-neutral-600)">${clock(e.t)}</span><span>${esc(e.text)}</span>
       </div>`).join(""));
  }

  async function renderDashboard() {
    const d = await api("/api/dashboard");
    renderHealth(d.health);
    renderDiagSummary(d.diagnosis);
    renderShared(d.shared_dependencies);
    renderDevicesMini(d.devices);
    renderTopology(d.topology);
    renderActiveIncidents(d.active_incidents, d.last_recovery);
    renderEvents(d.recent_events);
  }

  // ---- devices ------------------------------------------------------
  let depOptions = [];
  let suggestedDevice = { name: "", ip_address: "", device_type: "Computer", role: "Client", depends_on: null };

  async function renderDevices() {
    const d = await api("/api/devices");
    depOptions = d.dependency_options || [];
    if (d.suggested) suggestedDevice = d.suggested;
    const byId = {};
    depOptions.forEach((o) => { byId[o.id] = o.name; });
    set("devices-sub", `${d.online} of ${d.total} online &middot; measurements from the latest monitoring cycle`);
    set("devices-tbody", d.devices.map((x) =>
      `<tr>
         <td style="font-family:var(--font-heading);font-size:16px;letter-spacing:.04em">${esc(x.name)}</td>
         <td class="mono">${esc(x.ip_address)}</td>
         <td>${esc(x.device_type)}</td>
         <td>${esc(x.role)}</td>
         <td class="mono">${esc(x.depends_on ? byId[x.depends_on] || "#" + x.depends_on : "—")}</td>
         <td>${statusChip(x.status)}</td>
         <td class="mono">${x.latency_ms == null ? "—" : x.latency_ms + " ms"}${x.latency_class ? ` <span class="text-muted">(${x.latency_class})</span>` : ""}</td>
         <td class="mono">${x.packet_loss_pct == null ? "—" : x.packet_loss_pct + "%"}</td>
         <td class="mono" style="color:var(--color-neutral-600)">${x.last_checked ? clock(x.last_checked) : "—"}</td>
         <td style="text-align:right"><button class="btn btn-ghost btn-del-device" data-id="${x.id}" title="Remove device">&times;</button></td>
       </tr>`).join(""));

    document.querySelectorAll(".btn-del-device").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Remove this device? Its measurement history will also be deleted.")) return;
        btn.disabled = true;
        try {
          await api(`/api/devices/${btn.dataset.id}`, { method: "DELETE" });
          flash("Device removed");
          renderDevices();
        } catch (e) { flash(e.message, true); btn.disabled = false; }
      });
    });
  }

  // ---- Wi-Fi / LAN discovery -----------------------------------------
  async function runScan() {
    const btn = document.getElementById("btn-scan");
    btn.disabled = true;
    set("scan-results", `<div class="text-muted" style="font-size:13px;padding:8px 2px">Scanning your network for live devices&hellip; this can take a few seconds.</div>`);
    try {
      const d = await api("/api/devices/discover");
      renderScanResults(d);
    } catch (e) {
      set("scan-results", `<div class="text-muted" style="font-size:13px;padding:8px 2px">Scan failed: ${esc(e.message)}</div>`);
    }
    btn.disabled = false;
  }

  function renderScanResults(d) {
    const net = d.network || {};
    const header = `<div class="text-muted" style="font-size:12px;margin-bottom:6px">
        This machine: <span class="mono">${esc(net.local_ip || "?")}</span> &middot;
        Gateway/router: <span class="mono">${esc(net.gateway_ip || "unknown")}</span> &middot;
        Scanned <span class="mono">${esc(net.scanned_cidr || "?")}</span>
        ${net.note ? ` &middot; ${esc(net.note)}` : ""}
      </div>`;

    if (!d.discovered || !d.discovered.length) {
      set("scan-results", `<div class="card blueprint" style="padding:16px">${header}
        <div class="text-muted" style="font-size:13px">No live hosts answered. Make sure the other 2-3 devices are on and connected to the same Wi-Fi, then scan again.</div></div>`);
      return;
    }

    const rows = d.discovered.map((h) => `
      <div class="row" style="justify-content:space-between;padding:6px 0;border-bottom:1px dotted var(--color-divider)">
        <div>
          <span class="mono">${esc(h.ip)}</span>
          ${h.is_gateway ? `<span class="st st-warn" style="margin-left:6px">Router</span>` : ""}
          ${h.is_self ? `<span class="st st-up" style="margin-left:6px">This machine</span>` : ""}
          <div class="text-muted" style="font-size:12px">${esc(h.hostname || h.mac || "no hostname")}</div>
        </div>
        ${h.already_registered
          ? `<span class="text-muted" style="font-size:12px">already registered</span>`
          : `<button class="btn btn-ghost btn-add-host" data-ip="${esc(h.ip)}" data-name="${esc(h.suggested_name)}"
               data-type="${esc(h.suggested_type)}" data-role="${esc(h.suggested_role)}">Add</button>`}
      </div>`).join("");

    set("scan-results", `<div class="card blueprint" style="padding:16px">
        <i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
        ${header}${rows}
      </div>`);

    document.querySelectorAll(".btn-add-host").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Adding…";
        const gw = depOptions.find((o) => o.role === "Gateway");
        const payload = {
          name: btn.dataset.name, ip_address: btn.dataset.ip,
          device_type: btn.dataset.type, role: btn.dataset.role,
        };
        if (payload.role === "Client" && gw) payload.depends_on = gw.id;
        try {
          await api("/api/devices", { method: "POST", body: JSON.stringify(payload) });
          flash(`Registered ${payload.name} (${payload.ip_address})`);
          btn.closest(".row").outerHTML = `<div class="text-muted" style="font-size:12px;padding:6px 0">Added ${esc(payload.name)}.</div>`;
          renderDevices();
        } catch (e) {
          btn.disabled = false;
          btn.textContent = "Add";
          flash((e.body && e.body.errors && e.body.errors.join(", ")) || e.message, true);
        }
      });
    });
  }

  function openRegisterDialog() {
    const s = suggestedDevice || {};
    const opt = (o, sel) => `<option value="${o}" ${sel === o ? "selected" : ""}>${esc(o)}</option>`;
    const depOpts = depOptions.map((o) =>
      `<option value="${o.id}" ${s.depends_on === o.id ? "selected" : ""}>${esc(o.name)} &mdash; ${esc(o.ip_address)} (${esc(o.role)})</option>`).join("");
    const root = document.getElementById("dialog-root");
    root.innerHTML =
      `<div class="dialog-backdrop" id="dlg-back">
        <div class="dialog blueprint" style="width:min(460px,100%);background:var(--color-bg);padding:22px">
          <i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
          <div class="card-kicker">Device management</div>
          <div class="dialog-title">Register device</div>
          <div id="dlg-errors"></div>
          <div class="text-muted" style="font-size:12px">Pre-filled with the next free name and address &mdash; edit as needed.</div>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
            <div class="field" style="grid-column:span 2"><label>Device name</label>
              <input class="input" id="f-name" value="${esc(s.name || "")}" placeholder="e.g. PC-04"></div>
            <div class="field"><label>IP address</label>
              <input class="input" id="f-ip" value="${esc(s.ip_address || "")}" placeholder="e.g. 192.168.1.13"></div>
            <div class="field"><label>Device type</label>
              <select class="input" id="f-type">${["Computer", "Router", "Server", "Printer"].map((o) => opt(o, s.device_type || "Computer")).join("")}</select>
            </div>
            <div class="field" style="grid-column:span 2"><label>Network role</label>
              <select class="input" id="f-role">${["Client", "Gateway", "Service", "Peripheral"].map((o) => opt(o, s.role || "Client")).join("")}</select>
            </div>
            <div class="field" style="grid-column:span 2"><label>Depends on (shared dependency)</label>
              <select class="input" id="f-dep"><option value="">None</option>${depOpts}</select>
            </div>
          </div>
          <div class="dialog-body text-muted" style="font-size:12px">
            The dependency link is what lets the diagnosis engine collapse several device symptoms into one shared root cause.
          </div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" id="dlg-cancel">Cancel</button>
            <button class="btn btn-primary" id="dlg-save">Save device</button>
          </div>
        </div>
      </div>`;
    const close = () => { root.innerHTML = ""; };
    document.getElementById("dlg-back").addEventListener("click", (e) => { if (e.target.id === "dlg-back") close(); });
    document.getElementById("dlg-cancel").addEventListener("click", close);
    const showErrors = (errs) => set("dlg-errors",
      `<div style="border-left:3px solid var(--color-neutral-900);background:var(--color-neutral-200);padding:8px 12px;font-size:12px">
         Could not save:<br>${errs.map(esc).join("<br>")}</div>`);

    document.getElementById("dlg-save").addEventListener("click", async () => {
      const payload = {
        name: document.getElementById("f-name").value.trim(),
        ip_address: document.getElementById("f-ip").value.trim(),
        device_type: document.getElementById("f-type").value,
        role: document.getElementById("f-role").value,
      };
      const dep = document.getElementById("f-dep").value;
      if (dep) payload.depends_on = Number(dep);

      const local = [];
      if (!payload.name) local.push("name is required");
      if (!payload.ip_address) local.push("IP address is required");
      if (local.length) { showErrors(local); return; }

      const btn = document.getElementById("dlg-save");
      btn.disabled = true;
      try {
        const created = await api("/api/devices", { method: "POST", body: JSON.stringify(payload) });
        close();
        flash(`Registered ${created.name}`);
        renderDevices();
      } catch (err) {
        btn.disabled = false;
        showErrors((err.body && err.body.errors) || [err.message]);
      }
    });
  }

  // ---- diagnosis ---------------------------------------------------
  async function renderDiagnosisPage() {
    const d = await api("/api/diagnosis");
    set("rootcause-body",
      `<div style="font-family:var(--font-heading);font-weight:600;font-size:40px;line-height:1.02">${esc(d.root_cause)}</div>
       <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:6px">
         ${priorityChip(d.priority)}
         <span class="st st-warn">Confidence ${d.confidence}%</span>
         <span class="mono" style="color:var(--color-neutral-600)">rule: ${esc(d.rule_name)}</span>
       </div>
       <p class="text-muted" style="font-size:13px;margin:8px 0 0">${esc(d.reasoning)}</p>`);

    set("evidence-body",
      (d.evidence || []).map((e) =>
        `<div style="display:flex;gap:10px;align-items:baseline;padding:8px 0;border-bottom:1px solid var(--color-divider)">
           <span class="tick">✓</span>
           <div style="flex:1"><div style="font-size:14px">${esc(e.text)}</div>
             <div class="mono" style="color:var(--color-neutral-600)">${esc(e.detail)}</div></div>
           <span class="mono">${esc(e.score)}</span>
         </div>`).join("") +
      `<div style="display:flex;justify-content:flex-end;gap:10px;font-family:var(--font-heading);text-transform:uppercase;margin-top:8px">
         Total <span class="mono">${d.confidence}</span></div>`);

    const hyps = d.hypotheses || [];
    const max = Math.max(1, ...hyps.map((h) => h.score));
    set("hypotheses-body", hyps.map((h, i) =>
      `<div class="hyp-row">
         <span class="nm">${esc(h.label)}</span>
         <div class="hyp-bar ${i === 0 && h.score > 0 ? "top" : ""}"><i style="width:${Math.round(h.score / max * 100)}%"></i></div>
         <span class="mono sc">${h.score}</span>
       </div>`).join(""));

    set("affected-body", (d.affected && d.affected.length)
      ? d.affected.map((a) =>
        `<div class="row" style="justify-content:space-between;padding:6px 0;border-bottom:1px dotted var(--color-divider)">
           <span style="font-family:var(--font-heading);font-size:16px">${esc(a.name)}</span>
           <span class="mono" style="color:var(--color-neutral-600)">${esc(a.reason)}</span>
         </div>`).join("")
      : `<div class="text-muted" style="font-size:13px">No devices currently affected.</div>`);

    set("actions-body", (d.actions || []).map((a, i) =>
      `<div style="display:flex;gap:10px;font-size:14px;align-items:baseline">
         <span class="mono" style="color:var(--color-accent-700)">${i + 1}.</span><span>${esc(a)}</span>
       </div>`).join(""));
  }

  // ---- incidents --------------------------------------------------
  async function renderIncidents() {
    const d = await api("/api/incidents");
    if (!d.incidents.length) {
      set("incidents-tbody", `<tr><td colspan="9" class="text-muted" style="padding:12px 2px">No incidents recorded yet. Trigger a scenario on the Simulation page.</td></tr>`);
      return;
    }
    set("incidents-tbody", d.incidents.map((i) =>
      `<tr>
         <td class="mono">${esc(i.code)}</td>
         <td>${esc(i.root_cause)}</td>
         <td>${priorityChip(i.priority)}</td>
         <td>${statusChip(i.status)}</td>
         <td class="mono">${esc((i.affected || []).join(", ") || "—")}</td>
         <td class="mono">${clock(i.started_at)}</td>
         <td class="mono">${i.resolved_at ? clock(i.resolved_at) : "—"}</td>
         <td class="mono">${esc(i.duration || (i.status === "open" ? "ongoing" : "—"))}</td>
         <td style="text-align:right"><a class="btn btn-ghost" href="/incidents/${i.id}">Timeline</a></td>
       </tr>`).join(""));
  }

  async function renderIncidentDetail() {
    const id = document.body.dataset.incidentId;
    let d;
    try { d = await api(`/api/incidents/${id}`); }
    catch (e) { set("detail-body", `<div class="text-muted">Incident not found.</div>`); return; }

    const field = (label, value) =>
      `<div><div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--color-neutral-600)">${label}</div>
       <div class="mono">${esc(value)}</div></div>`;

    set("detail-body",
      `<div class="row" style="gap:10px">
         <span class="mono">${esc(d.code)}</span>${statusChip(d.status)}${priorityChip(d.priority)}
       </div>
       <div style="font-family:var(--font-heading);font-weight:600;font-size:34px;line-height:1.05">${esc(d.root_cause)}</div>
       <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;border-top:1px solid var(--color-divider);border-bottom:1px solid var(--color-divider);padding:12px 0">
         ${field("Started", clock(d.started_at))}
         ${field("Recovered", d.resolved_at ? clock(d.resolved_at) : "—")}
         ${field("Duration", d.duration || "ongoing")}
         ${field("Confidence", d.confidence + "%")}
       </div>
       <div class="card-kicker">Affected devices</div>
       <div style="display:flex;gap:8px;flex-wrap:wrap">
         ${(d.affected_devices || []).map((x) => `<span class="st st-warn">${esc(x.name)}</span>`).join("") || "<span class='text-muted'>none</span>"}
       </div>`);

    const tl = d.timeline || [];
    set("detail-timeline", tl.map((t, i) =>
      `<div class="timeline-row ${i === tl.length - 1 ? "last" : ""}">
         <span class="mono t">${clock(t.timestamp)}</span>
         <div class="rail"><div class="dot"></div><div class="line"></div></div>
         <div class="tx"><span class="mono" style="color:var(--color-accent-700)">${esc(t.rule_name)}</span> &mdash; ${esc(t.evidence)}</div>
       </div>`).join("") || `<div class="text-muted" style="font-size:13px">No timeline events.</div>`);
  }

  // ---- simulation ------------------------------------------------
  async function renderSimulation() {
    const d = await api("/api/simulation");
    set("sim-grid", (d.scenarios || []).map((s) => {
      const active = s.key === d.active;
      return `<button class="card blueprint simcard ${active ? "active" : ""}" data-endpoint="${esc(s.endpoint)}">
                <i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
                <div class="row">
                  <span style="font-family:var(--font-heading);font-weight:600;font-size:19px;letter-spacing:.04em;text-transform:uppercase">${esc(s.label)}</span>
                  <span class="spacer"></span>
                  <span class="mono" style="font-size:11px;opacity:.7">${active ? "ACTIVE" : ""}</span>
                </div>
                <div style="font-size:13px;opacity:.8">${esc(s.note)}</div>
                <div class="mono" style="font-size:11px;opacity:.6">POST ${esc(s.endpoint)}</div>
              </button>`;
    }).join(""));
    document.querySelectorAll(".simcard").forEach((btn) => {
      btn.addEventListener("click", async () => {
        document.querySelectorAll(".simcard").forEach((b) => (b.disabled = true));
        try {
          const r = await api(btn.dataset.endpoint, { method: "POST" });
          flash(`Applied: ${r.state ? r.state.label : r.applied}`);
        } catch (e) { flash(e.message, true); }
        await Promise.all([refreshHeader(), renderSimulation()]);
      });
    });
  }

  // ---- topology page ------------------------------------------------
  async function renderTopologyPage() {
    const d = await api("/api/dashboard");
    const topData = d.topology || {};
    renderVisualTopology("topo-canvas-wrap", topData, false);
    const noteEl = document.getElementById("topo-summary-note");
    if (noteEl) {
      noteEl.textContent = topData.note || "Topology synchronized with active monitoring cycle.";
    }
    const loadEl = document.getElementById("topo-loading");
    if (loadEl) loadEl.style.display = "none";

    if (!selectedNodeId) {
      const graph = topData.graph || {};
      const rc = (graph.nodes || []).find((n) => n.is_root_cause);
      const gw = (graph.nodes || []).find((n) => n.role === "Gateway");
      if (rc) {
        selectedNodeId = rc.id;
      } else if (gw) {
        selectedNodeId = gw.id;
      }
    }
    if (selectedNodeId) {
      updateInspector(selectedNodeId);
    }
  }

  // ---- dispatch -----------------------------------------------------
  const RENDERERS = {
    dashboard: renderDashboard,
    topology: renderTopologyPage,
    devices: renderDevices,
    diagnosis: renderDiagnosisPage,
    incidents: renderIncidents,
    incident_detail: renderIncidentDetail,
    simulation: renderSimulation,
  };

  async function tick() {
    await refreshHeader();
    const r = RENDERERS[page];
    if (r) {
      try { await r(); }
      catch (e) {
        console.error(e);
        flash(`Could not load ${page}: ${e.message}`, true);
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (page === "topology") {
      document.querySelectorAll(".topo-quick-sc").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const action = btn.dataset.sc;
          try {
            await api(`/api/simulation/${action}`, { method: "POST" });
            flash(`Injected: ${btn.textContent.trim()}`);
          } catch (e) {
            flash(e.message, true);
          }
          await Promise.all([refreshHeader(), renderTopologyPage()]);
        });
      });
    }
    if (page === "devices") {
      const b = document.getElementById("btn-register");
      if (b) b.addEventListener("click", openRegisterDialog);
      const sc = document.getElementById("btn-scan");
      if (sc) sc.addEventListener("click", runScan);
      const ms = document.getElementById("btn-mode-sim");
      if (ms) ms.addEventListener("click", () => setMode("simulation"));
      const ml = document.getElementById("btn-mode-live");
      if (ml) ml.addEventListener("click", () => setMode("live"));
    }
    if (page === "simulation") {
      const rb = document.getElementById("btn-reset-data");
      if (rb) rb.addEventListener("click", async () => {
        rb.disabled = true;
        try { await api("/api/monitoring/reset-data", { method: "POST" }); flash("Demo data cleared"); }
        catch (e) { flash(e.message, true); }
        rb.disabled = false;
        await Promise.all([refreshHeader(), renderSimulation()]);
      });
    }
    tick();
    setInterval(tick, POLL_MS);
  });
})();
