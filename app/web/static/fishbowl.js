// THE FISHBOWL — lightweight vanilla JS (Packet 12, Part B/P).
// No framework, no build step. Each page calls one Fishbowl.initX() and gets
// periodic re-fetch + re-render of its own dynamic regions. Every fetch here
// hits a read-only /fishbowl/api/* endpoint — see app/web/api.py's module
// docstring for why that can never trigger an LLM or research call.

(function (global) {
  "use strict";

  const POLL_MS = 4000;

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtTime(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (e) {
      return iso;
    }
  }

  function fmtMoney(n) {
    if (n === null || n === undefined) return "$0.00";
    return "$" + Number(n).toFixed(4);
  }

  async function getJSON(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`${url} -> ${res.status}`);
    return res.json();
  }

  // Self-scheduling poll loop — never overlaps a slow request with the next tick.
  function poll(fn, ms) {
    let stopped = false;
    async function tick() {
      if (stopped) return;
      try {
        await fn();
      } catch (e) {
        console.error("[fishbowl] poll error", e);
      }
      if (!stopped) setTimeout(tick, ms);
    }
    tick();
    return () => {
      stopped = true;
    };
  }

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  // ---- Controls (Part K) --------------------------------------------------

  let controlBusy = false;

  function bindControls() {
    document.querySelectorAll("[data-control]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (controlBusy) return;
        const action = btn.getAttribute("data-control");
        const live = btn.getAttribute("data-live") === "true";
        let qsStr = "";
        if (action === "run-day" && live) {
          const ok = window.confirm(
            "RUN DAY is running against a LIVE provider (real Anthropic/Tavily calls). " +
              "This may incur real API usage. Continue?"
          );
          if (!ok) return;
          qsStr = "?confirmed=true";
        }
        controlBusy = true;
        document.querySelectorAll("[data-control]").forEach((b) => (b.disabled = true));
        const log = qs("#control-log");
        // RUN PERIOD/DAY can take real wall-clock time against a live
        // provider (each activation is a real Anthropic call). The request
        // itself does not block anything else — the dashboard/feed below
        // keep polling and updating live throughout — but a control-log
        // line that never changes can still read as "frozen" on its own,
        // so tick a visible elapsed-time counter for as long as this
        // control action is actually running (RUNNING vs COMPLETED vs
        // FAILED, made visually unambiguous without needing a refresh).
        const startedAt = Date.now();
        const tick = () => {
          if (log) {
            const secs = ((Date.now() - startedAt) / 1000).toFixed(0);
            log.textContent = `Running ${action}... (${secs}s elapsed — watch the feed and agent cards below, they're updating live)`;
          }
        };
        tick();
        const ticker = setInterval(tick, 1000);
        try {
          const res = await fetch(`/fishbowl/api/control/${action}${qsStr}`, { method: "POST" });
          const body = await res.json().catch(() => ({}));
          const secs = ((Date.now() - startedAt) / 1000).toFixed(1);
          if (log) {
            log.textContent = res.ok
              ? `[${action}] COMPLETED after ${secs}s — ${body.message || "done"}`
              : `[${action}] FAILED after ${secs}s — ${body.detail || res.status}`;
          }
        } catch (e) {
          if (log) log.textContent = `[${action}] FAILED — ${e}`;
        } finally {
          clearInterval(ticker);
          controlBusy = false;
          document.querySelectorAll("[data-control]").forEach((b) => (b.disabled = false));
          if (global.Fishbowl && global.Fishbowl._refresh) global.Fishbowl._refresh();
        }
      });
    });

    const founderForm = qs("#founder-message-form");
    if (founderForm) {
      founderForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        if (controlBusy) return;
        const content = qs("#founder-message-content", founderForm).value.trim();
        if (!content) return;
        const target = qs("#founder-message-target", founderForm).value || null;
        controlBusy = true;
        const log = qs("#control-log");
        try {
          const res = await fetch("/fishbowl/api/control/founder-message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content, target_agent_id: target }),
          });
          const body = await res.json().catch(() => ({}));
          if (log) log.textContent = res.ok ? `[founder-message] ${body.message}` : `[founder-message] failed`;
          if (res.ok) qs("#founder-message-content", founderForm).value = "";
        } finally {
          controlBusy = false;
        }
      });
    }
  }

  // ---- Dashboard ------------------------------------------------------------

  function renderDashboard(data) {
    if (!data) return;
    const c = data.clock;
    const p = data.providers;
    const header = qs("#dash-status");
    if (header) {
      header.innerHTML = `
        <span><span class="light ${c.is_paused ? "light--amber" : "light--green"}"></span>DAY ${c.day} — ${esc(c.period)}${c.is_paused ? " (PAUSED)" : ""}</span>
        <span class="sep">|</span>
        <span>LLM: ${esc(p.llm_provider)} <span class="badge ${p.llm_is_live ? "badge--live" : "badge--fixture"}">${p.llm_is_live ? "LIVE" : "FIXTURE"}</span></span>
        <span class="sep">|</span>
        <span>Research: ${esc(p.research_provider)} <span class="badge ${p.research_is_live ? "badge--live" : "badge--fixture"}">${p.research_is_live ? "LIVE" : "FIXTURE"}</span></span>
        <span class="sep">|</span>
        <span class="dim">models: ${esc(p.agent_model)} / ${esc(p.research_model)} / ${esc(p.report_model)}</span>
        <span class="sep">|</span>
        <span class="dim">last event: ${c.latest_event_at ? fmtTime(c.latest_event_at) : "—"}</span>
      `;
    }
    const runDayBtn = qs('[data-control="run-day"]');
    if (runDayBtn) runDayBtn.setAttribute("data-live", p.llm_is_live || p.research_is_live ? "true" : "false");

    const grid = qs("#agent-grid");
    if (grid) {
      grid.innerHTML = data.agents
        .map((a) => {
          const partners = a.conversation_partners.map((x) => esc(x.name)).join(", ");
          const interests = a.top_interests.map((i) => `<span class="chip">${esc(i)}</span>`).join("");
          return `
          <div class="agent-card" onclick="location.href='/fishbowl/agents/${esc(a.agent_id)}'">
            <div class="agent-card__name">${esc(a.name)} <span class="agent-card__status">${esc(a.status)}</span></div>
            <div class="agent-card__role">${esc(a.role)}</div>
            <dl>
              <dt>Location</dt><dd>${esc(a.current_location || "—")}</dd>
              <dt>Activity</dt><dd>${esc(a.current_activity || "—")}</dd>
              ${partners ? `<dt>With</dt><dd>${partners}</dd>` : ""}
              ${a.current_research_question ? `<dt>Researching</dt><dd>${esc(a.current_research_question)}</dd>` : ""}
              ${a.recent_memory ? `<dt>Recent memory</dt><dd>${esc(a.recent_memory).slice(0, 140)}</dd>` : ""}
              ${a.last_action_summary ? `<dt>Last action</dt><dd>${esc(a.last_action_summary).slice(0, 140)}</dd>` : ""}
            </dl>
            ${interests ? `<div style="margin-top:6px">${interests}</div>` : ""}
          </div>`;
        })
        .join("");
    }
  }

  async function refreshDashboard() {
    renderDashboard(await getJSON("/fishbowl/api/dashboard"));
  }

  function initDashboard() {
    bindControls();
    global.Fishbowl._refresh = refreshDashboard;
    poll(refreshDashboard, POLL_MS);
    initFeed();
  }

  // ---- Activity feed (Part D) -----------------------------------------------

  function renderFeed(data) {
    const list = qs("#feed-list");
    if (!list) return;
    if (!data.events.length) {
      list.innerHTML = '<li class="empty">Nothing yet.</li>';
      return;
    }
    list.innerHTML = data.events
      .map(
        (e) => `
      <li>
        <time>${fmtTime(e.created_at)}</time>
        <span class="cat">${esc(e.category)}</span>
        <span>${esc(e.headline)}</span>
      </li>`
      )
      .join("");
  }

  function initFeed() {
    const agentSel = qs("#feed-agent");
    const catSel = qs("#feed-category");
    const daySel = qs("#feed-day");
    async function refresh() {
      const params = new URLSearchParams();
      if (agentSel && agentSel.value) params.set("agent", agentSel.value);
      if (catSel && catSel.value) params.set("category", catSel.value);
      if (daySel && daySel.value) params.set("day", daySel.value);
      renderFeed(await getJSON("/fishbowl/api/events?" + params.toString()));
    }
    [agentSel, catSel, daySel].forEach((el) => {
      if (el) el.addEventListener("change", refresh);
    });
    poll(refresh, POLL_MS);
  }

  // ---- Agent detail -----------------------------------------------------

  function renderAgentDetail(a) {
    const el = qs("#agent-detail");
    if (!el || !a) return;
    const stateEl = qs("#agent-current-state");
    if (stateEl) {
      const partners = a.conversation_partners.map((x) => esc(x.name)).join(", ");
      stateEl.innerHTML = `
        <dt>Location</dt><dd>${esc(a.current_location || "—")}</dd>
        <dt>Activity</dt><dd>${esc(a.current_activity || "—")}</dd>
        ${partners ? `<dt>Conversation</dt><dd>with ${partners}</dd>` : ""}
        ${a.current_research_question ? `<dt>Researching</dt><dd>${esc(a.current_research_question)}</dd>` : ""}
        <dt>Reflection pressure</dt><dd>${a.reflection_pressure.toFixed(1)}</dd>
      `;
    }
  }

  function initAgentDetail(agentId) {
    async function refresh() {
      renderAgentDetail(await getJSON(`/fishbowl/api/agents/${encodeURIComponent(agentId)}`));
    }
    poll(refresh, POLL_MS);
  }

  // ---- Conversations ------------------------------------------------------

  function renderConversationDetail(c) {
    const el = qs("#conversation-messages");
    if (!el || !c) return;
    if (!c.messages.length) {
      el.innerHTML = '<div class="empty">No turns yet.</div>';
      return;
    }
    el.innerHTML = c.messages
      .map(
        (m) => `
      <div class="turn">
        <span class="turn__who">${esc(m.agent_name)}</span><span class="turn__meta">turn ${m.turn_number} · ${fmtTime(m.created_at)}</span>
        <div>${esc(m.content)}</div>
      </div>`
      )
      .join("");
    const status = qs("#conversation-status");
    if (status) status.textContent = c.status;
  }

  function initConversationDetail(id) {
    async function refresh() {
      renderConversationDetail(await getJSON(`/fishbowl/api/conversations/${id}`));
    }
    poll(refresh, POLL_MS);
  }

  // ---- Telemetry -----------------------------------------------------------

  function renderTelemetry(t) {
    const el = qs("#telemetry-body");
    if (!el || !t) return;
    const totals = qs("#telemetry-totals");
    if (totals) {
      totals.innerHTML = `
        <dt>Total LLM calls</dt><dd>${t.llm_total_calls} (${t.llm_live_calls} live)</dd>
        <dt>Total estimated cost</dt><dd>${fmtMoney(t.llm_total_cost_usd)}</dd>
        <dt>Total retries</dt><dd>${t.llm_total_retries}</dd>
        <dt>Research sessions tracked</dt><dd>${t.research_total_sessions} (${t.research_live_sessions} live)</dd>
      `;
    }
    const byPurpose = qs("#telemetry-by-purpose");
    if (byPurpose) {
      byPurpose.innerHTML = t.llm_by_purpose
        .map(
          (p) => `<tr>
          <td data-label="Purpose">${esc(p.purpose)}</td>
          <td data-label="Calls">${p.calls}</td>
          <td data-label="Input tok">${p.input_tokens}</td>
          <td data-label="Output tok">${p.output_tokens}</td>
          <td data-label="Retries">${p.retries}</td>
          <td data-label="Avg latency">${p.avg_latency_ms} ms</td>
          <td data-label="Cost">${fmtMoney(p.estimated_cost_usd)}</td>
        </tr>`
        )
        .join("");
    }
    const recent = qs("#telemetry-recent");
    if (recent) {
      recent.innerHTML = t.recent_llm_runs
        .map(
          (r) => `<tr>
          <td data-label="When">${fmtTime(r.created_at)}</td>
          <td data-label="Purpose">${esc(r.purpose)}</td>
          <td data-label="Agent">${esc(r.agent_name || "—")}</td>
          <td data-label="Model">${esc(r.model)} ${r.is_fixture ? '<span class="badge badge--fixture">FIXTURE</span>' : '<span class="badge badge--live">LIVE</span>'}</td>
          <td data-label="Tokens">${r.input_tokens}/${r.output_tokens}</td>
          <td data-label="Retries">${r.retry_count}</td>
          <td data-label="Latency">${r.latency_ms} ms</td>
          <td data-label="Cost">${fmtMoney(r.estimated_cost_usd)}</td>
        </tr>`
        )
        .join("");
    }
    const usage = qs("#telemetry-research-usage");
    if (usage) {
      usage.innerHTML = t.research_usage
        .map(
          (u) => `<tr>
          <td data-label="Provider">${esc(u.provider)}</td>
          <td data-label="Sessions">${u.sessions}</td>
          <td data-label="Queries">${u.queries_executed}</td>
          <td data-label="Results">${u.results_returned}</td>
          <td data-label="Fetched">${u.sources_fetched}</td>
          <td data-label="Failures">${u.fetch_failures}</td>
          <td data-label="Retries">${u.retry_count}</td>
          <td data-label="Failed sessions">${u.failed_sessions}</td>
        </tr>`
        )
        .join("");
    }
  }

  function initTelemetry() {
    async function refresh() {
      renderTelemetry(await getJSON("/fishbowl/api/telemetry"));
    }
    poll(refresh, POLL_MS);
  }

  // ---- Conversations list ---------------------------------------------------

  function renderConversationList(data) {
    const el = qs("#conversation-list");
    if (!el) return;
    if (!data.conversations.length) {
      el.innerHTML = '<div class="empty">No conversations yet.</div>';
      return;
    }
    el.innerHTML = data.conversations
      .map((c) => {
        const names = c.participants.map((p) => esc(p.name)).join(", ");
        return `<div class="panel" style="cursor:pointer" onclick="location.href='/fishbowl/conversations/${c.id}'">
          <div><strong>${names}</strong> <span class="badge ${c.status === "ACTIVE" ? "badge--good" : "badge--fixture"}">${esc(c.status)}</span></div>
          <div class="dim">${esc(c.current_subject || c.initiating_reason || "")}</div>
          <div class="muted">${esc(c.location || "")} · ${c.message_count} turn(s) · started ${fmtTime(c.started_at)}</div>
        </div>`;
      })
      .join("");
  }

  function initConversationList() {
    async function refresh() {
      renderConversationList(await getJSON("/fishbowl/api/conversations"));
    }
    poll(refresh, POLL_MS);
  }

  // ---- Research list ---------------------------------------------------------

  function renderResearchList(data) {
    const el = qs("#research-list");
    if (!el) return;
    if (!data.sessions.length) {
      el.innerHTML = '<div class="empty">No research sessions yet.</div>';
      return;
    }
    el.innerHTML = data.sessions
      .map(
        (r) => `<div class="panel" style="cursor:pointer" onclick="location.href='/fishbowl/research/${esc(r.research_id)}'">
          <div><strong>${esc(r.agent_name)}</strong> <span class="badge ${r.is_fixture ? "badge--fixture" : "badge--live"}">${r.is_fixture ? "FIXTURE" : "LIVE"}</span> <span class="dim">${esc(r.status)}</span></div>
          <div>${esc(r.question)}</div>
          <div class="muted">${esc(r.evidence_strength)}${r.confidence !== null ? " · " + r.confidence.toFixed(0) + "% confidence" : ""} · ${r.finding_count} finding(s), ${r.source_count} source(s)</div>
        </div>`
      )
      .join("");
  }

  function initResearchList() {
    async function refresh() {
      renderResearchList(await getJSON("/fishbowl/api/research"));
    }
    poll(refresh, POLL_MS);
  }

  // ---- Wall --------------------------------------------------------------------

  function renderWall(data) {
    const el = qs("#wall-posts");
    if (!el) return;
    if (!data.posts.length) {
      el.innerHTML = '<div class="empty">Nothing pinned yet.</div>';
      return;
    }
    el.innerHTML = data.posts
      .map(
        (p) => `<div class="panel" id="post-${p.id}">
          <div><strong>${esc(p.agent_name)}</strong> <span class="badge badge--fixture">${esc(p.post_type)}</span> ${p.sim_day ? `<span class="muted">day ${p.sim_day}</span>` : ""}</div>
          <div>${esc(p.content)}</div>
          <div class="muted">${fmtTime(p.created_at)}${p.related_research_id ? ` · <a href="/fishbowl/research/${esc(p.related_research_id)}">research</a>` : ""}${p.related_rabbit_hole_id ? ` · <a href="/fishbowl/rabbit-holes/${p.related_rabbit_hole_id}">rabbit hole</a>` : ""}</div>
        </div>`
      )
      .join("");
  }

  function initWall() {
    async function refresh() {
      renderWall(await getJSON("/fishbowl/api/wall"));
    }
    poll(refresh, POLL_MS);
  }

  // ---- Rabbit holes --------------------------------------------------------------

  function renderRabbitHoleList(data) {
    const el = qs("#rabbit-hole-list");
    if (!el) return;
    if (!data.rabbit_holes.length) {
      el.innerHTML = '<div class="empty">No rabbit holes yet.</div>';
      return;
    }
    el.innerHTML = data.rabbit_holes
      .map(
        (h) => `<div class="panel" style="cursor:pointer" onclick="location.href='/fishbowl/rabbit-holes/${h.id}'">
          <div><strong>${esc(h.title)}</strong> <span class="badge badge--fixture">${esc(h.status)}</span></div>
          <div class="muted">opened by ${esc(h.originating_agent_name)} · ${h.member_count} member(s) · ${esc(h.evidence_strength)} · heat ${h.activity_level.toFixed(1)}</div>
        </div>`
      )
      .join("");
  }

  function initRabbitHoleList() {
    async function refresh() {
      renderRabbitHoleList(await getJSON("/fishbowl/api/rabbit-holes"));
    }
    poll(refresh, POLL_MS);
  }

  global.Fishbowl = {
    esc, fmtTime, fmtMoney, getJSON, poll, bindControls,
    initDashboard, initAgentDetail, initConversationDetail, initTelemetry,
    initConversationList, initResearchList, initWall, initRabbitHoleList,
    _refresh: null,
  };
})(window);
