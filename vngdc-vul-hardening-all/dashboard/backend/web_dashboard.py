from fastapi import HTTPException
from fastapi.responses import HTMLResponse


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>VNGDC Security</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #081126;
      --muted: #54627a;
      --line: #d8e0ec;
      --blue: #0b5ed7;
      --blue-2: #eaf2ff;
      --green: #059669;
      --green-bg: #eafaf2;
      --amber: #d97706;
      --amber-bg: #fff7e6;
      --red: #dc2626;
      --red-bg: #fff0f0;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); }
    body::before {
      content: ""; position: fixed; inset: 0 0 auto 0; height: 210px; z-index: -1; pointer-events: none;
      border-bottom: 1px solid #dbeafe;
      background: linear-gradient(180deg, #eff6ff 0%, rgba(239,246,255,0) 100%);
    }
    a { color: inherit; text-decoration: none; }
    button, input, select, textarea { font: inherit; }
    button { cursor: pointer; }
    .topbar {
      min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 24px;
      padding: 12px 40px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.95);
      position: sticky; top: 0; z-index: 10; backdrop-filter: blur(12px);
    }
    .brand { display: flex; gap: 12px; align-items: center; min-width: fit-content; }
    .brand-icon { width: 36px; height: 36px; border-radius: 9px; display: grid; place-items: center; color: var(--blue); background: var(--blue-2); border: 1px solid #bfdbfe; }
    .brand-icon svg { width: 20px; height: 20px; }
    .brand-title { font-weight: 750; font-size: 14px; line-height: 20px; }
    .brand-subtitle { color: var(--muted); font-size: 12px; margin-top: 0; }
    .nav { display: flex; gap: 10px; align-items: center; }
    .nav a { min-height: 36px; display: inline-flex; align-items: center; gap: 8px; padding: 0 12px; border-radius: 8px; color: #64748b; font-weight: 650; border: 1px solid transparent; font-size: 14px; }
    .nav a.active { color: var(--blue); background: var(--blue-2); border-color: #bfd8ff; }
    .nav a:hover { color: var(--text); background: #f1f5f9; border-color: var(--line); }
    .nav svg { width: 16px; height: 16px; }
    .container { width: 100%; margin: 0; padding: 24px 40px 48px; }
    .page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 22px; }
    .eyebrow { color: var(--blue); font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 6px 0 6px; font-size: 26px; font-weight: 750; letter-spacing: 0; }
    p { margin: 0; color: var(--muted); line-height: 1.55; }
    .toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .btn {
      border: 1px solid var(--line); background: var(--panel); color: #10203a;
      min-height: 36px; padding: 0 13px; border-radius: 8px; font-weight: 700; font-size: 14px; display: inline-flex; gap: 8px; align-items: center;
    }
    .btn.primary { background: var(--blue); color: #fff; border-color: #0754c4; }
    .btn.danger { color: var(--red); border-color: #fecaca; background: #fff; }
    .btn:hover { background: #f8fafc; }
    .btn.primary:hover { background: #0754c4; }
    .btn:disabled { opacity: .58; cursor: wait; }
    .grid { display: grid; gap: 16px; }
    .page-stack { display: grid; gap: 24px; }
    .cards-5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .cards-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .two-col { grid-template-columns: minmax(0, 2fr) minmax(360px, .95fr); align-items: start; }
    .chat-grid { grid-template-columns: minmax(280px, .75fr) minmax(560px, 1.45fr) minmax(280px, .75fr); height: calc(100vh - 180px); min-height: 640px; }
    .card {
      background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow);
    }
    .metric { padding: 18px 20px; min-height: 112px; position: relative; overflow: hidden; border-left: 0; }
    .metric::before { content: ""; position: absolute; left: 0; top: 0; width: 4px; height: 100%; background: #64748b; }
    .metric.good::before { background: var(--green); }
    .metric.warn::before { background: var(--amber); }
    .metric.bad::before { background: var(--red); }
    .metric.good { border-left-color: var(--green); }
    .metric.warn { border-left-color: var(--amber); }
    .metric.bad { border-left-color: var(--red); }
    .metric-value { font-size: 28px; font-weight: 750; margin-bottom: 6px; padding-left: 12px; }
    .metric-label { font-weight: 650; padding-left: 12px; }
    .metric-note { color: var(--muted); font-size: 13px; margin-top: 3px; padding-left: 12px; }
    .vul-metric { padding: 19px 20px; min-height: 126px; position: relative; overflow: hidden; }
    .vul-metric::before { content: ""; position: absolute; left: 20px; top: 18px; width: 48px; height: 4px; border-radius: 999px; background: #94a3b8; }
    .vul-metric.bad::before { background: var(--red); }
    .vul-metric.warn::before { background: #f97316; }
    .vul-metric.amber::before { background: #f59e0b; }
    .vul-metric-value { margin-top: 26px; font-size: 28px; line-height: 1; font-weight: 750; }
    .vul-metric-label { margin-top: 10px; font-size: 15px; font-weight: 700; }
    .vul-metric-note { margin-top: 6px; color: var(--muted); font-size: 13px; }
    .section-title { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--line); font-weight: 700; }
    .panel-body { padding: 18px 20px; }
    .row {
      display: grid; grid-template-columns: 40px minmax(0, 1fr) auto auto auto; gap: 16px; align-items: center;
      padding: 15px 20px; border-top: 1px solid var(--line);
    }
    .row:first-child { border-top: 0; }
    .row.clickable:hover { background: rgba(241, 245, 249, .72); }
    .asset-row { display: grid; grid-template-columns: 40px minmax(0, 1fr) minmax(110px, auto) auto auto; gap: 16px; align-items: center; padding: 16px 20px; border-top: 1px solid var(--line); }
    .asset-row:first-child { border-top: 0; }
    .asset-row.clickable:hover { background: rgba(241, 245, 249, .72); }
    .asset-icon { width: 40px; height: 40px; border-radius: 9px; display: grid; place-items: center; background: #fff7ed; border: 1px solid #fed7aa; color: #c2410c; font-weight: 900; font-size: 0; }
    .asset-icon.blue { background: #eff6ff; border-color: #bfdbfe; color: var(--blue); }
    .asset-icon.green { background: #ecfdf5; border-color: #a7f3d0; color: var(--green); }
    .asset-icon svg { width: 18px; height: 18px; }
    .name { font-weight: 700; }
    .sub { color: var(--muted); font-size: 13px; margin-top: 2px; }
    .pill {
      display: inline-flex; gap: 7px; align-items: center; border-radius: 999px; padding: 6px 11px;
      font-size: 12px; font-weight: 700; background: #f8fafc; color: #475569; border: 1px solid #dbe4ef;
    }
    .pill.good { background: var(--green-bg); color: #047857; border-color: #a7f3d0; }
    .pill.warn { background: var(--amber-bg); color: #b45309; border-color: #fcd37d; }
    .pill.bad { background: var(--red-bg); color: #b91c1c; border-color: #fecaca; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: currentColor; }
    .empty { padding: 82px 24px; text-align: center; color: var(--muted); }
    .status-line { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin: 12px 0 22px; }
    .report-card { padding: 22px; margin-bottom: 16px; }
    .progress { height: 11px; background: #e9eef5; border-radius: 999px; overflow: hidden; margin: 18px 0; }
    .progress > span { display: block; height: 100%; background: var(--green); width: 0; }
    .checks { display: grid; gap: 10px; }
    .check-row { display: grid; grid-template-columns: 74px minmax(0, 1fr); gap: 12px; padding: 10px 12px; background: #f8fafc; border: 1px solid #e5ebf3; border-radius: 8px; }
    .tabs { display: flex; gap: 9px; flex-wrap: wrap; margin-bottom: 16px; }
    .tab { border: 0; background: #e9eef5; color: #1f344f; border-radius: 9px; padding: 10px 14px; font-weight: 850; }
    .tab.active { background: var(--blue); color: #fff; }
    .cve-card { padding: 20px; margin-top: 14px; }
    .cve-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: start; }
    .cve-title { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-weight: 900; font-size: 18px; }
    .radar-shell { overflow: hidden; }
    .radar-header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; padding: 18px 20px; border-bottom: 1px solid var(--line); }
    .radar-header h2 { margin: 0; font-size: 15px; font-weight: 750; }
    .radar-header p { margin-top: 5px; font-size: 13px; max-width: 860px; }
    .radar-meta { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
    .radar-error { border-bottom: 1px solid #fde68a; background: #fffbeb; color: #92400e; padding: 12px 20px; font-size: 13px; }
    .radar-row { display: grid; grid-template-columns: minmax(0, 1.42fr) minmax(280px, .9fr); gap: 20px; padding: 18px 20px; border-top: 1px solid var(--line); }
    .radar-row:first-of-type { border-top: 0; }
    .radar-badges { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
    .radar-cve { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 14px; font-weight: 800; }
    .radar-title { margin-top: 10px; color: #0f172a; font-weight: 700; line-height: 1.45; }
    .radar-analysis { margin-top: 9px; color: #334155; font-size: 14px; line-height: 1.7; }
    .tag-cloud { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
    .tag { border: 1px solid #bfdbfe; background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 4px 8px; font-size: 12px; }
    .tag.red { border-color: #fecaca; background: #fef2f2; color: #b91c1c; }
    .tag.green { border-color: #bbf7d0; background: #f0fdf4; color: #047857; }
    .radar-side { border: 1px solid #e2e8f0; background: #f8fafc; border-radius: 8px; padding: 14px; }
    .mini-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 11px; }
    .mini-label { color: var(--muted); font-size: 12px; }
    .mini-value { margin-top: 3px; font-weight: 750; font-size: 13px; }
    .recommend-box { margin-top: 13px; border: 1px solid #bbf7d0; background: #ecfdf5; color: #064e3b; border-radius: 7px; padding: 10px 12px; font-size: 13px; line-height: 1.55; }
    .ref-links { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
    .ref-links a { color: var(--blue); font-size: 12px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
    .info-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }
    .info-box { border: 1px solid var(--line); background: #f8fafc; border-radius: 8px; padding: 12px; }
    .info-label { color: var(--muted); font-size: 13px; margin-bottom: 6px; }
    .info-value { font-weight: 850; }
    .callout { border: 1px solid #c6dafb; background: #eef6ff; border-radius: 9px; padding: 14px; margin-top: 12px; }
    .callout.green { border-color: #a7f3d0; background: #effdf5; }
    .callout-title { font-size: 12px; letter-spacing: .18em; color: var(--blue); text-transform: uppercase; font-weight: 900; margin-bottom: 8px; }
    .chat-panel { display: flex; flex-direction: column; min-height: 0; }
    .chat-header { padding: 16px 20px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; }
    .chat-agent { display: flex; align-items: center; gap: 12px; }
    .chat-agent-icon { width: 38px; height: 38px; border-radius: 9px; display: grid; place-items: center; border: 1px solid #bfdbfe; background: #eff6ff; color: var(--blue); }
    .chat-agent-icon svg { width: 20px; height: 20px; }
    .chat-messages { flex: 1; overflow-y: auto; padding: 22px; display: flex; flex-direction: column; gap: 14px; background: #f8fafc; }
    .bubble { max-width: 82%; padding: 13px 15px; border-radius: 9px; border: 1px solid var(--line); background: #fff; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; box-shadow: var(--shadow); }
    .bubble.user { align-self: flex-end; background: var(--blue); color: #fff; border-color: #0754c4; }
    .chat-input { display: grid; grid-template-columns: minmax(0, 1fr) 48px; gap: 10px; padding: 16px; border-top: 1px solid var(--line); background: #fff; }
    .chat-input textarea { resize: none; min-height: 58px; border: 1px solid var(--line); border-radius: 10px; padding: 13px; outline: none; }
    .chat-input textarea:focus { box-shadow: 0 0 0 3px rgba(11,94,215,.12); border-color: #9ec5fe; }
    .send-icon-btn { min-height: 48px; width: 48px; padding: 0; justify-content: center; }
    .send-icon-btn svg { width: 18px; height: 18px; }
    dialog { border: 0; border-radius: 12px; padding: 0; width: min(680px, calc(100vw - 36px)); box-shadow: 0 24px 64px rgba(15, 23, 42, .22); }
    dialog::backdrop { background: rgba(15, 23, 42, .45); }
    .dialog-head { padding: 18px 22px; border-bottom: 1px solid var(--line); font-weight: 900; }
    .dialog-body { padding: 20px 22px; display: grid; gap: 13px; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }
    .field { display: grid; gap: 6px; }
    label { color: #334155; font-weight: 800; font-size: 13px; }
    input, select, textarea { border: 1px solid var(--line); border-radius: 9px; padding: 11px 12px; background: #fff; color: var(--text); }
    textarea.code { min-height: 120px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .dialog-actions { padding: 16px 22px; border-top: 1px solid var(--line); display: flex; justify-content: flex-end; gap: 10px; }
    .toast { position: fixed; right: 22px; bottom: 22px; background: #0f172a; color: #fff; padding: 13px 16px; border-radius: 10px; box-shadow: 0 18px 44px rgba(15,23,42,.2); z-index: 20; display: none; max-width: min(520px, calc(100vw - 44px)); }
    .donut-wrap { min-height: 245px; display: grid; place-items: center; gap: 14px; }
    .donut {
      --hard: 0deg; --partial: 0deg; --none: 0deg;
      width: 210px; aspect-ratio: 1; border-radius: 50%;
      background: conic-gradient(
        var(--green) 0 var(--hard),
        var(--amber) var(--hard) calc(var(--hard) + var(--partial)),
        var(--red) calc(var(--hard) + var(--partial)) calc(var(--hard) + var(--partial) + var(--none)),
        #64748b calc(var(--hard) + var(--partial) + var(--none)) 360deg
      );
      position: relative;
    }
    .donut::after { content: ""; position: absolute; inset: 36px; border-radius: 50%; background: var(--panel); }
    .legend-inline { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; color: var(--muted); font-size: 13px; }
    .legend-item { display: inline-flex; gap: 6px; align-items: center; }
    .legend-dot { width: 9px; height: 9px; border-radius: 50%; background: #64748b; }
    .markdown-lite h2, .markdown-lite h3 { margin: 12px 0 8px; }
    .markdown-lite p { margin-bottom: 10px; }
    .markdown-lite code { background: #eef2f7; padding: 2px 5px; border-radius: 5px; }
    @media (max-width: 1100px) {
      .cards-5, .cards-4, .two-col, .chat-grid { grid-template-columns: 1fr; height: auto; }
      .topbar { padding: 0 18px; height: auto; min-height: 78px; align-items: flex-start; flex-direction: column; gap: 12px; padding-top: 14px; padding-bottom: 14px; }
      .container { width: 100%; padding: 20px 18px 40px; }
      .row, .asset-row, .radar-row { grid-template-columns: 42px minmax(0, 1fr); }
      .radar-row { display: block; }
      .radar-side { margin-top: 14px; }
      .info-grid, .form-grid { grid-template-columns: 1fr; }
      .bubble { max-width: 94%; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <a href="/hardening" class="brand">
      <div class="brand-icon">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" />
        </svg>
      </div>
      <div>
        <div class="brand-title">VNGDC Security</div>
        <div class="brand-subtitle">Hardening and vulnerability operations</div>
      </div>
    </a>
    <nav class="nav">
      <a href="/hardening" data-nav="hardening">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-5" /></svg>
        Hardening
      </a>
      <a href="/vulnerabilities" data-nav="vulnerabilities">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v4m0 4h.01M10.3 4.4L2.8 18a2 2 0 001.7 3h15a2 2 0 001.7-3L13.7 4.4a2 2 0 00-3.4 0z" /></svg>
        Vul Assets
      </a>
      <a href="/vulnerabilities/radar" data-nav="radar">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12h3l2.3-6 4.4 12L15 12h6" /></svg>
        CVE Radar
      </a>
      <a href="/chat" data-nav="chat">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h8M8 14h5m8-2a8 8 0 11-15.5-2.8L3 21l4.2-1.4A8 8 0 0021 12z" /></svg>
        Agent Chat
      </a>
    </nav>
  </header>

  <main id="app" class="container"></main>

  <dialog id="serverDialog">
    <form method="dialog" onsubmit="return false;">
      <div class="dialog-head">Add managed server</div>
      <div class="dialog-body">
        <div class="form-grid">
          <div class="field"><label>Name</label><input id="srvName" required placeholder="VNGDC-SYS-SERVER" /></div>
          <div class="field"><label>OS type</label><select id="srvOs"><option value="ubuntu">Ubuntu</option><option value="windows">Windows</option><option value="junos">Juniper Junos</option></select></div>
          <div class="field"><label>Host</label><input id="srvHost" required placeholder="10.0.0.10" /></div>
          <div class="field"><label>Port</label><input id="srvPort" type="number" value="22" min="1" max="65535" /></div>
          <div class="field"><label>Username</label><input id="srvUser" required placeholder="agent" /></div>
          <div class="field"><label>Password</label><input id="srvPassword" type="password" placeholder="optional if SSH key is used" /></div>
        </div>
        <div class="field"><label>SSH private key</label><textarea id="srvKey" class="code" placeholder="optional"></textarea></div>
      </div>
      <div class="dialog-actions">
        <button class="btn" type="button" onclick="closeDialog('serverDialog')">Cancel</button>
        <button class="btn primary" type="button" onclick="createServer()">Create server</button>
      </div>
    </form>
  </dialog>

  <dialog id="scheduleDialog">
    <form method="dialog" onsubmit="return false;">
      <div class="dialog-head">Scheduled CVE checks</div>
      <div class="dialog-body">
        <div class="field"><label><input id="schEnabled" type="checkbox" /> Enable recurring vulnerability refresh</label></div>
        <div class="form-grid">
          <div class="field"><label>Interval seconds</label><input id="schInterval" type="number" min="60" max="604800" value="900" /></div>
          <div class="field"><label>Wazuh agent filter</label><input id="schAgent" placeholder="optional" /></div>
        </div>
        <div class="field"><label><input id="schAnalysis" type="checkbox" checked /> Include agent analysis</label></div>
        <div class="field"><label><input id="schReport" type="checkbox" checked /> Send Telegram/Teams report from agent</label></div>
        <p id="scheduleMeta"></p>
      </div>
      <div class="dialog-actions">
        <button class="btn" type="button" onclick="closeDialog('scheduleDialog')">Cancel</button>
        <button class="btn primary" type="button" onclick="saveSchedule()">Save schedule</button>
      </div>
    </form>
  </dialog>

  <div id="toast" class="toast"></div>

  <script>
    const app = document.getElementById('app');
    const chatSession = localStorage.getItem('vngdc-chat-session') || `dashboard-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem('vngdc-chat-session', chatSession);

    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const pct = (value) => `${Math.round(Number(value || 0) * 100) / 100}%`;
    const int = (value) => Number.parseInt(value || 0, 10) || 0;

    async function api(path, options = {}) {
      const init = {headers: {'Content-Type': 'application/json'}, ...options};
      if (options.body && typeof options.body !== 'string') init.body = JSON.stringify(options.body);
      const res = await fetch(path, init);
      if (res.status === 204) return null;
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = text; }
      if (!res.ok) {
        const message = typeof data === 'object' && data && data.detail ? data.detail : text || `HTTP ${res.status}`;
        throw new Error(message);
      }
      return data;
    }

    function toast(message) {
      const node = document.getElementById('toast');
      node.textContent = message;
      node.style.display = 'block';
      clearTimeout(node._timer);
      node._timer = setTimeout(() => node.style.display = 'none', 4200);
    }

    function route() { return window.location.pathname.replace(/\/+$/, '') || '/hardening'; }
    function activeNav() {
      const p = route();
      document.querySelectorAll('.nav a').forEach(a => a.classList.remove('active'));
      const key = p.startsWith('/vulnerabilities/radar') ? 'radar' : p.startsWith('/vulnerabilities') ? 'vulnerabilities' : (p.startsWith('/agent-chat') || p.startsWith('/chat')) ? 'chat' : 'hardening';
      document.querySelector(`[data-nav="${key}"]`)?.classList.add('active');
    }
    function go(path) { history.pushState({}, '', path); render(); }
    window.addEventListener('popstate', render);
    document.addEventListener('click', (event) => {
      const link = event.target.closest('a[href^="/"]');
      if (!link || event.metaKey || event.ctrlKey) return;
      event.preventDefault();
      go(link.getAttribute('href'));
    });

    function timeAgo(value) {
      if (!value) return 'Never';
      const diff = Date.now() - new Date(value).getTime();
      if (!Number.isFinite(diff)) return 'Unknown';
      const min = Math.max(0, Math.round(diff / 60000));
      if (min < 1) return 'just now';
      if (min < 60) return `${min} min ago`;
      const h = Math.round(min / 60);
      if (h < 48) return `${h} hours ago`;
      return `${Math.round(h / 24)} days ago`;
    }

    function statusLabel(status) {
      return ({hardened:'Hardened', partial:'Partial', none:'Not Hardened', fail:'Not Hardened', warn:'Partial', pass:'Passed', error:'Error', pending:'Pending', running:'Running'}[status] || 'Unchecked');
    }
    function statusClass(status) {
      if (['good', 'warn', 'bad'].includes(status)) return status;
      if (['hardened', 'pass', 'completed', 'OK'].includes(status)) return 'good';
      if (['partial', 'warn', 'P2', 'P3'].includes(status)) return 'warn';
      if (['none', 'fail', 'error', 'failed', 'P1'].includes(status)) return 'bad';
      return '';
    }
    function pill(label, status) {
      return `<span class="pill ${statusClass(status)}"><span class="dot"></span>${esc(label)}</span>`;
    }
    function severityClass(sev) {
      const value = String(sev || '').toLowerCase();
      if (value === 'critical' || value === 'high') return 'bad';
      if (value === 'medium') return 'warn';
      return '';
    }

    function header(eyebrow, title, subtitle, actions = '') {
      return `<div class="page-head"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="toolbar">${actions}</div></div>`;
    }
    function metric(value, label, note, kind = '') {
      return `<div class="card metric ${kind}"><div class="metric-value">${esc(value)}</div><div class="metric-label">${esc(label)}</div><div class="metric-note">${esc(note)}</div></div>`;
    }
    function vulMetric(value, label, note, kind = '') {
      return `<div class="card vul-metric ${kind}"><div class="vul-metric-value">${esc(value)}</div><div class="vul-metric-label">${esc(label)}</div><div class="vul-metric-note">${esc(note)}</div></div>`;
    }
    function serverIcon(os) {
      const tone = os === 'junos' ? 'green' : os === 'windows' ? 'blue' : '';
      return `<div class="asset-icon ${tone}"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 7h14M7 7v10m10-10v10M5 17h14M8 11h.01M8 14h.01M16 11h.01M16 14h.01" /></svg></div>`;
    }
    function cveIcon() {
      return `<div class="asset-icon blue"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v4m0 4h.01M10.3 4.4L2.8 18a2 2 0 001.7 3h15a2 2 0 001.7-3L13.7 4.4a2 2 0 00-3.4 0z" /></svg></div>`;
    }
    function severityLabel(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'critical') return 'Critical';
      if (v === 'high') return 'High';
      if (v === 'medium') return 'Medium';
      if (v === 'low') return 'Low';
      return 'Unknown';
    }
    function exploitLabel(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'known exploited') return 'Known exploited';
      if (v === 'high') return 'High';
      if (v === 'medium') return 'Medium';
      if (v === 'low') return 'Low';
      return 'Unknown';
    }
    function relationLabel(item) {
      if (item.relation_label) return item.relation_label;
      if (item.relation === 'direct') return 'Seen in system';
      if (item.relation === 'possible') return 'Possibly relevant';
      return 'Not seen';
    }
    function percentLabel(value) {
      const n = Number(value || 0);
      return `${(n * 100).toFixed(n > 0 && n < 0.01 ? 2 : 1)}%`;
    }
    function riskClass(score) {
      const n = Number(score || 0);
      if (n >= 85) return 'bad';
      if (n >= 65) return 'bad';
      if (n >= 40) return 'warn';
      return 'good';
    }
    function openDialog(id) { document.getElementById(id).showModal(); }
    function closeDialog(id) { document.getElementById(id).close(); }

    async function render() {
      activeNav();
      const p = route();
      try {
        if (p.startsWith('/agent-chat') || p.startsWith('/chat')) return renderChat();
        if (p.startsWith('/vulnerabilities/radar')) return renderRadar();
        if (p.startsWith('/vulnerabilities/') && p !== '/vulnerabilities') return renderVulnerabilityDetail(p.split('/').pop());
        if (p.startsWith('/vulnerabilities')) return renderVulnerabilities();
        if (p.startsWith('/hardening/') && p !== '/hardening') return renderHardeningDetail(p.split('/').pop());
        return renderHardening();
      } catch (error) {
        app.innerHTML = `<div class="card empty"><h2>Dashboard failed</h2><p>${esc(error.message || error)}</p></div>`;
      }
    }

    async function renderHardening() {
      app.innerHTML = header('Hardening', 'Server hardening checks', 'Monitor configured Ubuntu, Windows, and network hardening baselines.', `<button class="btn primary" onclick="openDialog('serverDialog')">+ Add Server</button>`) + `<div class="empty">Loading...</div>`;
      const [stats, servers] = await Promise.all([api('/api/stats'), api('/api/servers')]);
      app.innerHTML = `<div class="page-stack">`
        + header('Hardening', 'Server hardening checks', 'Monitor configured Ubuntu, Windows, and network hardening baselines.', `<button class="btn primary" onclick="openDialog('serverDialog')">+ Add Server</button>`)
        + `<div class="grid cards-5">
          ${metric(stats.total, 'Total Servers', 'Managed assets')}
          ${metric(stats.hardened, 'Hardened', 'All checks pass', 'good')}
          ${metric(stats.partial, 'Partial', 'Needs review', 'warn')}
          ${metric(stats.none, 'Not Hardened', 'Needs action', 'bad')}
          ${metric(stats.unchecked, 'Unchecked', 'Never scanned')}
        </div>
        <div class="grid two-col">
          <div class="card"><div class="section-title"><span>Hardening distribution</span><span class="sub">${servers.length} assets</span></div><div class="panel-body">${distribution(stats)}</div></div>
          <div class="card"><div class="section-title"><span>Managed servers</span><span class="sub">${servers.length} rows</span></div>${servers.length ? servers.map(serverRow).join('') : `<div class="empty">No managed servers yet</div>`}</div>
        </div></div>`;
    }
    function distribution(stats) {
      const total = Math.max(int(stats.total), 1);
      const hard = Math.round(int(stats.hardened) / total * 360);
      const partial = Math.round(int(stats.partial) / total * 360);
      const none = Math.round(int(stats.none) / total * 360);
      const rows = [
        ['Hardened', stats.hardened, 'var(--green)'],
        ['Partial', stats.partial, 'var(--amber)'],
        ['Not Hardened', stats.none, 'var(--red)'],
        ['Unchecked', stats.unchecked, '#64748b'],
      ].filter(([, count]) => int(count) > 0);
      const legend = rows.length ? rows.map(([label, count, color]) => `<span class="legend-item"><span class="legend-dot" style="background:${color}"></span>${esc(label)} (${esc(count)})</span>`).join('') : '<span class="sub">No servers added yet</span>';
      return `<div class="donut-wrap">
        <div class="donut" style="--hard:${hard}deg;--partial:${partial}deg;--none:${none}deg" aria-label="Hardening distribution"></div>
        <div class="legend-inline">${legend}</div>
      </div>`;
    }
    function serverRow(s) {
      const status = s.last_status || 'unchecked';
      return `<div class="row clickable" onclick="go('/hardening/${s.id}')">
        ${serverIcon(s.os_type)}<div><div class="name">${esc(s.name)}</div><div class="sub">${esc(s.username)}@${esc(s.host)}:${esc(s.port)} - ${esc(s.os_type)}</div></div>
        <div class="sub">${timeAgo(s.last_checked_at)}</div>${pill(statusLabel(status), status)}
        <button class="btn" onclick="event.stopPropagation(); runCheck('${s.id}')">Run Check</button></div>`;
    }
    async function createServer() {
      const body = {
        name: document.getElementById('srvName').value.trim(),
        host: document.getElementById('srvHost').value.trim(),
        port: int(document.getElementById('srvPort').value) || 22,
        username: document.getElementById('srvUser').value.trim(),
        password: document.getElementById('srvPassword').value || null,
        ssh_key: document.getElementById('srvKey').value || null,
        os_type: document.getElementById('srvOs').value,
      };
      try {
        const server = await api('/api/servers', {method:'POST', body});
        closeDialog('serverDialog');
        toast('Server created');
        go(`/hardening/${server.id}`);
      } catch (error) { toast(`Create failed: ${error.message}`); }
    }
    async function runCheck(serverId) {
      try {
        const task = await api(`/api/servers/${serverId}/check`, {method:'POST'});
        toast('Hardening check started');
        pollTask(task.id);
      } catch (error) { toast(`Check failed: ${error.message}`); }
    }
    async function pollTask(taskId) {
      for (let i = 0; i < 120; i++) {
        await new Promise(resolve => setTimeout(resolve, 2500));
        const task = await api(`/api/tasks/${taskId}`).catch(() => null);
        if (!task) continue;
        if (['completed', 'failed'].includes(task.status)) {
          toast(task.status === 'completed' ? 'Hardening check completed' : `Hardening check failed: ${task.error || 'unknown error'}`);
          render();
          return;
        }
      }
      render();
    }

    async function renderHardeningDetail(serverId) {
      app.innerHTML = `<div class="empty">Loading server report...</div>`;
      const [server, reports] = await Promise.all([api(`/api/servers/${serverId}`), api(`/api/servers/${serverId}/reports`).catch(() => [])]);
      const report = reports[0];
      const actions = `<button class="btn primary" onclick="runCheck('${server.id}')">Run Hardening Check</button><button class="btn danger" onclick="deleteServer('${server.id}')">Delete</button>`;
      app.innerHTML = `<div class="status-line"><a class="btn" href="/hardening">Back to Hardening</a></div>`
        + header('Hardening Detail', server.name, `${server.username}@${server.host}:${server.port} - ${server.os_type}`, actions)
        + `<div class="status-line">${pill(statusLabel(server.last_status || 'unchecked'), server.last_status || 'unchecked')}<span class="sub">Last checked ${timeAgo(server.last_checked_at)}</span></div>`
        + (report ? reportView(server, report, reports) : `<div class="card empty"><h2>No hardening report yet</h2><p>Run a hardening check to scan this server.</p></div>`);
    }
    function reportView(server, report, reports) {
      const sections = Array.isArray(report.sections) ? report.sections : [];
      const pass = sections.reduce((n, s) => n + int(s.pass_count), 0);
      const fail = sections.reduce((n, s) => n + int(s.fail_count), 0);
      const warn = sections.reduce((n, s) => n + int(s.warn_count), 0);
      const scored = sections.filter(s => ['pass', 'fail', 'warn'].includes(s.status)).length;
      const passed = sections.filter(s => s.status === 'pass').length;
      const ratio = scored ? Math.round(passed / scored * 100) : 0;
      return `<div class="tabs">${reports.slice(0, 8).map((r, i) => `<button class="tab ${i===0?'active':''}" onclick="go('/hardening/${server.id}')">${i===0?'Latest':'#'+(reports.length-i)} - ${timeAgo(r.checked_at)}</button>`).join('')}</div>
      <div class="card report-card">
        <div class="section-title" style="padding:0 0 16px;border-bottom:0"><div><div style="font-size:22px;font-weight:900">${passed} / ${scored} sections passed</div><p>Checked ${timeAgo(report.checked_at)} - ${esc(report.duration_seconds || 0)}s</p></div><div class="toolbar"><a class="btn" href="/api/servers/${server.id}/reports/${report.id}/export.xlsx">XLSX</a>${pill(statusLabel(report.status), report.status)}</div></div>
        <div class="progress"><span style="width:${ratio}%"></span></div>
        <div class="status-line"><b style="color:var(--green)">${pass} Pass</b><b style="color:var(--red)">${fail} Fail</b><b style="color:var(--amber)">${warn} Warn</b></div>
        ${report.analysis ? `<div class="callout"><div class="callout-title">Agent analysis</div>${formatText(report.analysis)}</div>` : ''}
      </div>
      <div class="grid">${sections.map(sectionView).join('') || `<div class="card empty">No parsed sections in this report</div>`}</div>`;
    }
    function sectionView(section) {
      const checks = Array.isArray(section.checks) ? section.checks : [];
      return `<div class="card report-card"><div class="section-title" style="padding:0 0 14px"><span>${esc(section.name)}</span>${pill(statusLabel(section.status), section.status)}</div>
        <div class="checks">${checks.map(c => `<div class="check-row"><div>${pill(String(c.level || '').toUpperCase(), c.level)}</div><div>${esc(c.message)}</div></div>`).join('') || '<p>No checks</p>'}</div></div>`;
    }
    async function deleteServer(serverId) {
      if (!confirm('Delete this server and its reports?')) return;
      await api(`/api/servers/${serverId}`, {method:'DELETE'});
      toast('Server deleted');
      go('/hardening');
    }

    async function renderVulnerabilities() {
      app.innerHTML = header('Vulnerability Assets', 'Asset vulnerability posture', 'Track Wazuh CVE exposure, scanner status, and latest findings.', `<button class="btn" onclick="openSchedule()">Scheduled CVE checks</button><a class="btn" href="/api/vulnerabilities/latest/export.xlsx">Export XLSX</a><button class="btn primary" onclick="refreshVulns()">Refresh from Agent</button>`) + `<div class="empty">Loading...</div>`;
      const [summary, servers, schedule, agent] = await Promise.all([
        api('/api/vulnerabilities/summary'),
        api('/api/servers'),
        api('/api/vulnerabilities/schedule').catch(() => null),
        api('/api/agent/status').catch(() => ({connected:false})),
      ]);
      const assets = await Promise.all(servers.map(s => api(`/api/vulnerabilities/assets/${s.id}?limit=8`).catch(error => ({server:s, error:error.message, total:0, critical:0, high:0, medium:0, low:0, items:[], assessment:{priority:'Unknown', verdict:'Unknown'}}))));
      const atRisk = assets.filter(a => a.assessment && a.assessment.priority && a.assessment.priority !== 'OK').length;
      const unknown = assets.filter(a => !a.latest_scan_id || a.total === 0).length;
      app.innerHTML = `<div class="page-stack">`
        + header('Vulnerability Assets', 'Asset vulnerability posture', 'Track Wazuh CVE exposure, scanner status, and latest findings.', `<button class="btn" onclick="openSchedule()">Scheduled CVE checks</button><a class="btn" href="/api/vulnerabilities/latest/export.xlsx">Export XLSX</a><button class="btn primary" onclick="refreshVulns()">Refresh from Agent</button>`)
        + `<div class="grid cards-4">
          ${vulMetric(summary.critical, 'Critical CVEs', `Last scan ${timeAgo(summary.scanned_at)}`, 'bad')}
          ${vulMetric(summary.high, 'High CVEs', `Source: ${summary.source || 'pending'}`, 'warn')}
          ${vulMetric(atRisk, 'Assets at risk', 'Derived from Wazuh findings', 'amber')}
          ${vulMetric(unknown, 'Unknown coverage', 'Assets with no mapped CVE')}
        </div>
        <div class="grid two-col">
          <div class="card"><div class="section-title"><span>Asset vulnerability posture</span><span class="sub">${assets.length} assets</span></div>${assets.map(vulAssetRow).join('') || '<div class="empty">No managed assets</div>'}</div>
          <div class="grid">
            <div class="card"><div class="section-title"><span>Scanner readiness</span></div><div class="panel-body">
              ${scannerLine('Hardening database', `${servers.length} managed assets`, true)}
              ${scannerLine('Security agent', agent.connected ? 'Runtime reachable' : (agent.error || 'Not reachable'), agent.connected)}
              ${scannerLine('CVE scanner feed', `${summary.fetched || summary.total || 0} findings fetched - ${timeAgo(summary.scanned_at)}`, summary.status === 'completed')}
              ${schedule ? scannerLine('Scheduled checks', schedule.enabled ? `Every ${schedule.interval_seconds}s - next ${timeAgo(schedule.next_run_at)}` : 'Disabled', schedule.enabled) : ''}
            </div></div>
            <div class="card"><div class="section-title"><span>Latest vulnerability signals</span></div><div class="panel-body">${latestSignals(summary.items || [])}</div></div>
          </div>
        </div></div>`;
    }
    function scannerLine(title, note, ok) {
      return `<div style="display:flex;justify-content:space-between;gap:14px;margin:14px 0"><div><b>${esc(title)}</b><div class="sub">${esc(note)}</div></div>${pill(ok ? 'Online' : 'Pending', ok ? 'hardened' : 'unchecked')}</div>`;
    }
    function vulAssetRow(a) {
      const s = a.server || {};
      const priority = a.assessment?.priority || 'Unknown';
      const verdict = a.assessment?.verdict || (a.total ? 'Needs review' : 'No mapped CVE');
      const status = priority === 'OK' ? 'hardened' : priority === 'P1' ? 'none' : priority === 'Unknown' ? 'unchecked' : 'partial';
      return `<div class="asset-row clickable" onclick="go('/vulnerabilities/${s.id}')">
        ${cveIcon()}<div><div class="name">${esc(s.name)}</div><div class="sub">${esc(s.host)}:${esc(s.port)} - ${esc(s.os_type || '')}</div></div>
        <div class="sub">${a.total || 0} findings</div>${pill(priority, status)}<div class="sub">${esc(verdict)}</div></div>`;
    }
    function latestSignals(items) {
      const rows = items.slice(0, 8);
      if (!rows.length) return '<p>No vulnerability findings in dashboard yet.</p>';
      return rows.map(item => `<div style="margin:14px 0"><div class="cve-title" style="font-size:16px">${pill(item.severity || 'Low', severityClass(item.severity))}<span>${esc(item.cve || 'CVE')}</span> - ${esc(item.package || 'unknown')}</div><div class="sub">${esc(item.severity || 'Unknown')} on ${esc(item.agent || item.host || 'unknown asset')}</div></div>`).join('');
    }
    async function refreshVulns() {
      toast('Vulnerability refresh started');
      try {
        await api('/api/vulnerabilities/refresh', {method:'POST', body:{agent_name:'', include_analysis:true, send_report:true}});
        toast('Vulnerability refresh completed');
      } catch (error) { toast(`Refresh failed: ${error.message}`); }
      render();
    }
    async function openSchedule() {
      try {
        const schedule = await api('/api/vulnerabilities/schedule');
        document.getElementById('schEnabled').checked = !!schedule.enabled;
        document.getElementById('schInterval').value = schedule.interval_seconds || 900;
        document.getElementById('schAgent').value = schedule.agent_name || '';
        document.getElementById('schAnalysis').checked = !!schedule.include_analysis;
        document.getElementById('schReport').checked = !!schedule.send_report;
        document.getElementById('scheduleMeta').textContent = `Last status: ${schedule.last_status || 'none'} | Next run: ${timeAgo(schedule.next_run_at)}`;
      } catch (error) { document.getElementById('scheduleMeta').textContent = error.message; }
      openDialog('scheduleDialog');
    }
    async function saveSchedule() {
      const body = {
        enabled: document.getElementById('schEnabled').checked,
        interval_seconds: int(document.getElementById('schInterval').value) || 900,
        include_analysis: document.getElementById('schAnalysis').checked,
        send_report: document.getElementById('schReport').checked,
        agent_name: document.getElementById('schAgent').value.trim(),
      };
      try {
        await api('/api/vulnerabilities/schedule', {method:'PUT', body});
        closeDialog('scheduleDialog');
        toast('Schedule saved');
        render();
      } catch (error) { toast(`Schedule failed: ${error.message}`); }
    }

    async function renderVulnerabilityDetail(serverId) {
      app.innerHTML = `<div class="empty">Loading CVE detail...</div>`;
      const detail = await api(`/api/vulnerabilities/assets/${serverId}?limit=300`);
      const s = detail.server;
      const a = detail.assessment || {};
      app.innerHTML = `<div class="page-stack"><div class="status-line"><a class="btn" href="/vulnerabilities">Back to Vulnerabilities</a></div>`
        + header('Asset CVE detail', s.name, `${s.host}:${s.port} - ${s.os_type}`, `<a class="btn" href="/api/vulnerabilities/assets/${s.id}/export.xlsx">Export XLSX</a>`)
        + `<div class="grid cards-4">
          ${vulMetric(detail.critical, 'Critical', 'Critical findings', 'bad')}
          ${vulMetric(detail.high, 'High', 'High findings', 'warn')}
          ${vulMetric(detail.medium, 'Medium', 'Medium findings', 'amber')}
          ${vulMetric(detail.low, 'Low', 'Low findings')}
        </div>
        <div class="card report-card">
          <div class="section-title" style="padding:0 0 14px">
            <span>Agent assessment</span>${pill(a.priority || 'Unknown', a.priority || 'Unknown')}
          </div>
          <p style="font-weight:700;color:var(--text);margin-bottom:6px">${esc(a.verdict || 'No verdict yet')}</p>
          <p>${esc(a.summary || 'No assessment yet.')}</p>
          <div class="info-grid">
            <div class="info-box"><div class="info-label">Max risk score</div><div class="info-value">${esc(a.max_risk_score || 0)}/100</div></div>
            <div class="info-box"><div class="info-label">Known exploited</div><div class="info-value">${esc(a.known_exploited || 0)}</div></div>
            <div class="info-box"><div class="info-label">Max EPSS</div><div class="info-value">${percentLabel(a.max_epss)}</div></div>
            <div class="info-box"><div class="info-label">Scan status</div><div class="info-value">${esc(detail.status || 'Unknown')}</div></div>
          </div>
        </div>
        <div>${(detail.items || []).map(cveCard).join('') || '<div class="card empty">No CVE mapped to this asset in the latest scan.</div>'}</div></div>`;
    }
    function cveCard(item) {
      const refs = Array.isArray(item.reference) ? item.reference : [];
      const plan = Array.isArray(item.patch_plan) ? item.patch_plan : [];
      return `<div class="card cve-card">
        <div class="cve-head"><div><div class="cve-title">${pill(item.severity || 'Low', severityClass(item.severity))}<span>${esc(item.cve || 'CVE')}</span>${pill(item.risk_priority || 'P3', item.risk_priority || 'P3')}${pill(`Risk ${item.risk_score || 0}/100`, item.risk_label || '')}</div>
        <div class="sub">${esc(item.package || 'unknown package')} - ${esc(item.version || '')}</div></div><div class="sub">CVSS ${esc(item.score || item.nvd_cvss_score || 'N/A')}</div></div>
        <p style="margin-top:14px">${esc(item.description || item.title || 'No description available.')}</p>
        <div class="info-grid">
          <div class="info-box"><div class="info-label">Exploit likelihood</div><div class="info-value">${esc(item.exploit_likelihood || 'Unknown')}</div></div>
          <div class="info-box"><div class="info-label">EPSS</div><div class="info-value">${pct((Number(item.epss || 0) * 100))}</div></div>
          <div class="info-box"><div class="info-label">Fixed version</div><div class="info-value">${esc(item.fixed_version || 'Vendor advisory required')}</div></div>
          <div class="info-box"><div class="info-label">Patch SLA</div><div class="info-value">${esc(item.patch_sla || 'N/A')}</div></div>
        </div>
        <div class="callout"><div class="callout-title">Agent evaluation</div>${formatText(item.agent_assessment || 'No agent evaluation.')}</div>
        <div class="callout green"><div class="callout-title">Recommended fix</div>${formatText(item.recommendation || 'Review vendor advisory and update affected package.')}</div>
        ${plan.length ? `<div class="callout"><div class="callout-title">Patch plan</div><ol>${plan.map(step => `<li>${esc(step)}</li>`).join('')}</ol></div>` : ''}
        ${refs.length ? `<div class="status-line">${refs.slice(0,5).map((url, i) => `<a class="pill" target="_blank" rel="noreferrer" href="${esc(url)}">Reference ${i+1}</a>`).join('')}</div>` : ''}
      </div>`;
    }

    async function renderRadar() {
      app.innerHTML = header('CVE Radar', 'High-risk CVE intelligence', 'Track dangerous CVEs from CISA KEV, NVD, EPSS, and local Wazuh relevance.', `<button class="btn primary" onclick="renderRadar()">Refresh intelligence</button>`) + `<div class="empty">Loading CVE radar...</div>`;
      const data = await api('/api/vulnerabilities/emerging?limit=10&days=14');
      const errors = Array.isArray(data.errors) && data.errors.length ? `<div class="radar-error">${esc(data.errors.join(' | '))}</div>` : '';
      app.innerHTML = `<div class="page-stack">`
        + header('CVE Radar', 'High-risk CVE intelligence', 'Track dangerous CVEs from CISA KEV, NVD, EPSS, and local Wazuh relevance.', `<button class="btn primary" onclick="renderRadar()">Refresh intelligence</button>`)
        + `<div class="card radar-shell">
          <div class="radar-header">
            <div>
              <h2>Top 10 CVEs to monitor</h2>
              <p>Agent correlates external vulnerability intelligence with the latest Wazuh scan to estimate relevance to the internal system.</p>
            </div>
            <div class="radar-meta">
              <span class="pill">Updated ${esc(timeAgo(data.generated_at))}</span>
              <span class="pill">${esc((data.sources || []).join(', ') || 'CVE sources')}</span>
            </div>
          </div>
          ${errors}
          ${(data.items || []).map(radarRow).join('') || '<div class="empty">No emerging CVEs available.</div>'}
        </div></div>`;
    }
    function radarRow(item) {
      const relation = relationLabel(item);
      const relationKind = item.relation === 'direct' ? 'bad' : item.relation === 'possible' ? 'warn' : '';
      const refs = Array.isArray(item.references) ? item.references : [];
      const assets = Array.isArray(item.affected_assets) ? item.affected_assets : [];
      const packages = Array.isArray(item.matched_packages) ? item.matched_packages : [];
      const tags = [
        ...assets.slice(0, 4).map(asset => `<span class="tag red">${esc(asset)}</span>`),
        ...packages.slice(0, 5).map(pkg => `<span class="tag">${esc(pkg)}</span>`),
      ].join('');
      return `<div class="radar-row">
        <div class="radar-main">
          <div class="radar-badges">
            <span class="radar-cve">${esc(item.cve || 'CVE')}</span>
            ${pill(severityLabel(item.severity), severityClass(item.severity))}
            ${pill(`Risk ${item.risk_score || 0}/100`, riskClass(item.risk_score))}
            ${item.known_exploited ? pill('CISA KEV', 'bad') : ''}
            ${pill(relation, relationKind)}
          </div>
          <div class="radar-title">${esc(item.title || item.description || 'No CVE title from source')}</div>
          <div class="radar-analysis">${esc(item.analysis || item.description || 'No relevance analysis available.')}</div>
          ${tags ? `<div class="tag-cloud">${tags}</div>` : ''}
        </div>
        <div class="radar-side">
          <div class="mini-grid">
            <div><div class="mini-label">CVSS</div><div class="mini-value">${item.cvss ? Number(item.cvss).toFixed(1) : 'N/A'}</div></div>
            <div><div class="mini-label">EPSS</div><div class="mini-value">${percentLabel(item.epss)}</div></div>
            <div><div class="mini-label">Exploit</div><div class="mini-value">${esc(exploitLabel(item.exploit_likelihood))}</div></div>
            <div><div class="mini-label">Source</div><div class="mini-value">${esc(item.source || 'N/A')}</div></div>
          </div>
          <div class="recommend-box"><b>Recommendation: </b>${esc(item.recommendation || 'Monitor feed and verify affected product/package before opening remediation change.')}</div>
          ${refs.length ? `<div class="ref-links">${refs.slice(0, 3).map((url, i) => `<a target="_blank" rel="noreferrer" href="${esc(url)}">Source ${i + 1}</a>`).join('')}</div>` : ''}
        </div>
      </div>`;
    }

    async function renderChat() {
      app.innerHTML = header('Agent Chat', 'Security operations chat', 'Ask the agent about hardening, CVEs, Wazuh data, and runtime findings.')
        + `<div class="grid chat-grid">
          <div class="card"><div class="section-title"><span>Operations summary</span></div><div id="chatSummary" class="panel-body">Loading...</div></div>
          <div class="card chat-panel"><div class="chat-header"><div class="chat-agent"><div class="chat-agent-icon"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h8M8 14h5m8-2a8 8 0 11-15.5-2.8L3 21l4.2-1.4A8 8 0 0021 12z" /></svg></div><div><div class="name">Security Agent</div><div class="sub">AgentBase runtime</div></div></div><span id="agentPill">${pill('Checking', '')}</span></div><div id="messages" class="chat-messages"></div><div class="chat-input"><textarea id="chatText" placeholder="Ask the security agent..."></textarea><button class="btn primary send-icon-btn" title="Send" onclick="sendChat()"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg></button></div></div>
          <div class="card"><div class="section-title"><span>Latest events</span></div><div id="chatEvents" class="panel-body">Loading...</div></div>
        </div>`;
      const [stats, summary, status, messages] = await Promise.all([
        api('/api/stats').catch(() => ({})),
        api('/api/vulnerabilities/summary').catch(() => ({})),
        api('/api/agent/status').catch(() => ({connected:false})),
        api(`/api/agent/chat/${chatSession}/messages`).catch(() => []),
      ]);
      document.getElementById('chatSummary').innerHTML = `
        ${summaryLine('Servers', stats.total || 0)}${summaryLine('Hardened', stats.hardened || 0)}${summaryLine('Not hardened', stats.none || 0)}
        <hr style="border:0;border-top:1px solid var(--line);margin:18px 0">
        ${summaryLine('Critical CVEs', summary.critical || 0)}${summaryLine('High CVEs', summary.high || 0)}${summaryLine('Latest scan', timeAgo(summary.scanned_at))}
      `;
      document.getElementById('agentPill').innerHTML = pill(status.connected ? 'Online' : 'Offline', status.connected ? 'hardened' : 'error');
      document.getElementById('chatEvents').innerHTML = `<p>${esc(status.error || status.response || 'No server events yet.')}</p>`;
      renderMessages(messages);
    }
    function summaryLine(label, value) { return `<div style="display:flex;justify-content:space-between;margin:11px 0"><span>${esc(label)}</span><b>${esc(value)}</b></div>`; }
    function renderMessages(messages) {
      const node = document.getElementById('messages');
      node.innerHTML = messages.length ? messages.map(m => `<div class="bubble ${m.role === 'user' ? 'user' : ''}">${formatText(m.content)}</div>`).join('') : `<div class="empty">No messages in this session</div>`;
      node.scrollTop = node.scrollHeight;
    }
    async function sendChat() {
      const input = document.getElementById('chatText');
      const message = input.value.trim();
      if (!message) return;
      input.value = '';
      const node = document.getElementById('messages');
      node.innerHTML += `<div class="bubble user">${esc(message)}</div><div class="bubble" id="typing">...</div>`;
      node.scrollTop = node.scrollHeight;
      try {
        const result = await api('/api/agent/chat', {method:'POST', body:{message, session_id:chatSession}});
        document.getElementById('typing')?.remove();
        node.innerHTML += `<div class="bubble">${formatText(result.response || 'No response')}</div>`;
        node.scrollTop = node.scrollHeight;
      } catch (error) {
        document.getElementById('typing')?.remove();
        node.innerHTML += `<div class="bubble">Dashboard could not reach the agent runtime. ${esc(error.message)}</div>`;
      }
    }
    function formatText(text) {
      return esc(text || '').replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\n/g, '<br>');
    }

    render();
  </script>
</body>
</html>
"""


def register_dashboard_routes(app):
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/hardening", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/hardening/{server_id}", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/vulnerabilities", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/vulnerabilities/radar", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/vulnerabilities/{server_id}", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/agent-chat", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_app():
        return HTMLResponse(DASHBOARD_HTML)

    @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_fallback(full_path: str):
        reserved_prefixes = ("api/", "docs", "redoc", "openapi.json", "health", "ping")
        if full_path.startswith(reserved_prefixes):
            raise HTTPException(status_code=404, detail="Not found")
        return HTMLResponse(DASHBOARD_HTML)
