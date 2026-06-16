from __future__ import annotations


def render_chat_ui(service_name: str) -> str:
    return CHAT_UI_HTML.replace("__SERVICE_NAME__", service_name)


CHAT_UI_HTML = r"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Infra Log Sentinel</title>
  <style>
    :root {
      --bg: #f3f5f7;
      --nav: #111715;
      --nav-soft: #1b2420;
      --surface: #ffffff;
      --surface-soft: #f7f9fb;
      --surface-strong: #eef2f5;
      --line: #d9e0e5;
      --line-strong: #c5ced6;
      --text: #15201b;
      --muted: #63706a;
      --muted-strong: #44514b;
      --accent: #0f8b7d;
      --accent-strong: #08665c;
      --accent-soft: #e0f3ef;
      --blue: #315da8;
      --blue-soft: #e7eefb;
      --amber: #b7791f;
      --amber-soft: #fff2d2;
      --red: #bb241a;
      --red-soft: #fde7e5;
      --green: #1f7a4d;
      --green-soft: #e3f4eb;
      --purple: #6654b8;
      --purple-soft: #ece9fb;
      --code-bg: #0f1714;
      --code-head: #1c2a25;
      --code-text: #e9f8f2;
      --shadow: 0 16px 38px rgba(21, 32, 27, 0.09);
      --shadow-soft: 0 6px 18px rgba(21, 32, 27, 0.06);
      --radius: 8px;
    }

    * {
      box-sizing: border-box;
      min-width: 0;
    }

    html,
    body {
      margin: 0;
      height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
      overflow: hidden;
    }

    button,
    textarea,
    input,
    select {
      font: inherit;
    }

    button {
      letter-spacing: 0;
    }

    .app-shell {
      display: grid;
      grid-template-columns: 292px minmax(0, 1fr) 326px;
      height: 100vh;
      width: 100%;
      max-width: 100vw;
      overflow: hidden;
    }

    .nav {
      background: var(--nav);
      color: #eff6f3;
      border-right: 1px solid #202b27;
      padding: 20px 16px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      height: 100vh;
      overflow-y: auto;
      overscroll-behavior: contain;
    }

    .brand {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      padding-bottom: 4px;
    }

    .mark {
      width: 44px;
      height: 44px;
      border-radius: var(--radius);
      display: grid;
      place-items: center;
      background: #eff6f3;
      color: #0e1714;
      font-size: 15px;
      font-weight: 900;
      letter-spacing: 0;
    }

    .brand h1 {
      margin: 0;
      font-size: 17px;
      line-height: 1.15;
      font-weight: 850;
    }

    .brand p {
      margin: 4px 0 0;
      color: #9eb0a8;
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .nav-panel {
      border: 1px solid #26332e;
      border-radius: var(--radius);
      background: var(--nav-soft);
      padding: 12px;
    }

    .nav-title {
      margin: 0 0 10px;
      color: #9eb0a8;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .runtime-state {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .state-copy strong {
      display: block;
      font-size: 15px;
    }

    .state-copy span {
      display: block;
      margin-top: 2px;
      color: #9eb0a8;
      font-size: 12px;
    }

    .state-pill,
    .chip,
    .mini-chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 28px;
      border-radius: 999px;
      white-space: nowrap;
    }

    .state-pill {
      padding: 3px 9px;
      background: #20352e;
      color: #d8efe7;
      font-size: 12px;
      font-weight: 800;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--amber);
    }

    .dot.ok {
      background: #35c07e;
    }

    .dot.bad {
      background: #ff5a4f;
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .metric {
      min-height: 72px;
      border-radius: var(--radius);
      background: #19221f;
      border: 1px solid #26332e;
      padding: 10px;
    }

    .metric span {
      display: block;
      color: #98aaa2;
      font-size: 11px;
      margin-bottom: 8px;
    }

    .metric strong {
      display: block;
      color: #f7fbf9;
      font-size: 25px;
      line-height: 1;
    }

    .metric.critical strong {
      color: #ff7c72;
    }

    .metric.warning strong {
      color: #ffd36d;
    }

    .quick-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      width: 100%;
      max-width: 100%;
    }

    .quick {
      width: 100%;
      min-width: 0;
      min-height: 40px;
      border: 1px solid #2c3934;
      border-radius: var(--radius);
      background: #151d1a;
      color: #e8f0ed;
      display: grid;
      grid-template-columns: 24px minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      text-align: left;
      cursor: pointer;
    }

    .quick:hover {
      border-color: #4cb8a9;
      background: #1c2a25;
    }

    .quick .icon {
      width: 24px;
      height: 24px;
      display: grid;
      place-items: center;
      border-radius: 6px;
      background: #23332e;
      color: #9de4d9;
      font-weight: 850;
      font-size: 12px;
    }

    .quick span:last-child {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .nav-foot {
      margin-top: auto;
      color: #9eb0a8;
      font-size: 12px;
      line-height: 1.45;
    }

    .workspace {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-width: 0;
      height: 100vh;
      background: var(--bg);
      overflow: hidden;
    }

    .workspace-header {
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(16px);
      padding: 16px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      z-index: 5;
    }

    .title-block {
      min-width: 0;
    }

    .eyebrow {
      margin: 0 0 4px;
      color: var(--accent-strong);
      font-size: 11px;
      font-weight: 850;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .workspace-header h2 {
      margin: 0;
      font-size: 22px;
      line-height: 1.15;
      letter-spacing: 0;
    }

    .workspace-header small {
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
    }

    .header-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }

    .chip {
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--muted-strong);
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 750;
      box-shadow: var(--shadow-soft);
      max-width: 100%;
    }

    .chip strong {
      color: var(--text);
    }

    .conversation {
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 24px 22px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      overscroll-behavior: contain;
    }

    .conversation-inner {
      width: min(100%, 920px);
      max-width: 100%;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .rca-workspace {
      width: min(100%, 920px);
      max-width: 100%;
      margin: 0 auto 18px;
      border: 1px solid #b9d9d1;
      border-left: 4px solid var(--accent);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: var(--shadow-soft);
      overflow: hidden;
    }

    .rca-workspace-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: start;
      padding: 13px 15px;
      background: linear-gradient(90deg, #eefaf6 0%, #f8fbff 100%);
      border-bottom: 1px solid #d1e6df;
    }

    .rca-workspace-kicker {
      margin: 0 0 4px;
      color: var(--accent-strong);
      font-size: 11px;
      font-weight: 950;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .rca-workspace-title {
      margin: 0;
      font-size: 17px;
      line-height: 1.25;
      font-weight: 950;
    }

    .rca-confidence-pill {
      min-width: 72px;
      padding: 7px 10px;
      border: 1px solid #b8d8d1;
      border-radius: var(--radius);
      background: #ffffff;
      color: var(--accent-strong);
      text-align: center;
      font-size: 20px;
      font-weight: 950;
      line-height: 1;
    }

    .rca-confidence-pill span {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 10px;
      font-weight: 850;
      text-transform: uppercase;
    }

    .rca-workspace-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(160px, 0.55fr);
      gap: 10px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }

    .rca-field {
      display: grid;
      gap: 6px;
      color: var(--muted-strong);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .rca-field-hint {
      margin: -2px 0 0;
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      line-height: 1.35;
      letter-spacing: 0;
      text-transform: none;
    }

    .rca-field textarea,
    .rca-field input,
    .rca-field select {
      width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: var(--radius);
      background: #fbfcfd;
      color: var(--text);
      padding: 9px 10px;
      font-size: 13px;
      font-weight: 650;
      text-transform: none;
      letter-spacing: 0;
      outline: none;
    }

    .rca-field textarea {
      min-height: 76px;
      resize: vertical;
    }

    .rca-field input:focus,
    .rca-field select:focus,
    .rca-field textarea:focus {
      border-color: #64bbae;
      box-shadow: 0 0 0 3px rgba(15, 139, 125, 0.12);
    }

    .rca-field-stack {
      display: grid;
      gap: 10px;
    }

    .rca-workspace-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding: 0 12px 12px;
    }

    .rca-workspace-button {
      min-height: 36px;
      border: 1px solid #94c9be;
      border-radius: var(--radius);
      background: var(--accent);
      color: #ffffff;
      padding: 0 12px;
      font-size: 12px;
      font-weight: 950;
      cursor: pointer;
    }

    .rca-workspace-button.secondary {
      background: #ffffff;
      color: var(--accent-strong);
    }

    .rca-workspace-button.danger {
      background: #fff7ed;
      border-color: #fed7aa;
      color: #9a3412;
    }

    .rca-workspace-button:hover {
      filter: brightness(0.97);
    }

    .rca-workspace-button:disabled {
      cursor: wait;
      opacity: 0.6;
    }

    .rca-workspace-result {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
      padding: 0 12px 12px;
    }

    .rca-result-block {
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface-soft);
      padding: 10px;
    }

    .rca-result-block h4 {
      margin: 0 0 7px;
      color: var(--accent-strong);
      font-size: 11px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .rca-root-cause {
      margin: 0;
      font-size: 14px;
      line-height: 1.45;
      font-weight: 850;
    }

    .rca-scope-line {
      margin: 6px 0 0;
      color: var(--muted-strong);
      font-size: 12px;
      line-height: 1.35;
      font-weight: 700;
    }

    .rca-scope-line strong {
      color: var(--accent-strong);
      font-weight: 950;
    }

    .rca-compact-list {
      margin: 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 6px;
    }

    .rca-compact-list li {
      padding: 7px 8px;
      border-left: 3px solid #7fbfb3;
      border-radius: 6px;
      background: #ffffff;
      color: var(--muted-strong);
      font-size: 12px;
      line-height: 1.35;
    }

    .rca-command-list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }

    .rca-command-list .command-card {
      margin: 0;
      background: #ffffff;
    }

    .rca-focus-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-top: 8px;
    }

    .rca-focus-chips span {
      padding: 4px 7px;
      border: 1px solid #bddbd4;
      border-radius: 999px;
      background: #ffffff;
      color: var(--accent-strong);
      font-size: 11px;
      font-weight: 850;
    }

    .message {
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }

    .message.user {
      grid-template-columns: minmax(0, 1fr) 38px;
      margin-left: min(22%, 220px);
    }

    .avatar {
      width: 38px;
      height: 38px;
      border-radius: var(--radius);
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 900;
    }

    .message.user .avatar {
      grid-column: 2;
      background: #18231f;
      color: #ffffff;
      border-color: #18231f;
    }

    .bubble {
      min-width: 0;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      box-shadow: var(--shadow-soft);
      overflow-wrap: anywhere;
    }

    .message.user .bubble {
      grid-column: 1;
      grid-row: 1;
      background: #18231f;
      color: #ffffff;
      border-color: #18231f;
      padding: 13px 15px;
      line-height: 1.5;
      white-space: pre-wrap;
    }

    .message.agent.typing .bubble {
      padding: 14px 16px;
      color: var(--muted);
    }

    .answer {
      padding: 17px 18px;
      line-height: 1.58;
      overflow-wrap: anywhere;
      word-break: normal;
    }

    .answer > :first-child {
      margin-top: 0;
    }

    .answer > :last-child {
      margin-bottom: 0;
    }

    .answer-banner {
      margin: -2px 0 15px;
      display: grid;
      grid-template-columns: 40px minmax(0, 1fr);
      gap: 11px;
      align-items: start;
      padding: 12px 13px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      border-radius: var(--radius);
      background: #f8fbfa;
    }

    .answer.context-summary .answer-banner {
      border-left-color: var(--green);
      background: #f6fbf8;
    }

    .answer.context-runbook .answer-banner {
      border-left-color: var(--blue);
      background: #f6f9ff;
    }

    .answer.context-command .answer-banner {
      border-left-color: var(--purple);
      background: #f8f7ff;
    }

    .answer.context-clarify .answer-banner {
      border-left-color: var(--amber);
      background: #fffaf0;
    }

    .answer.context-action .answer-banner {
      border-left-color: var(--accent);
      background: #f5fbf9;
    }

    .answer-banner-icon {
      width: 40px;
      height: 40px;
      border-radius: var(--radius);
      display: grid;
      place-items: center;
      color: #ffffff;
      background: var(--accent);
      font-size: 12px;
      font-weight: 950;
      letter-spacing: 0.02em;
    }

    .answer.context-summary .answer-banner-icon {
      background: var(--green);
    }

    .answer.context-runbook .answer-banner-icon {
      background: var(--blue);
    }

    .answer.context-command .answer-banner-icon {
      background: var(--purple);
    }

    .answer.context-clarify .answer-banner-icon {
      background: var(--amber);
    }

    .answer-banner-kicker {
      margin: 0 0 3px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .answer-banner-title {
      margin: 0;
      color: var(--text);
      font-size: 16px;
      line-height: 1.25;
      font-weight: 900;
    }

    .answer-banner-subtitle {
      margin: 4px 0 0;
      color: var(--muted-strong);
      font-size: 13px;
      line-height: 1.45;
    }

    .answer-section-title {
      margin: 16px 0 8px;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 900;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .answer-section-title::before {
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: var(--accent);
    }

    .answer-field {
      margin: 8px 0;
      display: grid;
      grid-template-columns: minmax(130px, 190px) minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      padding: 10px 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface-soft);
    }

    .answer-field-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .answer-field-value {
      color: var(--text);
      font-weight: 720;
      overflow-wrap: anywhere;
    }

    .answer-chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      align-items: center;
    }

    .answer-mini-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 26px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #ffffff;
      color: var(--muted-strong);
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }

    .answer-mini-chip .chip-key {
      color: var(--muted);
      font-weight: 800;
    }

    .answer-mini-chip .chip-value {
      color: var(--text);
      font-weight: 950;
    }

    .answer-mini-chip.critical {
      border-color: #f3b9b5;
      background: var(--red-soft);
    }

    .answer-mini-chip.error {
      border-color: #f2c59e;
      background: #fce7d5;
    }

    .answer-mini-chip.warning {
      border-color: #f2d58a;
      background: var(--amber-soft);
    }

    .answer-mini-chip.info {
      border-color: #b9c9ed;
      background: var(--blue-soft);
    }

    .finding-card {
      margin: 10px 0;
      padding: 11px 12px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: 0 5px 14px rgba(21, 32, 27, 0.04);
    }

    .finding-card.critical {
      border-left-color: var(--red);
      background: #fff8f7;
    }

    .finding-card.error {
      border-left-color: #c86412;
      background: #fff9f4;
    }

    .finding-card.warning {
      border-left-color: var(--amber);
      background: #fffdf7;
    }

    .finding-card.info {
      border-left-color: var(--blue);
      background: #f8fbff;
    }

    .finding-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      align-items: center;
      margin-bottom: 7px;
    }

    .finding-index {
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
    }

    .finding-location {
      min-width: 0;
      color: var(--text);
      font-size: 13px;
      font-weight: 900;
      overflow-wrap: anywhere;
    }

    .finding-type {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface-soft);
      color: var(--muted-strong);
      font-size: 12px;
      font-weight: 850;
    }

    .finding-message {
      margin: 0;
      color: var(--muted-strong);
      line-height: 1.52;
    }

    .answer h2,
    .answer h3,
    .answer h4 {
      margin: 18px 0 9px;
      line-height: 1.25;
      letter-spacing: 0;
    }

    .answer h2 {
      font-size: 18px;
      color: var(--accent-strong);
      padding-bottom: 8px;
      border-bottom: 1px solid var(--line);
    }

    .answer h3 {
      font-size: 16px;
      color: var(--muted-strong);
    }

    .answer h4 {
      font-size: 14px;
      color: var(--blue);
    }

    .answer p {
      margin: 9px 0;
      overflow-wrap: anywhere;
    }

    .answer a {
      color: var(--blue);
      font-weight: 800;
    }

    .answer ul,
    .answer ol {
      margin: 8px 0 13px 22px;
      padding: 0;
    }

    .answer li {
      margin: 5px 0;
    }

    .answer strong {
      color: #0f1c18;
      font-weight: 850;
    }

    .inline-code {
      display: inline-block;
      max-width: 100%;
      padding: 1px 6px;
      border: 1px solid #c8d6d1;
      border-radius: 6px;
      background: #f2f7f5;
      color: #075f56;
      font-family: "Cascadia Mono", "Fira Code", Consolas, monospace;
      font-size: 0.92em;
      vertical-align: baseline;
    }

    .severity {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 850;
      letter-spacing: 0.02em;
    }

    .severity.critical {
      background: var(--red-soft);
      color: var(--red);
    }

    .severity.error {
      background: #fce7d5;
      color: #a94f0b;
    }

    .severity.warning {
      background: var(--amber-soft);
      color: var(--amber);
    }

    .severity.info {
      background: var(--blue-soft);
      color: var(--blue);
    }

    .code-block {
      margin: 13px 0;
      overflow: hidden;
      border: 1px solid #20312b;
      border-radius: var(--radius);
      background: var(--code-bg);
    }

    .code-head {
      min-height: 40px;
      padding: 7px 9px 7px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--code-head);
      color: #c9ded6;
      font-size: 12px;
      font-weight: 800;
      border-bottom: 1px solid #273a33;
    }

    .copy-button,
    .command-copy {
      min-height: 30px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 850;
    }

    .copy-button {
      border: 1px solid rgba(255, 255, 255, 0.18);
      background: rgba(255, 255, 255, 0.08);
      color: #ffffff;
      padding: 0 10px;
    }

    .copy-button:hover {
      background: rgba(255, 255, 255, 0.16);
    }

    .code-block pre {
      margin: 0;
      padding: 15px;
      overflow-x: auto;
    }

    .code-block code {
      color: var(--code-text);
      font-family: "Cascadia Mono", "Fira Code", Consolas, monospace;
      font-size: 13px;
      line-height: 1.55;
      white-space: pre;
    }

    .command-card {
      margin: 11px 0;
      border: 1px solid #bfd9d2;
      border-left: 4px solid var(--accent);
      border-radius: var(--radius);
      background: #f8fcfa;
      overflow: hidden;
    }

    .command-card.verify,
    .command-card.check {
      border-color: #bfd9d2;
      border-left-color: var(--accent);
    }

    .command-card.investigate,
    .command-card.analyze {
      border-color: #bcc9ea;
      border-left-color: var(--blue);
      background: #f8fbff;
    }

    .command-card.remediate,
    .command-card.fix {
      border-color: #f1b7b2;
      border-left-color: var(--red);
      background: #fff8f7;
    }

    .command-card.validate {
      border-color: #badbc8;
      border-left-color: var(--green);
      background: #f7fcf9;
    }

    .command-head {
      min-height: 40px;
      padding: 8px 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      background: var(--accent-soft);
      border-bottom: 1px solid #d2e7e1;
    }

    .command-card.investigate .command-head,
    .command-card.analyze .command-head {
      background: var(--blue-soft);
      border-bottom-color: #cbd8f2;
    }

    .command-card.remediate .command-head,
    .command-card.fix .command-head {
      background: var(--red-soft);
      border-bottom-color: #f0c4c0;
    }

    .command-card.validate .command-head {
      background: var(--green-soft);
      border-bottom-color: #cde7d8;
    }

    .phase {
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .command-card.investigate .phase,
    .command-card.analyze .phase {
      color: var(--blue);
    }

    .command-card.remediate .phase,
    .command-card.fix .phase {
      color: var(--red);
    }

    .command-card.validate .phase {
      color: var(--green);
    }

    .command-copy {
      border: 1px solid #91bdb4;
      background: #ffffff;
      color: var(--accent-strong);
      padding: 0 10px;
    }

    .command-copy:hover {
      background: #eef8f5;
    }

    .command-text {
      display: block;
      padding: 12px 13px;
      color: #10251e;
      font-family: "Cascadia Mono", "Fira Code", Consolas, monospace;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }

    .why {
      margin: -4px 0 9px 0;
      padding-left: 13px;
      color: var(--muted);
      font-size: 13px;
      border-left: 2px solid var(--line);
    }

    .answer table {
      width: 100%;
      border-collapse: collapse;
      margin: 13px 0;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      font-size: 13px;
    }

    .answer th,
    .answer td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }

    .answer th {
      background: #eef4f2;
      color: var(--accent-strong);
      font-weight: 850;
    }

    .answer tr:last-child td {
      border-bottom: 0;
    }

    .answer hr {
      border: 0;
      border-top: 1px solid var(--line);
      margin: 15px 0;
    }

    .composer {
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.9);
      padding: 14px 22px 18px;
      position: sticky;
      bottom: 0;
      z-index: 8;
    }

    .composer-shell {
      width: min(100%, 920px);
      margin: 0 auto;
      border: 1px solid var(--line-strong);
      border-radius: var(--radius);
      background: var(--surface);
      overflow: hidden;
      box-shadow: var(--shadow);
    }

    textarea {
      width: 100%;
      min-height: 78px;
      max-height: 180px;
      display: block;
      border: 0;
      outline: none;
      resize: vertical;
      padding: 15px 16px;
      color: var(--text);
      background: transparent;
    }

    .composer-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid var(--line);
      padding: 10px;
    }

    .composer-left {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .composer-link {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #ffffff;
      color: var(--accent-strong);
      min-height: 34px;
      padding: 0 11px;
      font-size: 12px;
      font-weight: 850;
      cursor: pointer;
    }

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      color: var(--muted);
      font-size: 13px;
      user-select: none;
    }

    .toggle input {
      accent-color: var(--accent);
    }

    .send {
      min-width: 96px;
      min-height: 40px;
      border: 0;
      border-radius: var(--radius);
      background: var(--accent);
      color: #ffffff;
      cursor: pointer;
      font-weight: 850;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }

    .send:hover {
      background: var(--accent-strong);
    }

    .send:disabled {
      cursor: wait;
      opacity: 0.68;
    }

    .insight-rail {
      border-left: 1px solid var(--line);
      background: #fbfcfd;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 0;
      height: 100vh;
      overflow: hidden;
      overscroll-behavior: contain;
    }

    .rail-tabs {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
      flex: 0 0 auto;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #eef3f2;
    }

    .rail-tab {
      min-width: 0;
      min-height: 36px;
      border: 0;
      border-radius: calc(var(--radius) - 2px);
      background: transparent;
      color: var(--muted-strong);
      cursor: pointer;
      font-size: 12px;
      font-weight: 950;
    }

    .rail-tab.is-active {
      background: var(--surface);
      color: var(--accent-strong);
      box-shadow: 0 1px 4px rgba(17, 24, 39, 0.08);
    }

    .rail-panel {
      flex: 1 1 auto;
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      padding-right: 4px;
      display: none;
      gap: 10px;
      overscroll-behavior: contain;
    }

    .rail-panel.is-active {
      display: flex;
      flex-direction: column;
      align-content: stretch;
    }

    .rail-section {
      flex: 0 0 auto;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      padding: 11px;
      box-shadow: var(--shadow-soft);
      min-height: 0;
    }

    .rail-section h3 {
      margin: 0 0 9px;
      font-size: 14px;
      letter-spacing: 0;
    }

    .rail-section.alerts-section {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .alerts-section .alert-list {
      max-height: 230px;
    }

    .insight-rail .rca-workspace {
      flex: 0 0 auto;
      width: 100%;
      margin: 0;
      box-shadow: var(--shadow-soft);
    }

    .insight-rail .rca-workspace-head {
      padding: 12px;
      grid-template-columns: minmax(0, 1fr);
    }

    .insight-rail .rca-confidence-pill {
      justify-self: start;
      min-width: 82px;
    }

    .insight-rail .rca-workspace-grid,
    .insight-rail .rca-workspace-result {
      grid-template-columns: 1fr;
    }

    .insight-rail .rca-workspace-result {
      max-height: 360px;
      overflow-y: auto;
      overscroll-behavior: contain;
    }

    .insight-rail .rca-workspace-actions {
      display: grid;
      grid-template-columns: 1fr;
    }

    .insight-rail .rca-workspace-button {
      width: 100%;
    }

    .alert-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-height: 0;
      overflow-y: auto;
      padding-right: 3px;
      overscroll-behavior: contain;
    }

    .alert-item {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 8px;
      background: var(--surface-soft);
    }

    .alert-item strong {
      display: block;
      margin: 5px 0 3px;
      font-size: 12px;
      line-height: 1.25;
    }

    .alert-item p {
      margin: 0;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }

    .rca-card {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .rca-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
    }

    .rca-head strong {
      display: block;
      color: var(--text);
      font-size: 13px;
      line-height: 1.25;
    }

    .rca-head small {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }

    .rca-confidence {
      min-width: 54px;
      padding: 5px 7px;
      border-radius: var(--radius);
      background: var(--blue-soft);
      color: var(--blue);
      text-align: center;
      font-size: 17px;
      line-height: 1;
      font-weight: 950;
    }

    .rca-cause {
      padding: 9px;
      border: 1px solid #cbd8f2;
      border-left: 3px solid var(--blue);
      border-radius: var(--radius);
      background: #f8fbff;
      color: var(--text);
      font-size: 12px;
      line-height: 1.4;
      font-weight: 760;
    }

    .rca-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .rca-list span {
      color: var(--muted);
      font-size: 10px;
      font-weight: 950;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    .rca-list p {
      margin: 0;
      padding: 7px 8px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface-soft);
      color: var(--muted-strong);
      font-size: 11px;
      line-height: 1.35;
    }

    .rca-action {
      width: 100%;
      min-height: 30px;
      border: 1px solid #8fc9bf;
      border-radius: var(--radius);
      background: var(--accent);
      color: #ffffff;
      font-size: 12px;
      font-weight: 950;
      cursor: pointer;
    }

    .rca-action:hover {
      background: var(--accent-strong);
    }

    .mini-chip {
      min-height: 22px;
      padding: 2px 7px;
      background: var(--surface-strong);
      color: var(--muted-strong);
      font-size: 11px;
      font-weight: 850;
    }

    .mini-chip.critical {
      background: var(--red-soft);
      color: var(--red);
    }

    .mini-chip.error {
      background: #fce7d5;
      color: #9a4f10;
    }

    .mini-chip.warning {
      background: var(--amber-soft);
      color: var(--amber);
    }

    .control-list,
    .facts {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .control-list {
      gap: 9px;
    }

    .runtime-control-card {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface-soft);
    }

    .runtime-control-card:focus-within {
      border-color: #8fc9bf;
      box-shadow: 0 0 0 3px rgba(15, 139, 125, 0.12);
    }

    .runtime-control-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 9px;
      min-width: 0;
    }

    .runtime-control-head strong {
      display: block;
      color: var(--text);
      font-size: 13px;
      line-height: 1.25;
    }

    .runtime-control-head small {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }

    .switch {
      width: 46px;
      height: 26px;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      background: #dfe6eb;
      padding: 2px;
      cursor: pointer;
      transition: background 0.16s ease, border-color 0.16s ease;
    }

    .switch span {
      display: block;
      width: 20px;
      height: 20px;
      border-radius: 999px;
      background: #ffffff;
      box-shadow: 0 2px 7px rgba(21, 32, 27, 0.18);
      transition: transform 0.16s ease;
    }

    .switch.is-on {
      border-color: #51aa86;
      background: #1f9d68;
    }

    .switch.is-on span {
      transform: translateX(20px);
    }

    .switch:disabled,
    .control-save:disabled {
      cursor: wait;
      opacity: 0.62;
    }

    .interval-control {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
    }

    .interval-control input {
      width: 100%;
      min-height: 34px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      padding: 6px 9px;
      font: inherit;
      font-size: 13px;
      outline: none;
    }

    .interval-control input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 139, 125, 0.12);
    }

    .control-save {
      min-height: 34px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #ffffff;
      cursor: pointer;
      padding: 0 11px;
      font-size: 12px;
      font-weight: 900;
    }

    .control-save:hover {
      background: var(--accent-strong);
    }

    .control-item,
    .fact {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      min-height: 28px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
    }

    .control-item:last-child,
    .fact:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }

    .control-item strong,
    .fact strong {
      color: var(--text);
      font-size: 13px;
      text-align: right;
      overflow-wrap: anywhere;
    }

    .control-badge {
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 850;
      color: var(--green);
      background: var(--green-soft);
    }

    .control-badge.live {
      color: var(--green);
      background: var(--green-soft);
    }

    .control-badge.off {
      color: var(--muted-strong);
      background: var(--surface-strong);
    }

    .control-badge.paused {
      color: var(--amber);
      background: var(--amber-soft);
    }

    .control-badge.dry-run,
    .control-badge.disabled {
      color: var(--amber);
      background: var(--amber-soft);
    }

    .control-badge.misconfigured,
    .control-badge.worker-down,
    .control-badge.error {
      color: var(--red);
      background: var(--red-soft);
    }

    .domain-bars {
      display: flex;
      flex-direction: column;
      gap: 7px;
    }

    .domain-row {
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr) 28px;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
    }

    .bar {
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: var(--surface-strong);
    }

    .bar span {
      display: block;
      height: 100%;
      width: 0;
      background: var(--accent);
    }

    .empty {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    @media (max-width: 1180px) {
      .app-shell {
        grid-template-columns: 280px minmax(0, 1fr);
      }

      .insight-rail {
        grid-column: 1 / -1;
        border-left: 0;
        border-top: 1px solid var(--line);
        height: min(58vh, 620px);
      }
    }

    @media (max-width: 860px) {
      .app-shell {
        grid-template-columns: 1fr;
        max-width: 100vw;
        overflow-x: hidden;
      }

      .nav {
        border-right: 0;
      }

      .quick-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .workspace-header {
        align-items: flex-start;
        flex-direction: column;
      }

      .header-actions {
        justify-content: flex-start;
      }

      .insight-rail {
        height: min(62vh, 640px);
      }
    }

    @media (max-width: 620px) {
      .app-shell,
      .nav,
      .workspace,
      .insight-rail,
      .workspace-header,
      .conversation,
      .composer {
        width: 100vw;
        max-width: 100vw;
        overflow-x: hidden;
      }

      .workspace {
        padding-right: 18px;
      }

      .workspace-header,
      .conversation,
      .composer {
        width: 100%;
        max-width: 100%;
      }

      .nav {
        gap: 12px;
        padding: 14px;
      }

      .runtime-state {
        align-items: flex-start;
        flex-direction: column;
      }

      .signal-panel,
      .nav-foot {
        display: none;
      }

      .quick-list {
        grid-template-columns: 1fr;
        overflow: hidden;
      }

      .quick-panel {
        overflow: hidden;
      }

      .quick {
        min-height: 36px;
        font-size: 14px;
      }

      .quick .icon {
        width: 22px;
        height: 22px;
      }

      .workspace-header {
        padding: 14px;
        max-width: 100vw;
        overflow-x: hidden;
      }

      .workspace-header h2 {
        font-size: 20px;
      }

      .workspace-header small,
      .title-block {
        max-width: 100%;
        overflow-wrap: anywhere;
      }

      .header-actions {
        width: 100%;
        max-width: calc(100vw - 28px);
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-start;
        padding-right: 8px;
      }

      .header-actions .chip {
        flex: 0 1 auto;
        min-width: 0;
        justify-content: center;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .header-actions .chip strong {
        display: inline-block;
        max-width: 112px;
        overflow: hidden;
        text-overflow: ellipsis;
        vertical-align: bottom;
      }

      .header-actions .chip:last-child {
        grid-column: auto;
      }

      .conversation {
        padding: 18px 12px;
        max-width: 100vw;
        overflow-x: hidden;
      }

      .conversation-inner,
      .composer-shell,
      .bubble,
      .answer {
        width: 100%;
        max-width: 100%;
      }

      .answer {
        padding: 16px;
      }

      .answer-banner,
      .answer-field {
        grid-template-columns: 1fr;
      }

      .answer-banner-icon {
        width: 34px;
        height: 34px;
      }

      .answer-field-label {
        margin-bottom: -3px;
      }

      .message,
      .message.user {
        grid-template-columns: 1fr;
        margin-left: 0;
        width: calc(100vw - 56px) !important;
        max-width: calc(100vw - 56px) !important;
        overflow: hidden;
      }

      .avatar {
        display: none;
      }

      .message.user .bubble {
        grid-column: 1;
      }

      .message.agent .bubble,
      .message.user .bubble {
        width: 100% !important;
        max-width: 100% !important;
      }

      .composer {
        padding: 12px;
      }
    }

    /* Dashboard-aligned visual shell. Keep IDs and JavaScript contracts intact. */
    :root {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-soft: #f1f5f9;
      --surface-strong: #e9eef5;
      --line: #d8dee8;
      --line-strong: #c7d0de;
      --text: #172033;
      --muted: #667085;
      --muted-strong: #475467;
      --accent: #0f766e;
      --accent-strong: #0f5f59;
      --accent-soft: #e6f6f3;
      --blue: #1d5fd0;
      --blue-soft: #eff6ff;
      --amber: #d97706;
      --amber-soft: #fff7e6;
      --red: #dc2626;
      --red-soft: #fff1f1;
      --green: #059669;
      --green-soft: #ecfdf5;
      --purple: #6d5bd0;
      --purple-soft: #f1efff;
      --code-bg: #111827;
      --code-head: #1f2937;
      --code-text: #f8fafc;
      --shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
      --shadow-soft: 0 4px 16px rgba(15, 23, 42, 0.06);
      --radius: 8px;
    }

    body {
      background: var(--bg);
      color: var(--text);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0 0 auto;
      height: 220px;
      pointer-events: none;
      z-index: -1;
      background: linear-gradient(180deg, #eff6ff 0%, rgba(239, 246, 255, 0) 100%);
      border-bottom: 1px solid #dbeafe;
    }

    .app-shell {
      display: grid;
      grid-template-areas:
        "nav workspace rail";
      grid-template-columns: 306px minmax(0, 1fr) 380px;
      grid-template-rows: minmax(0, 1fr);
      gap: 0;
      height: 100vh;
      background: transparent;
      overflow: hidden;
    }

    .nav {
      grid-area: nav;
      height: auto;
      max-height: none;
      display: grid;
      grid-template-columns: 1fr;
      align-items: stretch;
      gap: 14px;
      padding: 20px 16px;
      overflow-y: auto;
      overflow-x: hidden;
      color: var(--text);
      background: rgba(248, 250, 252, 0.92);
      border: 0;
      border-right: 1px solid var(--line);
      box-shadow: none;
      backdrop-filter: blur(14px);
      align-content: start;
    }

    .brand {
      display: grid;
      grid-template-columns: 40px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      align-self: start;
      padding: 0;
    }

    .mark {
      width: 40px;
      height: 40px;
      border: 1px solid #bfdbfe;
      border-radius: var(--radius);
      background: var(--blue-soft);
      color: var(--blue);
      font-size: 13px;
      font-weight: 850;
      box-shadow: none;
    }

    .brand h1 {
      color: var(--text);
      font-size: 15px;
      line-height: 1.2;
      font-weight: 760;
    }

    .brand p {
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
    }

    .nav-panel {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      padding: 12px;
      box-shadow: var(--shadow-soft);
    }

    .nav-title {
      margin: 0 0 9px;
      color: var(--muted);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.1em;
    }

    .runtime-panel {
      align-self: stretch;
    }

    .runtime-state {
      align-items: center;
    }

    .state-copy strong {
      color: var(--text);
      font-size: 15px;
      font-weight: 760;
    }

    .state-copy span {
      color: var(--muted);
      font-size: 12px;
    }

    .state-pill {
      border: 1px solid #bbf7d0;
      background: var(--green-soft);
      color: #047857;
      font-weight: 760;
    }

    .signal-panel {
      min-width: 0;
    }

    .metric-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .metric {
      min-height: 58px;
      border: 1px solid var(--line);
      border-left: 4px solid #64748b;
      border-radius: var(--radius);
      background: #ffffff;
      padding: 9px 10px;
      box-shadow: none;
    }

    .metric span {
      margin-bottom: 5px;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .metric strong {
      color: var(--text);
      font-size: 23px;
      font-weight: 760;
    }

    .metric.critical {
      border-left-color: var(--red);
      background: #fffafa;
    }

    .metric.critical strong {
      color: var(--red);
    }

    .metric.warning {
      border-left-color: var(--amber);
      background: #fffdf6;
    }

    .metric.warning strong {
      color: var(--amber);
    }

    .quick-panel {
      min-width: 0;
    }

    .quick-list {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }

    .quick {
      min-height: 34px;
      border: 1px solid transparent;
      border-radius: var(--radius);
      background: var(--surface-soft);
      color: var(--muted-strong);
      grid-template-columns: 24px minmax(0, 1fr);
      padding: 6px 8px;
      font-size: 12px;
      font-weight: 650;
      transition: border-color 150ms ease, background 150ms ease, color 150ms ease;
    }

    .quick:hover {
      border-color: #bfdbfe;
      background: var(--blue-soft);
      color: var(--blue);
    }

    .quick .icon {
      background: #ffffff;
      color: var(--blue);
      border: 1px solid #dbeafe;
      font-weight: 800;
    }

    .nav-foot {
      display: block;
      margin-top: auto;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .workspace {
      grid-area: workspace;
      height: auto;
      min-height: 0;
      border-right: 1px solid var(--line);
      background: transparent;
    }

    .workspace-header {
      border-bottom: 1px solid var(--line);
      background: rgba(248, 250, 252, 0.88);
      padding: 18px 24px;
      backdrop-filter: blur(12px);
    }

    .eyebrow {
      color: var(--blue);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.1em;
    }

    .workspace-header h2 {
      color: var(--text);
      font-size: 24px;
      font-weight: 760;
    }

    .workspace-header small {
      color: var(--muted);
      font-size: 13px;
    }

    .chip {
      min-height: 30px;
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--muted);
      border-radius: 999px;
      box-shadow: none;
      font-weight: 650;
    }

    .chip strong {
      color: var(--text);
      font-weight: 760;
    }

    .conversation {
      padding: 24px;
      background: rgba(248, 250, 252, 0.72);
    }

    .conversation-inner,
    .composer-shell {
      width: min(100%, 980px);
    }

    .message {
      grid-template-columns: 36px minmax(0, 1fr);
      gap: 10px;
    }

    .message.user {
      grid-template-columns: minmax(0, 1fr) 36px;
      margin-left: min(18%, 180px);
    }

    .avatar {
      width: 36px;
      height: 36px;
      border-radius: var(--radius);
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--blue);
      box-shadow: var(--shadow-soft);
    }

    .message.user .avatar {
      background: var(--blue);
      border-color: var(--blue);
      color: #ffffff;
    }

    .bubble {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: var(--shadow-soft);
    }

    .message.user .bubble {
      background: var(--blue);
      border-color: var(--blue);
      color: #ffffff;
    }

    .answer-banner {
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      border-radius: var(--radius);
      background: #f8fbff;
      box-shadow: none;
    }

    .answer.context-summary .answer-banner {
      border-left-color: var(--green);
      background: #f7fefb;
    }

    .answer.context-action .answer-banner,
    .answer.context-clarify .answer-banner {
      border-left-color: var(--accent);
      background: #f7fdfb;
    }

    .answer-banner-icon {
      border-radius: var(--radius);
      background: var(--blue);
    }

    .answer.context-summary .answer-banner-icon {
      background: var(--green);
    }

    .answer.context-action .answer-banner-icon,
    .answer.context-clarify .answer-banner-icon {
      background: var(--accent);
    }

    .answer-section-title {
      color: var(--blue);
    }

    .answer-section-title::before {
      background: var(--blue);
    }

    .finding-card,
    .answer-field,
    .rca-result-block {
      border-color: var(--line);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: none;
    }

    .composer {
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
      padding: 14px 24px 18px;
      backdrop-filter: blur(14px);
    }

    .composer-shell {
      border: 1px solid var(--line-strong);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: var(--shadow-soft);
    }

    .composer-shell:focus-within {
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(29, 95, 208, 0.13);
    }

    .composer-link,
    .control-save,
    .rca-workspace-button.secondary,
    .rca-workspace-button.danger {
      border-radius: var(--radius);
    }

    .send {
      border-radius: var(--radius);
      background: var(--blue);
      box-shadow: none;
    }

    .send:hover {
      background: #174ea8;
    }

    .toggle {
      color: var(--muted-strong);
    }

    .insight-rail {
      grid-area: rail;
      min-height: 0;
      height: auto;
      border-left: 0;
      background: rgba(255, 255, 255, 0.82);
      padding: 16px;
      overflow: hidden;
    }

    .rail-tabs {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface-soft);
      padding: 4px;
    }

    .rail-tab {
      border-radius: 6px;
      color: var(--muted);
      font-weight: 720;
    }

    .rail-tab.is-active {
      color: var(--blue);
      background: #ffffff;
      box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
    }

    .rail-section {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: var(--shadow-soft);
    }

    .rail-section h3 {
      color: var(--text);
      font-weight: 760;
    }

    .alert-item {
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: none;
    }

    .alert-item:has(.mini-chip.critical) {
      border-left-color: var(--red);
    }

    .alert-item:has(.mini-chip.error) {
      border-left-color: #ea580c;
    }

    .alert-item:has(.mini-chip.warning) {
      border-left-color: var(--amber);
    }

    .runtime-control-card {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: none;
    }

    .runtime-control-card:focus-within {
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(29, 95, 208, 0.12);
    }

    .switch {
      background: var(--surface-strong);
    }

    .switch[aria-checked="true"] {
      background: var(--blue);
    }

    .control-badge.live {
      border-color: #bfdbfe;
      background: var(--blue-soft);
      color: var(--blue);
    }

    .fact,
    .domain-row {
      border-radius: var(--radius);
      background: var(--surface-soft);
    }

    .bar {
      background: #e2e8f0;
    }

    .bar span {
      background: var(--blue);
    }

    .insight-rail .rca-workspace {
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      border-radius: var(--radius);
      background: #ffffff;
      box-shadow: var(--shadow-soft);
    }

    .rca-workspace-head {
      background: linear-gradient(90deg, #f0fdfa 0%, #f8fbff 100%);
      border-bottom-color: #ccfbf1;
    }

    .rca-workspace-kicker,
    .rca-result-block h4 {
      color: var(--accent-strong);
    }

    .rca-confidence-pill {
      border-color: #99f6e4;
      border-radius: var(--radius);
      background: #ffffff;
      color: var(--accent-strong);
    }

    .rca-field textarea,
    .rca-field input,
    .rca-field select,
    .interval-control input {
      border-color: var(--line-strong);
      border-radius: var(--radius);
      background: #fbfdff;
    }

    .rca-field input:focus,
    .rca-field select:focus,
    .rca-field textarea:focus,
    .interval-control input:focus {
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(29, 95, 208, 0.12);
    }

    .rca-workspace-button {
      border-color: var(--accent);
      border-radius: var(--radius);
      background: var(--accent);
    }

    .rca-workspace-button.secondary {
      border-color: #99f6e4;
      background: #ffffff;
      color: var(--accent-strong);
    }

    .rca-workspace-button.danger {
      border-color: #fed7aa;
      background: #fff7ed;
      color: #9a3412;
    }

    .workspace-menu {
      display: grid;
      gap: 8px;
    }

    .view-link {
      width: 100%;
      min-height: 54px;
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      border: 1px solid transparent;
      border-radius: var(--radius);
      background: var(--surface-soft);
      color: var(--muted-strong);
      padding: 8px;
      text-align: left;
      cursor: pointer;
      transition: border-color 150ms ease, background 150ms ease, color 150ms ease;
    }

    .view-link:hover,
    .view-link.is-active {
      border-color: #bfdbfe;
      background: var(--blue-soft);
      color: var(--blue);
    }

    .view-link strong,
    .view-link small {
      display: block;
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .view-link strong {
      color: inherit;
      font-size: 13px;
      font-weight: 760;
    }

    .view-link small {
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 550;
    }

    .view-icon {
      width: 32px;
      height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #dbeafe;
      border-radius: var(--radius);
      background: #ffffff;
      color: var(--blue);
      font-size: 12px;
      font-weight: 850;
    }

    .workspace-view {
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      display: none;
      padding: 24px;
      background: rgba(248, 250, 252, 0.72);
    }

    body[data-view="dashboard"] .workspace {
      grid-column: 2 / 4;
      grid-row: 1;
      grid-template-rows: auto minmax(0, 1fr);
      border-right: 0;
    }

    body[data-view="dashboard"] #view-dashboard {
      display: block;
    }

    body[data-view="dashboard"] .conversation,
    body[data-view="dashboard"] .composer,
    body[data-view="dashboard"] .insight-rail {
      display: none;
    }

    body[data-view="chat"] .workspace {
      grid-column: 2 / 4;
      grid-row: 1;
      border-right: 0;
    }

    body[data-view="chat"] #view-dashboard {
      display: none;
    }

    body[data-view="chat"] .conversation {
      display: flex;
    }

    body[data-view="chat"] .composer {
      display: block;
    }

    body[data-view="chat"] .insight-rail {
      display: none;
    }

    body[data-view="setting"] .workspace {
      display: none;
    }

    body[data-view="setting"] .insight-rail {
      grid-column: 2 / 4;
      grid-row: 1;
      display: flex;
      height: 100vh;
      padding: 22px 24px;
      background: rgba(248, 250, 252, 0.72);
      overflow: hidden;
    }

    body[data-view="setting"] .rail-tabs,
    body[data-view="setting"] #rail-panel-rca,
    body[data-view="setting"] .alerts-section,
    body[data-view="setting"] .environment-section,
    body[data-view="setting"] .domain-section {
      display: none !important;
    }

    body[data-view="setting"] #rail-panel-sentinel {
      width: min(100%, 1080px);
      margin: 0 auto;
      padding-right: 0;
      display: flex;
    }

    body[data-view="setting"] .runtime-section {
      display: block;
      padding: 18px;
    }

    body[data-view="setting"] .runtime-section h3 {
      margin-bottom: 14px;
      font-size: 18px;
    }

    body[data-view="setting"] .runtime-section .control-list {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    body[data-view="setting"] .runtime-control-card {
      min-height: 124px;
    }

    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(360px, 1.12fr) minmax(340px, 0.88fr);
      gap: 16px;
      align-items: start;
    }

    .dashboard-card {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #ffffff;
      padding: 16px;
      box-shadow: var(--shadow-soft);
    }

    .dashboard-card-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 14px;
    }

    .dashboard-card-head h3 {
      margin: 3px 0 0;
      color: var(--text);
      font-size: 16px;
      font-weight: 760;
      line-height: 1.25;
    }

    .dashboard-posture-card {
      min-height: 190px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      border-left: 4px solid var(--blue);
    }

    .dashboard-posture-copy {
      display: grid;
      gap: 6px;
    }

    .dashboard-posture-copy strong {
      color: var(--text);
      font-size: 34px;
      line-height: 1;
      font-weight: 780;
    }

    .dashboard-posture-copy span {
      color: var(--muted);
      font-size: 14px;
    }

    .dashboard-metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }

    .dashboard-metric-grid .metric {
      min-height: 84px;
    }

    .dashboard-wide-card {
      grid-column: 1 / -1;
    }

    .dashboard-view .alert-list,
    .dashboard-view .domain-bars {
      display: grid;
      gap: 10px;
    }

    .dashboard-view .alert-list {
      max-height: 360px;
      overflow-y: auto;
      padding-right: 4px;
    }

    .dashboard-view .facts {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    @media (max-width: 1280px) {
      .app-shell {
        grid-template-areas:
          "nav"
          "workspace"
          "rail";
        grid-template-columns: 1fr;
        grid-template-rows: auto minmax(640px, 1fr) minmax(420px, 48vh);
        overflow-y: auto;
      }

      .nav {
        grid-template-columns: minmax(220px, 0.9fr) minmax(240px, 1fr);
      }

      .quick-panel {
        grid-column: 1 / -1;
      }

      .workspace,
      .insight-rail {
        min-height: 0;
      }

      .workspace {
        border-right: 0;
      }

      .insight-rail {
        border-top: 1px solid var(--line);
      }
    }

    @media (max-width: 760px) {
      html,
      body {
        overflow: auto;
      }

      .app-shell,
      .nav,
      .workspace,
      .insight-rail,
      .workspace-header,
      .conversation,
      .composer {
        width: 100%;
        max-width: 100vw;
        overflow-x: hidden;
      }

      .app-shell {
        height: auto;
        min-height: 100vh;
        grid-template-rows: auto auto auto;
      }

      .nav {
        grid-template-columns: 1fr;
        padding: 12px;
      }

      .metric-grid,
      .quick-list {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .workspace {
        height: auto;
        min-height: 680px;
        padding-right: 0;
      }

      .workspace-header {
        padding: 16px 14px;
      }

      .conversation {
        min-height: 520px;
        padding: 16px 12px;
      }

      .conversation-inner,
      .composer-shell {
        width: 100%;
      }

      .message,
      .message.user {
        width: 100%;
        margin-left: 0;
        margin-right: 0;
      }

      .bubble,
      .answer {
        width: 100%;
        max-width: 100%;
      }

      .answer-banner {
        grid-template-columns: 40px minmax(0, 1fr);
      }

      .composer {
        padding: 12px;
      }

      .insight-rail {
        height: auto;
        padding: 12px;
      }
    }

    @media (max-width: 480px) {
      .app-shell {
        display: block;
      }

      .nav,
      .workspace,
      .insight-rail {
        display: block;
        min-width: 0;
      }

      .metric-grid,
      .quick-list {
        grid-template-columns: 1fr;
      }

      .workspace-header h2 {
        font-size: 22px;
      }

      .header-actions {
        justify-content: flex-start;
      }

      .message,
      .message.user {
        display: block;
      }

      .avatar,
      .message.user .avatar {
        display: none;
      }

      .bubble {
        display: block;
        max-width: calc(100vw - 24px);
      }

      .answer-banner {
        display: flex;
        align-items: flex-start;
        gap: 10px;
      }

      .answer-banner > div:last-child {
        flex: 1 1 auto;
        min-width: 0;
      }

      .answer-field {
        grid-template-columns: 1fr;
      }
    }
    /* GreenNode playground-inspired desktop shell. */
    :root {
      --blue: #2f9442;
      --blue-soft: #eaf6ed;
      --accent: #197a35;
      --accent-strong: #14642c;
      --accent-soft: #e8f5ec;
      --line: #dcdfe3;
      --line-strong: #cfd4da;
      --surface-soft: #f5f6f7;
      --text: #111827;
      --muted: #6b7280;
      --muted-strong: #4b5563;
      --shadow-soft: none;
      --radius: 4px;
    }

    body {
      background: #ffffff;
    }

    body::before {
      display: none;
    }

    .app-shell {
      grid-template-areas:
        "nav panel workspace";
      grid-template-columns: 225px 315px minmax(0, 1fr);
      grid-template-rows: minmax(0, 1fr);
      height: 100vh;
      background: #ffffff;
      overflow: hidden;
    }

    .platform-topbar {
      grid-area: topbar;
      display: grid;
      grid-template-columns: auto auto minmax(260px, 300px) minmax(0, 1fr) auto auto auto auto;
      align-items: center;
      gap: 8px;
      height: 49px;
      padding: 0 18px;
      background: #0f1512;
      border-top: 4px solid #0a7892;
      color: #f8fafc;
    }

    .platform-logo {
      color: #ffffff;
      font-size: 20px;
      font-weight: 850;
      letter-spacing: 0;
    }

    .platform-logo span {
      color: #20b455;
    }

    .top-region,
    .top-search,
    .top-credits,
    .top-help,
    .top-language,
    .top-account {
      height: 28px;
      display: inline-flex;
      align-items: center;
      border-radius: 4px;
      color: #e5e7eb;
      font-size: 13px;
      line-height: 1;
    }

    .top-region {
      gap: 8px;
      padding: 0 12px;
      background: rgba(255, 255, 255, 0.16);
    }

    .top-region span,
    .top-credits span {
      color: #b9c0c7;
      font-weight: 700;
    }

    .top-search {
      justify-content: space-between;
      gap: 12px;
      padding: 0 12px;
      background: rgba(255, 255, 255, 0.18);
      color: #b9c0c7;
    }

    .top-search strong {
      color: #9ca3af;
      font-size: 14px;
    }

    .top-credits {
      height: 45px;
      flex-direction: column;
      justify-content: center;
      align-items: flex-start;
      padding: 0 20px;
      border-left: 1px solid rgba(255, 255, 255, 0.14);
      border-right: 1px solid rgba(255, 255, 255, 0.14);
    }

    .top-credits strong {
      color: #ffffff;
      font-size: 13px;
    }

    .top-help {
      width: 28px;
      justify-content: center;
      border: 1px solid rgba(255, 255, 255, 0.24);
      border-radius: 50%;
      font-weight: 800;
    }

    .top-language {
      gap: 6px;
      padding: 0 10px;
      color: #ffffff;
      font-weight: 700;
    }

    .top-account {
      gap: 8px;
      padding-left: 14px;
      border-left: 1px solid rgba(255, 255, 255, 0.14);
      color: #ffffff;
    }

    .top-account span {
      width: 24px;
      height: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #ffffff;
      color: #111827;
      font-weight: 850;
    }

    .nav {
      grid-area: nav;
      grid-column: 1 / 2;
      grid-row: 1 / 2;
      height: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 10px 11px;
      background: #f7f7f8;
      border-right: 1px solid var(--line);
      box-shadow: none;
      backdrop-filter: none;
    }

    .nav .brand {
      min-height: 46px;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 10px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: #ffffff;
    }

    .nav .mark {
      width: 24px;
      height: 24px;
      border-color: #cdebd4;
      background: #effaf2;
      color: #20a34a;
      font-size: 10px;
    }

    .nav .brand h1 {
      font-size: 15px;
      font-weight: 760;
    }

    .nav .brand p {
      display: none;
    }

    .nav-panel,
    .workspace-menu-panel,
    .quick-panel {
      border: 0;
      border-radius: 0;
      background: transparent;
      padding: 0;
      box-shadow: none;
    }

    .nav-title {
      margin: 16px 9px 8px;
      color: #9aa0a6;
      font-size: 12px;
      font-weight: 760;
      letter-spacing: 0;
      text-transform: none;
    }

    .workspace-menu,
    .quick-list {
      gap: 2px;
    }

    .view-link,
    .quick {
      min-height: 36px;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 8px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: #4b5563;
      padding: 6px 9px;
      font-size: 13px;
      font-weight: 650;
    }

    .view-link:hover,
    .view-link.is-active,
    .quick:hover {
      border-color: transparent;
      background: #e8f3ea;
      color: #23883a;
    }

    .view-link small {
      display: none;
    }

    .view-icon,
    .quick .icon {
      width: 22px;
      height: 22px;
      border: 0;
      border-radius: 4px;
      background: transparent;
      color: currentColor;
      font-size: 11px;
    }

    .nav .runtime-panel,
    .nav .signal-panel,
    .nav-foot {
      display: none;
    }

    .workspace {
      min-height: 0;
      height: auto;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      border-right: 0;
      background: #ffffff;
      overflow: hidden;
    }

    .workspace-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      padding: 12px 30px 9px;
      border-bottom: 1px solid #ebeef2;
      background: #ffffff;
      backdrop-filter: none;
    }

    .workspace-header .eyebrow {
      margin-bottom: 2px;
      color: #7a818a;
      font-size: 12px;
      font-weight: 650;
      letter-spacing: 0;
      text-transform: none;
    }

    .workspace-header h2 {
      color: #111827;
      font-size: 28px;
      line-height: 1.05;
      font-weight: 780;
    }

    .workspace-header small {
      color: #777f89;
      font-size: 13px;
    }

    .header-actions {
      align-items: center;
      padding-top: 20px;
    }

    .chip {
      min-height: 30px;
      border-color: #d9dde2;
      border-radius: 6px;
      background: #ffffff;
      color: #65707c;
      box-shadow: none;
    }

    .model-type-tabs {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 14px 30px;
      border-bottom: 1px solid #ebeef2;
      background: #ffffff;
      overflow: hidden;
    }

    .model-type-tabs > strong {
      margin-right: 12px;
      color: #111827;
      font-size: 13px;
      font-weight: 780;
      white-space: nowrap;
    }

    .mode-tab {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #e0e4e8;
      border-radius: 4px;
      background: #f8f9fa;
      color: #4b5563;
      padding: 0 12px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }

    .mode-tab:hover,
    .mode-tab.is-active {
      border-color: #c8d0d8;
      background: #ffffff;
      color: #111827;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
    }

    body[data-view="dashboard"] .workspace {
      grid-column: 2 / 4;
      grid-row: 1 / 2;
      grid-template-rows: auto auto minmax(0, 1fr);
      border-right: 0;
    }

    body[data-view="dashboard"] .insight-rail {
      display: none;
    }

    body[data-view="dashboard"] #view-dashboard {
      display: block;
    }

    .workspace-view {
      padding: 18px 30px 26px;
      background: #ffffff;
    }

    .dashboard-grid {
      grid-template-columns: minmax(380px, 1.05fr) minmax(360px, 0.95fr);
      gap: 16px;
    }

    .dashboard-card,
    .rail-section,
    .runtime-control-card,
    .insight-rail .rca-workspace,
    .composer-shell,
    .bubble {
      border-color: #dfe3e8;
      border-radius: 4px;
      box-shadow: none;
    }

    .dashboard-card {
      padding: 18px 20px;
    }

    .dashboard-card-head h3,
    .rail-section h3 {
      color: #111827;
      font-size: 15px;
    }

    .dashboard-posture-card {
      min-height: 188px;
      border-left-color: #2f9442;
    }

    .dashboard-posture-copy strong {
      font-size: 32px;
    }

    .dashboard-metric-grid .metric {
      min-height: 84px;
      border-radius: 6px;
    }

    body[data-view="chat"] .insight-rail {
      grid-column: 2 / 3;
      grid-row: 1 / 2;
      display: flex;
      height: auto;
      min-height: 0;
      padding: 14px;
      border-right: 1px solid var(--line);
      border-left: 0;
      background: #ffffff;
      overflow: hidden;
    }

    body[data-view="chat"] .workspace {
      grid-column: 3 / 4;
      grid-row: 1 / 2;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      border-right: 0;
    }

    body[data-view="chat"] .settings-page-head {
      display: none;
    }

    body[data-view="chat"] .rail-tabs {
      flex: 0 0 auto;
      border-color: #e0e4e8;
      border-radius: 4px;
      background: #f8f9fa;
    }

    body[data-view="chat"] .rail-panel {
      padding-right: 0;
    }

    body[data-view="chat"] .conversation {
      margin: 0 30px;
      padding: 18px 20px;
      border: 1px solid #dfe3e8;
      border-bottom: 0;
      background: #ffffff;
    }

    body[data-view="chat"] .conversation-inner,
    body[data-view="chat"] .composer-shell {
      width: min(100%, 1180px);
      max-width: none;
    }

    body[data-view="chat"] .composer {
      margin: 0 30px 14px;
      padding: 16px 20px 20px;
      border: 1px solid #dfe3e8;
      border-top: 0;
      background: #ffffff;
    }

    body[data-view="setting"] .workspace {
      display: none;
    }

    body[data-view="setting"] .insight-rail {
      grid-column: 2 / 4;
      grid-row: 1 / 2;
      display: flex;
      height: auto;
      min-height: 0;
      padding: 26px 30px;
      border-left: 0;
      background: #ffffff;
    }

    .settings-page-head {
      display: none;
      margin: 0 auto 14px;
      width: min(100%, 1080px);
    }

    body[data-view="setting"] .settings-page-head {
      display: block;
    }

    .settings-page-head h2 {
      margin: 2px 0 4px;
      color: #111827;
      font-size: 28px;
      line-height: 1.05;
      font-weight: 780;
    }

    .settings-page-head small {
      color: #777f89;
      font-size: 13px;
    }

    body[data-view="setting"] #rail-panel-sentinel {
      width: min(100%, 1080px);
    }

    body[data-view="setting"] .runtime-section {
      border-radius: 4px;
      padding: 20px;
    }

    body[data-view="setting"] .runtime-section .control-list {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .send,
    .rca-workspace-button {
      border-color: #2f9442;
      background: #2f9442;
    }

    .send:hover,
    .rca-workspace-button:hover {
      background: #237a34;
    }

    .switch[aria-checked="true"] {
      background: #2f9442;
    }

    .control-badge.live,
    .state-pill {
      border-color: #bde8c8;
      background: #edfaf0;
      color: #197a35;
    }

    /* Left navigation is the source of truth: each view owns the full content frame. */
    body[data-view="chat"] .insight-rail {
      display: none !important;
    }

    body[data-view="chat"] .workspace {
      grid-column: 2 / 4;
      grid-row: 1 / 2;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      border-right: 0;
    }

    body[data-view="chat"] .conversation {
      margin: 0 30px;
      padding: 18px 20px;
      border: 1px solid #dfe3e8;
      border-bottom: 0;
      background: #ffffff;
    }

    body[data-view="chat"] .conversation-inner,
    body[data-view="chat"] .composer-shell {
      width: min(100%, 1180px);
      max-width: none;
      margin-left: auto;
      margin-right: auto;
    }

    body[data-view="chat"] .composer {
      margin: 0 30px 14px;
      padding: 16px 20px 20px;
      border: 1px solid #dfe3e8;
      border-top: 0;
      background: #ffffff;
    }

    .model-type-tabs {
      display: none !important;
    }

    body[data-view="dashboard"] .workspace {
      grid-template-rows: auto minmax(0, 1fr);
    }

    body[data-view="dashboard"] .dashboard-environment-card {
      display: none;
    }

    body[data-view="dashboard"] .dashboard-alert-card {
      grid-column: 1 / -1;
    }

    body[data-view="chat"] .workspace {
      grid-template-rows: auto minmax(0, 1fr) auto;
    }

    body[data-view="setting"] #rail-panel-sentinel {
      display: grid !important;
      gap: 14px;
      align-content: start;
      grid-auto-rows: max-content;
    }

    body[data-view="setting"] .environment-section {
      display: block !important;
    }

    body[data-view="setting"] .runtime-section,
    body[data-view="setting"] .environment-section {
      align-self: start;
      min-height: 0;
    }

    body[data-view="setting"] .environment-section .facts {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    body[data-view="rca"] .workspace {
      display: none;
    }

    body[data-view="rca"] .insight-rail {
      grid-column: 2 / 4;
      grid-row: 1 / 2;
      display: flex;
      height: auto;
      min-height: 0;
      padding: 26px 30px;
      border-left: 0;
      background: #ffffff;
    }

    body[data-view="rca"] .settings-page-head,
    body[data-view="rca"] .rail-tabs,
    body[data-view="rca"] #rail-panel-sentinel {
      display: none !important;
    }

    body[data-view="rca"] #rail-panel-rca {
      width: min(100%, 1080px);
      margin: 0 auto;
      padding-right: 0;
      display: flex !important;
    }

    body[data-view="rca"] .rca-workspace {
      width: 100%;
    }

    body[data-view="rca"] .insight-rail {
      padding: 0;
      overflow: hidden;
    }

    body[data-view="rca"] #rail-panel-rca {
      width: 100%;
      display: grid !important;
      grid-template-columns: 228px minmax(0, 1fr);
      grid-template-rows: minmax(0, 1fr);
      column-gap: 28px;
      overflow: hidden;
    }

    body[data-view="rca"] .rca-workspace {
      min-height: calc(100vh - 36px);
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      margin: 18px 30px 18px 0;
      overflow: hidden;
    }

    body[data-view="rca"] .rca-workspace-head {
      grid-template-columns: minmax(0, 1fr) auto auto;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
    }

    body[data-view="rca"] .rca-workspace-title {
      font-size: 16px;
    }

    body[data-view="rca"] .rca-confidence-pill {
      justify-self: end;
      min-width: 66px;
      padding: 5px 8px;
      font-size: 13px;
    }

    body[data-view="rca"] .rca-confidence-pill span {
      font-size: 8px;
    }

    body[data-view="rca"] .rca-workspace-actions {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 6px;
      flex-wrap: nowrap;
      padding: 0;
    }

    body[data-view="rca"] .rca-workspace-button {
      width: auto !important;
      min-height: 28px;
      padding: 0 10px;
      font-size: 11px;
      line-height: 1;
      white-space: nowrap;
    }

    body[data-view="rca"] .rca-workspace-grid {
      grid-template-columns: minmax(360px, 1fr) minmax(420px, 0.95fr);
      gap: 10px;
      align-items: end;
      padding: 10px 14px;
    }

    body[data-view="rca"] .rca-field-stack {
      grid-template-columns: 112px minmax(0, 1fr) minmax(0, 1fr);
      gap: 8px;
      align-items: end;
    }

    body[data-view="rca"] .rca-field {
      gap: 4px;
      font-size: 10px;
    }

    body[data-view="rca"] .rca-field textarea,
    body[data-view="rca"] .rca-field input {
      min-height: 32px;
      padding: 6px 8px;
      font-size: 12px;
    }

    body[data-view="rca"] .rca-field textarea {
      height: 48px;
      min-height: 48px;
    }

    body[data-view="rca"] .rca-workspace-result {
      grid-template-columns: 1fr;
      gap: 10px;
      max-height: none;
      min-height: 0;
      overflow-y: auto;
      padding: 12px 14px 14px;
      align-items: stretch;
    }

    body[data-view="rca"] .rca-result-block {
      min-height: 120px;
      padding: 12px;
    }

    .quick-panel {
      display: none !important;
    }

    .chat-quick-panel {
      display: none;
    }

    .chat-history-panel,
    .rca-history-panel {
      display: none;
      min-height: 0;
      padding: 0;
      border: 0;
      background: transparent;
    }

    body[data-view="chat"] .workspace {
      grid-column: 2 / 4;
      grid-template-columns: 228px minmax(0, 1fr);
      grid-template-rows: auto minmax(0, 1fr) auto;
      column-gap: 28px;
      border-right: 0;
    }

    body[data-view="chat"] .workspace-header {
      grid-column: 1 / -1;
      grid-row: 1;
    }

    body[data-view="chat"] .chat-history-panel {
      display: grid;
      gap: 8px;
      margin-top: 2px;
      overflow: hidden;
    }

    body[data-view="rca"] .rca-history-panel {
      display: grid;
      gap: 8px;
      align-content: start;
      min-width: 0;
      margin: 0 0 0 30px;
      padding: 18px 16px 0 0;
      border-right: 1px solid #e3e8ef;
      overflow: hidden;
    }

    body[data-view="chat"] .runtime-panel,
    body[data-view="chat"] .signal-panel,
    body[data-view="rca"] .runtime-panel,
    body[data-view="rca"] .signal-panel {
      display: none;
    }

    body[data-view="chat"] .chat-quick-panel {
      display: grid;
      grid-column: 1 / 2;
      grid-row: 2 / 4;
      align-content: start;
      gap: 12px;
      min-width: 0;
      margin-left: 30px;
      padding: 18px 16px 0 0;
      border-right: 1px solid #e3e8ef;
    }

    .chat-quick-title {
      margin: 0;
      color: #111827;
      font-size: 13px;
      font-weight: 780;
    }

    .chat-quick-select-slot {
      display: grid;
      gap: 8px;
      min-width: 0;
    }

    body[data-view="chat"] .conversation {
      grid-column: 2 / 3;
      grid-row: 2;
      min-height: 0;
      margin: 0;
      padding: 18px 30px 12px 0;
      border: 0;
      background: transparent;
    }

    body[data-view="chat"] .conversation-inner {
      width: min(100%, 1180px);
      margin: 0;
    }

    body[data-view="chat"] .composer {
      grid-column: 2 / 3;
      grid-row: 3;
      position: static;
      margin: 0;
      padding: 0 30px 20px 0;
      border: 0;
      background: transparent;
      backdrop-filter: none;
    }

    body[data-view="chat"] .composer-shell {
      width: min(100%, 1180px);
      margin: 0;
    }

    body[data-view="chat"] .composer-actions {
      justify-content: flex-end;
    }

    body[data-view="chat"] .composer-left {
      margin-left: auto;
      flex-wrap: nowrap;
    }

    .chat-history-head strong,
    .chat-history-head small {
      display: block;
    }

    .chat-history-head strong {
      color: #111827;
      font-size: 13px;
      font-weight: 780;
    }

    .chat-history-head small {
      margin-top: 2px;
      color: #7a818a;
      font-size: 11px;
    }

    .chat-history-list {
      min-width: 0;
      max-height: min(32vh, 340px);
      display: grid;
      gap: 4px;
      overflow-y: auto;
      overflow-x: hidden;
      padding-right: 2px;
    }

    .history-empty {
      color: #7a818a;
      font-size: 12px;
      line-height: 1.2;
      white-space: normal;
    }

    .history-item {
      width: 100%;
      min-width: 0;
      min-height: 32px;
      border: 1px solid transparent;
      border-radius: 4px;
      background: transparent;
      color: #334155;
      padding: 7px 8px;
      text-align: left;
      cursor: pointer;
    }

    .history-item.is-active,
    .history-item:hover {
      border-color: #bde8c8;
      background: #edfaf0;
      color: #197a35;
    }

    .history-item strong,
    .history-item span {
      display: block;
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .history-item strong {
      font-size: 12px;
      line-height: 1.1;
    }

    .history-item span {
      margin-top: 2px;
      color: #7a818a;
      font-size: 10px;
    }

    .quick-action-select,
    .config-control input {
      border: 1px solid #cfd4da;
      border-radius: 4px;
      background: #ffffff;
      color: #111827;
      font-size: 12px;
      font-weight: 650;
    }

    .quick-action-select {
      min-height: 32px;
      max-width: 190px;
      padding: 0 8px;
    }

    body[data-view="chat"] .chat-quick-panel .quick-action-select {
      width: 100%;
      max-width: none;
    }

    .config-control {
      display: grid;
      gap: 5px;
      border-radius: 4px;
      background: #f5f6f7;
      padding: 8px;
    }

    .config-control label {
      color: #65707c;
      font-size: 11px;
      font-weight: 700;
    }

    .config-control-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 7px;
      align-items: center;
    }

    .config-control input {
      width: 100%;
      min-height: 32px;
      padding: 0 8px;
    }

    .config-control > strong {
      color: #111827;
      font-size: 12px;
      justify-self: end;
    }
  </style>
</head>
<body data-view="dashboard">
  <div class="app-shell">
    <aside class="nav">
      <div class="brand">
        <div class="mark">ILS</div>
        <div>
          <h1>Infra Log Sentinel</h1>
          <p>__SERVICE_NAME__</p>
        </div>
      </div>

      <section class="nav-panel workspace-menu-panel">
        <p class="nav-title">Workspace</p>
        <div class="workspace-menu" role="tablist" aria-label="Main workspace">
          <button class="view-link is-active" type="button" data-view-tab="dashboard" aria-selected="true">
            <span class="view-icon">D</span>
            <span><strong>Dashboard</strong><small>Statistics and posture</small></span>
          </button>
          <button class="view-link" type="button" data-view-tab="setting" aria-selected="false">
            <span class="view-icon">S</span>
            <span><strong>Setting</strong><small>Runtime controls</small></span>
          </button>
          <button class="view-link" type="button" data-view-tab="chat" aria-selected="false">
            <span class="view-icon">C</span>
            <span><strong>Chat Agent</strong><small>Ask, RCA, report actions</small></span>
          </button>
          <button class="view-link" type="button" data-view-tab="rca" aria-selected="false">
            <span class="view-icon">R</span>
            <span><strong>RCA</strong><small>Root cause search</small></span>
          </button>
        </div>
      </section>

      <section class="nav-panel runtime-panel">
        <p class="nav-title">Runtime posture</p>
        <div class="runtime-state">
          <div class="state-copy">
            <strong id="posture-label">Checking</strong>
            <span id="posture-detail">Waiting for telemetry</span>
          </div>
          <span class="state-pill"><span id="health-dot" class="dot"></span><span id="health-text">syncing</span></span>
        </div>
      </section>

      <section class="nav-panel signal-panel">
        <p class="nav-title">Last 24h signal</p>
        <div class="metric-grid">
          <div class="metric">
            <span>Events</span>
            <strong id="metric-events">-</strong>
          </div>
          <div class="metric critical">
            <span>Critical</span>
            <strong id="metric-critical">-</strong>
          </div>
          <div class="metric">
            <span>Error</span>
            <strong id="metric-error">-</strong>
          </div>
          <div class="metric warning">
            <span>Warning</span>
            <strong id="metric-warning">-</strong>
          </div>
        </div>
      </section>

      <section class="nav-panel quick-panel">
        <p class="nav-title">Quick actions</p>
        <div class="quick-list">
          <button class="quick" type="button" data-prompt="tóm tắt log hôm nay"><span class="icon">S</span><span>Tóm tắt hôm nay</span></button>
          <button class="quick" type="button" data-prompt="alert nào cần ưu tiên và vì sao"><span class="icon">P</span><span>Ưu tiên alert</span></button>
          <button class="quick" type="button" data-prompt="phân tích lỗi nghiêm trọng và đưa command xử lý"><span class="icon">C</span><span>Command xử lý</span></button>
          <button class="quick" type="button" data-prompt="sinh log su co broadcast loop roi phan tich RCA"><span class="icon">A</span><span>RCA incident</span></button>
          <button class="quick" type="button" data-prompt="trạng thái control"><span class="icon">R</span><span>Runtime control</span></button>
          <button class="quick" type="button" data-prompt="tạm ngừng sinh log trong 5 phút"><span class="icon">G</span><span>Tạm ngừng sinh log</span></button>
          <button class="quick" type="button" data-prompt="gửi báo cáo hôm nay qua Gmail"><span class="icon">M</span><span>Gửi report Gmail</span></button>
        </div>
      </section>

      <div class="nav-foot">
        Agent hỏi lại khi thiếu target, value, thời gian hoặc kênh gửi. Các thao tác thật chỉ chạy khi tắt Preview only.
      </div>
    </aside>

    <main class="workspace">
      <header class="workspace-header">
        <div class="title-block">
          <p class="eyebrow">AI operations & RCA copilot</p>
          <h2>Infrastructure Log & RCA Intelligence</h2>
          <small>Phân tích log hạ tầng, điều tra root cause, đề xuất runbook command và điều khiển runtime controls.</small>
        </div>
        <div class="header-actions">
          <span class="chip">Model <strong id="model-chip">MiniMax M2.5</strong></span>
          <span class="chip">Window <strong id="window-chip">24h</strong></span>
          <span class="chip">Mode <strong id="mode-chip">runtime</strong></span>
        </div>
      </header>

      <section id="chat-quick-panel" class="chat-quick-panel" aria-label="Quick actions">
        <p class="chat-quick-title">Quick action</p>
        <div id="chat-quick-select-slot" class="chat-quick-select-slot"></div>
        <section class="nav-panel chat-history-panel" aria-label="Chat history">
          <div class="chat-history-head">
            <strong>Recents</strong>
            <small>Last 5 sessions</small>
          </div>
          <div id="chat-history-list" class="chat-history-list"></div>
        </section>
      </section>

      <section id="view-dashboard" class="workspace-view dashboard-view" data-view-panel="dashboard">
        <div class="dashboard-grid">
          <section class="dashboard-card dashboard-posture-card">
            <div class="dashboard-card-head">
              <div>
                <p class="eyebrow">Dashboard</p>
                <h3>Operations posture</h3>
              </div>
              <span class="state-pill"><span id="dash-health-dot" class="dot"></span><span id="dash-health-text">syncing</span></span>
            </div>
            <div class="dashboard-posture-copy">
              <strong id="dash-posture-label">Checking</strong>
              <span id="dash-posture-detail">Waiting for telemetry</span>
            </div>
          </section>

          <section class="dashboard-card dashboard-metrics-card">
            <div class="dashboard-card-head">
              <div>
                <p class="eyebrow">Last 24h signal</p>
                <h3>Log volume and severity</h3>
              </div>
              <span class="chip">Mode <strong id="dash-mode-chip">runtime</strong></span>
            </div>
            <div class="dashboard-metric-grid">
              <div class="metric"><span>Events</span><strong id="dash-metric-events">-</strong></div>
              <div class="metric critical"><span>Critical</span><strong id="dash-metric-critical">-</strong></div>
              <div class="metric"><span>Error</span><strong id="dash-metric-error">-</strong></div>
              <div class="metric warning"><span>Warning</span><strong id="dash-metric-warning">-</strong></div>
            </div>
          </section>

          <section class="dashboard-card dashboard-alert-card">
            <div class="dashboard-card-head">
              <div>
                <p class="eyebrow">Priority queue</p>
                <h3>Current alert focus</h3>
              </div>
            </div>
            <div id="dash-alert-list" class="alert-list">
              <p class="empty">Waiting for status.</p>
            </div>
          </section>

          <section class="dashboard-card dashboard-environment-card">
            <div class="dashboard-card-head">
              <div>
                <p class="eyebrow">Environment</p>
                <h3>Runtime configuration</h3>
              </div>
            </div>
            <div class="facts">
              <div class="fact"><span>Report time</span><strong id="dash-fact-report-time">-</strong></div>
              <div class="fact"><span>Scan interval</span><strong id="dash-fact-scan">-</strong></div>
              <div class="fact"><span>Timezone</span><strong id="dash-fact-timezone">-</strong></div>
              <div class="fact"><span>Source mode</span><strong id="dash-fact-source">-</strong></div>
            </div>
          </section>

          <section class="dashboard-card dashboard-wide-card">
            <div class="dashboard-card-head">
              <div>
                <p class="eyebrow">Domain mix</p>
                <h3>Parsed log distribution</h3>
              </div>
            </div>
            <div id="dash-domain-bars" class="domain-bars">
              <p class="empty">Waiting for status.</p>
            </div>
          </section>
        </div>
      </section>

      <section class="conversation" aria-live="polite">
        <div id="conversation" class="conversation-inner"></div>
      </section>

      <footer class="composer">
        <form id="chat-form" class="composer-shell">
          <textarea id="prompt" rows="2" placeholder="Hỏi agent về log, RCA, alert, report, command xử lý hoặc runtime control..."></textarea>
          <div class="composer-actions">
            <div class="composer-left">
              <select id="quick-action-select" class="quick-action-select" aria-label="Quick action">
                <option value="">Quick action</option>
                <option value="tóm tắt log hôm nay">Tóm tắt hôm nay</option>
                <option value="alert nào cần ưu tiên và vì sao">Ưu tiên alert</option>
                <option value="phân tích lỗi nghiêm trọng và đưa command xử lý">Command xử lý</option>
                <option value="sinh log su co broadcast loop roi phan tich RCA">RCA incident</option>
                <option value="trạng thái control">Runtime control</option>
                <option value="tạm ngừng sinh log trong 5 phút">Tạm ngừng sinh log</option>
                <option value="gửi báo cáo hôm nay qua Gmail">Gửi report Gmail</option>
              </select>
              <select id="quick-impact-select" class="quick-action-select" aria-label="Quick impact">
                <option value="">Quick impact</option>
                <option value="phan tich RCA dua tren log hien tai: VLAN 20 users mat internet, firewall CPU saturated trong 1 gio qua">VLAN 20 internet slow</option>
                <option value="phan tich RCA dua tren log hien tai: Fortigate latency tang va new sessions delayed trong 1 gio qua">Fortigate session spike</option>
                <option value="phan tich RCA dua tren log hien tai: ung dung loi name resolution, DNS query timeout trong 1 gio qua">DNS query timeout</option>
                <option value="phan tich RCA dua tren log hien tai: applications cannot reach payment subnet sau routing change trong 1 gio qua">Routing payment subnet</option>
                <option value="phan tich RCA dua tren log hien tai: SQLAgent service down, database jobs khong chay trong 1 gio qua">SQLAgent service down</option>
                <option value="phan tich RCA dua tren log hien tai: SSH brute force tu internet, account lockout risk trong 1 gio qua">SSH brute force</option>
              </select>
              <label class="toggle">
                <input id="dry-run" type="checkbox" checked>
                Preview only
              </label>
              <button id="new-chat" class="composer-link" type="button">New chat</button>
            </div>
            <button id="send" class="send" type="submit"><span>Send</span><span>›</span></button>
          </div>
        </form>
      </footer>
    </main>

    <aside class="insight-rail">
      <div class="settings-page-head">
        <p class="eyebrow">Run control</p>
        <h2>Agent settings</h2>
        <small>Runtime switches and generation intervals for the sentinel agent.</small>
      </div>

      <div class="rail-tabs" role="tablist" aria-label="Right panel">
        <button class="rail-tab is-active" type="button" role="tab" aria-selected="true" aria-controls="rail-panel-sentinel" data-rail-tab="sentinel">Log Sentinel</button>
        <button class="rail-tab" type="button" role="tab" aria-selected="false" aria-controls="rail-panel-rca" data-rail-tab="rca">RCA</button>
      </div>

      <div id="rail-panel-sentinel" class="rail-panel is-active" role="tabpanel" data-rail-panel="sentinel">
      <section class="rail-section alerts-section">
        <h3>Priority queue</h3>
        <div id="alert-list" class="alert-list">
          <p class="empty">No alert context loaded yet.</p>
        </div>
      </section>

      <section class="rail-section runtime-section">
        <h3>Runtime controls</h3>
        <div class="control-list">
          <article class="runtime-control-card">
            <div class="runtime-control-head">
              <div>
                <strong>Telegram alerts</strong>
                <small id="control-telegram-detail">Realtime alert delivery</small>
              </div>
              <span id="control-telegram" class="control-badge disabled">-</span>
            </div>
            <button class="switch" type="button" data-runtime-control="telegram_alerts" aria-label="Toggle Telegram alerts" aria-checked="false"><span></span></button>
          </article>
          <article class="runtime-control-card">
            <div class="runtime-control-head">
              <div>
                <strong>Gmail reports</strong>
                <small id="control-email-detail">Scheduled report delivery</small>
              </div>
              <span id="control-email" class="control-badge disabled">-</span>
            </div>
            <button class="switch" type="button" data-runtime-control="email_reports" aria-label="Toggle Gmail reports" aria-checked="false"><span></span></button>
          </article>
          <article class="runtime-control-card">
            <div class="runtime-control-head">
              <div>
                <strong>Log generator</strong>
                <small id="control-loggen-detail">Synthetic runtime log stream</small>
              </div>
              <span id="control-loggen" class="control-badge disabled">-</span>
            </div>
            <button class="switch" type="button" data-runtime-control="log_generation" aria-label="Toggle log generator" aria-checked="false"><span></span></button>
          </article>
          <article class="runtime-control-card">
            <div class="runtime-control-head">
              <div>
                <strong>Incident generator</strong>
                <small id="control-incident-detail">All RCA incident scenarios</small>
              </div>
              <span id="control-incident" class="control-badge disabled">-</span>
            </div>
            <button class="switch" type="button" data-runtime-control="incident_generation" aria-label="Toggle incident generator" aria-checked="false"><span></span></button>
          </article>
          <article class="runtime-control-card">
            <div class="runtime-control-head">
              <div>
                <strong>Generator interval</strong>
                <small id="control-interval-detail">Seconds between generated logs</small>
              </div>
              <span id="control-interval" class="control-badge live">-</span>
            </div>
            <div class="interval-control">
              <input id="control-interval-input" type="number" min="1" max="86400" step="1" inputmode="numeric" aria-label="Generator interval seconds">
              <button id="control-interval-save" class="control-save" type="button">Save</button>
            </div>
          </article>
          <article class="runtime-control-card">
            <div class="runtime-control-head">
              <div>
                <strong>Incident interval</strong>
                <small id="control-incident-interval-detail">Seconds between all-scenario incident packs</small>
              </div>
              <span id="control-incident-interval" class="control-badge live">-</span>
            </div>
            <div class="interval-control">
              <input id="control-incident-interval-input" type="number" min="1" max="86400" step="1" inputmode="numeric" aria-label="Incident generator interval seconds">
              <button id="control-incident-interval-save" class="control-save" type="button">Save</button>
            </div>
          </article>
        </div>
      </section>

      <section class="rail-section environment-section">
        <h3>Runtime configuration</h3>
        <div class="facts">
          <div class="config-control">
            <label for="control-report-time-input">Report time <span id="report-timezone-label">(timezone)</span></label>
            <div class="config-control-row">
              <input id="control-report-time-input" type="time" aria-label="Report time">
              <button id="control-report-time-save" class="control-save" type="button">Save</button>
            </div>
            <strong id="fact-report-time">-</strong>
          </div>
          <div class="config-control">
            <label for="control-scan-interval-input">Scan interval</label>
            <div class="config-control-row">
              <input id="control-scan-interval-input" type="number" min="1" max="86400" step="1" inputmode="numeric" aria-label="Scan interval seconds">
              <button id="control-scan-interval-save" class="control-save" type="button">Save</button>
            </div>
            <strong id="fact-scan">-</strong>
          </div>
          <div class="fact"><span>Timezone</span><strong id="fact-timezone">-</strong></div>
          <div class="fact"><span>Source mode</span><strong id="fact-source">-</strong></div>
        </div>
      </section>

      <section class="rail-section domain-section">
        <h3>Domain mix</h3>
        <div id="domain-bars" class="domain-bars">
          <p class="empty">Waiting for status.</p>
        </div>
      </section>
      </div>

      <div id="rail-panel-rca" class="rail-panel" role="tabpanel" data-rail-panel="rca" hidden>
        <section class="nav-panel rca-history-panel" aria-label="RCA history">
          <div class="chat-history-head">
            <strong>Recent</strong>
            <small>Impact / symptom + time</small>
          </div>
          <div id="rca-history-list" class="chat-history-list"></div>
        </section>
        <section class="rca-workspace" aria-label="RCA workspace">
          <div class="rca-workspace-head">
            <div>
              <p class="rca-workspace-kicker">RCA workspace</p>
              <h3 class="rca-workspace-title">Basic RCA Search</h3>
            </div>
            <div id="rca-workspace-confidence" class="rca-confidence-pill">--<span>confidence</span></div>
            <div class="rca-workspace-actions">
              <button id="rca-analyze" class="rca-workspace-button" type="button">Analyze Current Logs</button>
              <button id="rca-send-chat" class="rca-workspace-button secondary" type="button">Send As Chat</button>
              <button id="rca-clear" class="rca-workspace-button danger" type="button">Clear</button>
            </div>
          </div>
          <div class="rca-workspace-grid">
            <label class="rca-field">
              Impact / symptom
              <textarea id="rca-impact" rows="3"></textarea>
            </label>
            <div class="rca-field-stack">
              <label class="rca-field">
                Window (hours)
                <input id="rca-lookback" type="number" min="0.25" max="168" step="0.25">
              </label>
              <label class="rca-field">
                From
                <input id="rca-start" type="datetime-local">
              </label>
              <label class="rca-field">
                To
                <input id="rca-end" type="datetime-local">
              </label>
            </div>
          </div>
          <div id="rca-workspace-result" class="rca-workspace-result">
            <div class="rca-result-block">
              <h4>Most Likely Root Cause</h4>
              <p class="rca-root-cause">Chưa chạy RCA search trong tab này.</p>
            </div>
            <div class="rca-result-block">
              <h4>Evidence</h4>
              <ul class="rca-compact-list">
                <li>Chưa có log evidence được chọn.</li>
              </ul>
            </div>
            <div class="rca-result-block">
              <h4>Analyze</h4>
              <ul class="rca-compact-list">
                <li>Nhập impact/symptom hoặc chọn incident context, sau đó chạy RCA.</li>
              </ul>
            </div>
            <div class="rca-result-block">
              <h4>Action</h4>
              <ul class="rca-compact-list">
                <li>Chạy Analyze Current Logs khi đã có incident context.</li>
              </ul>
            </div>
          </div>
        </section>
      </div>
    </aside>
  </div>

  <script>
    const conversation = document.getElementById("conversation");
    const form = document.getElementById("chat-form");
    const promptBox = document.getElementById("prompt");
    const dryRunBox = document.getElementById("dry-run");
    const sendButton = document.getElementById("send");
    const chatHistoryList = document.getElementById("chat-history-list");
    const rcaHistoryList = document.getElementById("rca-history-list");
    const quickActionSelect = document.getElementById("quick-action-select");
    const quickImpactSelect = document.getElementById("quick-impact-select");
    const quickActionSlot = document.getElementById("chat-quick-select-slot");
    const CHAT_SESSION_KEY = "infra-log-sentinel-web-session";
    const CHAT_HISTORY_KEY = "infra-log-sentinel-web-history-v1";
    const RCA_HISTORY_KEY = "infra-log-sentinel-rca-history-v1";
    let conversationId = getConversationId();

    if (quickActionSelect && quickActionSlot) {
      quickActionSlot.appendChild(quickActionSelect);
    }
    if (quickImpactSelect && quickActionSlot) {
      quickActionSlot.appendChild(quickImpactSelect);
    }

    const state = {
      busy: false,
      rcaScenarios: [],
      rcaWorkspaceHasRun: false,
      rcaWorkspaceAnalysis: null,
      activeRcaHistoryId: ""
    };

    function getConversationId() {
      try {
        const existing = window.localStorage.getItem(CHAT_SESSION_KEY);
        if (existing) {
          return existing;
        }
        const generated = newConversationId();
        window.localStorage.setItem(CHAT_SESSION_KEY, generated);
        return generated;
      } catch (error) {
        return newConversationId();
      }
    }

    function newConversationId() {
      return window.crypto && window.crypto.randomUUID
        ? "web-" + window.crypto.randomUUID()
        : "web-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
    }

    function legacyStartNewChatSessionUnused() {
      conversationId = newConversationId();
      try {
        window.localStorage.setItem(CHAT_SESSION_KEY, conversationId);
      } catch (error) {
        // Ignore storage failures; the in-memory id still separates this browser session.
      }
      conversation.innerHTML = "";
      appendMessage("agent", "**New chat.** Mình đã tách ngữ cảnh hội thoại. Câu tiếp theo sẽ được xử lý như một Log Sentinel/RCA investigation mới.");
      promptBox.focus();
    }

    function switchRailTab(target) {
      const tabName = target === "rca" ? "rca" : "sentinel";
      document.querySelectorAll("[data-rail-tab]").forEach(function(tab) {
        const active = tab.dataset.railTab === tabName;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      document.querySelectorAll("[data-rail-panel]").forEach(function(panel) {
        const active = panel.dataset.railPanel === tabName;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
      });
    }

    function switchWorkspaceView(target) {
      const viewName = ["dashboard", "setting", "chat", "rca"].includes(target) ? target : "dashboard";
      document.body.dataset.view = viewName;
      document.querySelectorAll("[data-view-tab]").forEach(function(tab) {
        const active = tab.dataset.viewTab === viewName;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      if (viewName === "setting") {
        switchRailTab("sentinel");
      }
      if (viewName === "rca") {
        switchRailTab("rca");
      }
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function linkify(value) {
      const escaped = escapeHtml(value);
      return escaped.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>');
    }

    function inlineFormat(value) {
      let html = escapeHtml(value);
      html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\[(CRITICAL|ERROR|WARNING|INFO)\]/gi, function(_, level) {
        return '<span class="severity ' + level.toLowerCase() + '">' + level.toUpperCase() + '</span>';
      });
      html = html.replace(/\b(Running|Stopped|Paused|Enabled|Disabled)\b/gi, function(status) {
        const key = status.toLowerCase();
        const cls = key === "running" || key === "enabled" ? "info" : key === "paused" ? "warning" : "error";
        return '<span class="answer-mini-chip ' + cls + '">' + status + '</span>';
      });
      html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>');
      return html;
    }

    function renderAgentContent(text) {
      const normalized = String(text || "").replace(/\r\n/g, "\n");
      const context = classifyAgentAnswer(normalized);
      const parts = [];
      const fenceRegex = /```([A-Za-z0-9_-]*)\n([\s\S]*?)```/g;
      let lastIndex = 0;
      let match;

      while ((match = fenceRegex.exec(normalized)) !== null) {
        if (match.index > lastIndex) {
          parts.push(renderMarkdownBlock(normalized.slice(lastIndex, match.index)));
        }
        parts.push(renderCodeBlock(match[2], match[1] || "command"));
        lastIndex = fenceRegex.lastIndex;
      }

      if (lastIndex < normalized.length) {
        parts.push(renderMarkdownBlock(normalized.slice(lastIndex)));
      }

      return '<div class="answer context-' + context.type + '">' + renderAnswerBanner(context) + parts.join("") + '</div>';
    }

    function textKey(value) {
      return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
    }

    function classifyAgentAnswer(text) {
      const key = textKey(text);
      if (key.includes("aiops rca investigation") || key.includes("aiops rca brief") || key.includes("root cause:") || key.includes("event timeline:")) {
        return {
          type: "rca",
          icon: "RCA",
          kicker: "Response type",
          title: "Root cause investigation",
          subtitle: "Root cause, impact, timeline, evidence and actions are grouped for incident review."
        };
      }
      if (key.includes("runbook command") || key.includes("command de xuat") || (key.includes("verify:") && key.includes("remediate:"))) {
        return {
          type: "runbook",
          icon: "RB",
          kicker: "Response type",
          title: "Runbook recommendation",
          subtitle: "Commands are grouped by phase so verification stays separate from remediation."
        };
      }
      if (key.includes("giai thich") || key.includes("command insight") || key.includes("dung de lam gi") || key.includes("khong phai yeu cau sinh them runbook")) {
        return {
          type: "command",
          icon: "CMD",
          kicker: "Response type",
          title: "Command explanation",
          subtitle: "Purpose, usage and operational risk are separated for quick review."
        };
      }
      if (key.includes("tom tat") || key.includes("tong so event") || key.includes("top alert") || key.includes("theo severity") || key.includes("theo domain")) {
        return {
          type: "summary",
          icon: "SUM",
          kicker: "Response type",
          title: "Log intelligence summary",
          subtitle: "Signal, severity and priority findings are organized for scanning."
        };
      }
      if (key.includes("thieu ngu canh") || key.includes("vui long noi ro") || key.includes("can lam ro") || key.includes("hoi lai truoc")) {
        return {
          type: "clarify",
          icon: "?",
          kicker: "Response type",
          title: "Needs clarification",
          subtitle: "The agent is asking for missing target, value, time window or delivery channel."
        };
      }
      if (key.includes("da tao") || key.includes("da gui") || key.includes("da cap nhat") || key.includes("runtime") || key.includes("telegram") || key.includes("gmail")) {
        return {
          type: "action",
          icon: "OK",
          kicker: "Response type",
          title: "Action result",
          subtitle: "Execution details and state changes are grouped below."
        };
      }
      if (key.includes("xin chao")) {
        return {
          type: "action",
          icon: "AI",
          kicker: "Copilot ready",
          title: "Infrastructure Log Sentinel",
          subtitle: "Ask about logs, reports, commands or runtime controls."
        };
      }
      return {
        type: "analysis",
        icon: "AI",
        kicker: "Response type",
        title: "Operational analysis",
        subtitle: "The answer is structured into readable findings and details."
      };
    }

    function renderAnswerBanner(context) {
      return '' +
        '<div class="answer-banner">' +
          '<div class="answer-banner-icon">' + escapeHtml(context.icon) + '</div>' +
          '<div>' +
            '<p class="answer-banner-kicker">' + escapeHtml(context.kicker) + '</p>' +
            '<p class="answer-banner-title">' + escapeHtml(context.title) + '</p>' +
            '<p class="answer-banner-subtitle">' + escapeHtml(context.subtitle) + '</p>' +
          '</div>' +
        '</div>';
    }

    function renderMarkdownBlock(text) {
      const lines = text.split("\n");
      const html = [];
      let listType = null;
      let listItems = [];
      let tableRows = [];

      function flushList() {
        if (!listType) {
          return;
        }
        html.push('<' + listType + '>' + listItems.map(function(item) {
          return '<li>' + inlineFormat(item) + '</li>';
        }).join("") + '</' + listType + '>');
        listType = null;
        listItems = [];
      }

      function flushTable() {
        if (!tableRows.length) {
          return;
        }
        const rows = tableRows.map(parseTableRow);
        const header = rows.shift() || [];
        if (rows.length && rows[0].every(function(cell) { return /^-+$/.test(cell.replace(/:/g, "").trim()); })) {
          rows.shift();
        }
        if (!header.length) {
          tableRows = [];
          return;
        }
        html.push(
          '<table><thead><tr>' +
          header.map(function(cell) { return '<th>' + inlineFormat(cell) + '</th>'; }).join("") +
          '</tr></thead><tbody>' +
          rows.map(function(row) {
            return '<tr>' + row.map(function(cell) { return '<td>' + inlineFormat(cell) + '</td>'; }).join("") + '</tr>';
          }).join("") +
          '</tbody></table>'
        );
        tableRows = [];
      }

      for (let i = 0; i < lines.length; i++) {
        const rawLine = lines[i];
        const line = rawLine.trim();

        if (!line) {
          flushList();
          flushTable();
          continue;
        }

        if (isTableLine(line)) {
          flushList();
          tableRows.push(line);
          continue;
        }
        flushTable();

        const commandMatch = rawLine.match(/^\s*-\s*(Verify|Investigate|Remediate|Validate|Check|Analyze|Fix):\s*(.+)$/i);
        if (commandMatch) {
          flushList();
          html.push(renderCommandCard(commandMatch[1], commandMatch[2]));
          continue;
        }

        const whyMatch = rawLine.match(/^\s*Why:\s*(.+)$/i);
        if (whyMatch) {
          flushList();
          html.push('<p class="why">' + inlineFormat(whyMatch[1]) + '</p>');
          continue;
        }

        const sectionTitle = parseSectionTitle(line);
        if (sectionTitle) {
          flushList();
          html.push('<div class="answer-section-title">' + inlineFormat(sectionTitle) + '</div>');
          continue;
        }

        const heading = line.match(/^(#{1,4})\s+(.+)$/);
        if (heading) {
          flushList();
          const level = Math.min(heading[1].length + 1, 4);
          html.push('<h' + level + '>' + inlineFormat(heading[2]) + '</h' + level + '>');
          continue;
        }

        if (/^-{3,}$/.test(line)) {
          flushList();
          html.push("<hr>");
          continue;
        }

        const bullet = line.match(/^[-*]\s+(.+)$/);
        if (bullet) {
          const special = renderSpecialLine(bullet[1]);
          if (special) {
            flushList();
            html.push(special);
            continue;
          }
          if (listType !== "ul") {
            flushList();
            listType = "ul";
          }
          listItems.push(bullet[1]);
          continue;
        }

        const numbered = line.match(/^(\d+)\.\s+(.+)$/);
        if (numbered) {
          const special = renderSpecialLine(numbered[2], numbered[1]);
          if (special) {
            flushList();
            html.push(special);
            continue;
          }
          if (listType !== "ol") {
            flushList();
            listType = "ol";
          }
          listItems.push(numbered[2]);
          continue;
        }

        const field = parseKeyValueLine(line);
        if (field && shouldPromoteField(field)) {
          flushList();
          html.push(renderFieldCard(field.label, field.value));
          continue;
        }

        flushList();
        html.push('<p>' + inlineFormat(line) + '</p>');
      }

      flushList();
      flushTable();
      return html.join("");
    }

    function parseSectionTitle(line) {
      const trimmed = String(line || "").trim();
      if (!trimmed.endsWith(":") || trimmed.includes("://")) {
        return "";
      }
      const title = trimmed.slice(0, -1).trim();
      if (title.length < 2 || title.length > 56 || title.includes("|")) {
        return "";
      }
      return title;
    }

    function renderSpecialLine(line, index) {
      const finding = parseFindingLine(line, index);
      if (finding) {
        return renderFindingCard(finding);
      }
      const field = parseKeyValueLine(line);
      if (field && shouldPromoteField(field)) {
        return renderFieldCard(field.label, field.value);
      }
      return "";
    }

    function parseFindingLine(line, index) {
      const detailed = String(line || "").match(/^\[([A-Za-z]+)\]\s+(\S+)\s+([^:]+):\s*(.+)$/);
      if (detailed) {
        return {
          index: index || "",
          severity: detailed[1],
          location: detailed[2],
          type: detailed[3],
          message: detailed[4]
        };
      }
      const compact = String(line || "").match(/^\[([A-Za-z]+)\]\s+(.+?)\s+-\s+(.+)$/);
      if (compact) {
        return {
          index: index || "",
          severity: compact[1],
          location: compact[2],
          type: compact[3],
          message: ""
        };
      }
      return null;
    }

    function renderFindingCard(finding) {
      const severity = severityClass(finding.severity);
      const index = finding.index ? '<span class="finding-index">#' + escapeHtml(finding.index) + '</span>' : "";
      const message = finding.message ? '<p class="finding-message">' + inlineFormat(finding.message) + '</p>' : "";
      return '' +
        '<article class="finding-card ' + severity + '">' +
          '<div class="finding-meta">' +
            index +
            '<span class="severity ' + severity + '">' + escapeHtml(String(finding.severity || "info").toUpperCase()) + '</span>' +
            '<span class="finding-location">' + inlineFormat(finding.location || "-") + '</span>' +
            '<span class="finding-type">' + inlineFormat(finding.type || "-") + '</span>' +
          '</div>' +
          message +
        '</article>';
    }

    function parseKeyValueLine(line) {
      const match = String(line || "").match(/^([^:]{2,48}):\s*(.+)$/);
      if (!match) {
        return null;
      }
      const label = match[1].trim();
      const value = match[2].trim();
      if (!label || !value || label.includes("://") || label.includes("|")) {
        return null;
      }
      return { label: label, value: value };
    }

    function shouldPromoteField(field) {
      const label = textKey(field.label);
      if (label.includes("http")) {
        return false;
      }
      return (
        label.includes("tong") ||
        label.includes("severity") ||
        label.includes("domain") ||
        label.includes("file") ||
        label.includes("pham vi") ||
        label.includes("log") ||
        label.includes("huong xu ly") ||
        label.includes("question") ||
        label.includes("command") ||
        label.includes("intent") ||
        label.includes("risk") ||
        label.includes("summary") ||
        label.includes("nguyen nhan") ||
        label.includes("tac dong")
      );
    }

    function renderFieldCard(label, value) {
      return '' +
        '<div class="answer-field">' +
          '<div class="answer-field-label">' + inlineFormat(label) + '</div>' +
          '<div class="answer-field-value">' + renderFieldValue(value) + '</div>' +
        '</div>';
    }

    function renderFieldValue(value) {
      const pairs = parseValuePairs(value);
      if (pairs.length) {
        return '<div class="answer-chip-row">' + pairs.map(renderValueChip).join("") + '</div>';
      }
      return inlineFormat(value);
    }

    function parseValuePairs(value) {
      const trimmed = String(value || "").trim();
      if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
        const body = trimmed.slice(1, -1);
        const pairs = [];
        const regex = /['"]?([^'",:{}]+)['"]?\s*:\s*['"]?([^,'"}]+)['"]?/g;
        let match;
        while ((match = regex.exec(body)) !== null) {
          pairs.push({ key: match[1].trim(), value: match[2].trim() });
        }
        return pairs;
      }
      if (/^[A-Za-z_, -]+$/.test(trimmed) && trimmed.includes(",")) {
        return trimmed.split(",").map(function(item) {
          return { key: item.trim(), value: "" };
        }).filter(function(item) {
          return item.key;
        });
      }
      return [];
    }

    function renderValueChip(pair) {
      const severity = severityClass(pair.key);
      const value = pair.value ? '<span class="chip-value">' + inlineFormat(pair.value) + '</span>' : "";
      return '' +
        '<span class="answer-mini-chip ' + severity + '">' +
          '<span class="chip-key">' + inlineFormat(pair.key) + '</span>' +
          value +
        '</span>';
    }

    function isTableLine(line) {
      return line.includes("|") && line.split("|").length >= 3;
    }

    function parseTableRow(line) {
      return line.replace(/^\|/, "").replace(/\|$/, "").split("|").map(function(cell) {
        return cell.trim();
      });
    }

    function renderCodeBlock(code, lang) {
      return '' +
        '<div class="code-block">' +
          '<div class="code-head"><span>' + escapeHtml(lang || "command") + '</span><button class="copy-button" type="button" data-copy="code">Copy</button></div>' +
          '<pre><code>' + escapeHtml(String(code || "").trim()) + '</code></pre>' +
        '</div>';
    }

    function renderCommandCard(phase, command) {
      const phaseKey = phaseClass(phase);
      return '' +
        '<div class="command-card ' + phaseKey + '">' +
          '<div class="command-head"><span class="phase">' + escapeHtml(phase) + '</span><button class="command-copy" type="button" data-copy="command">Copy</button></div>' +
          '<code class="command-text">' + escapeHtml(String(command || "").trim()) + '</code>' +
        '</div>';
    }

    function shellQuote(value) {
      return "'" + String(value || "").replaceAll("'", "'\"'\"'") + "'";
    }

    function powershellQuote(value) {
      return "'" + String(value || "").replaceAll("'", "''") + "'";
    }

    function rcaVietnameseStatus(status) {
      const value = String(status || "").toLowerCase();
      if (value === "confirmed") {
        return "đã xác nhận";
      }
      if (value === "need_verification" || value === "needs_verification") {
        return "cần xác minh thêm";
      }
      if (value === "insufficient_data") {
        return "chưa đủ dữ liệu";
      }
      return status || "-";
    }

    function rcaTimelineText(item) {
      return [
        item.timestamp,
        item.type,
        item.source,
        item.event
      ].filter(Boolean).join(" | ");
    }

    function rcaVietnameseActions(analysis, rawActions) {
      const anchor = (analysis && analysis.anchor_event) || {};
      const source = String(anchor.source || "source chưa xác định");
      const eventType = String(anchor.event_type || "event_type chưa xác định");
      const timestamp = String(anchor.timestamp || "thời điểm RCA");
      const confidence = Number(analysis && analysis.confidence || 0);
      const actions = [
        "Ưu tiên kiểm tra " + source + " / " + eventType + " trước khi remediation.",
        "Đối chiếu log quanh " + timestamp + " để xác minh chuỗi nguyên nhân -> ảnh hưởng.",
      ];
      if (confidence < 70) {
        actions.push("Chưa chạy thao tác có rủi ro; cần thu thập thêm evidence trước.");
      } else {
        actions.push("Nếu evidence khớp, xử lý theo runbook tương ứng và thông báo impact cho service owner.");
      }
      (rawActions || []).slice(0, 3).forEach(function(action) {
        actions.push("Khuyến nghị kỹ thuật: " + String(action));
      });
      return actions;
    }

    function rcaCommandCards(analysis) {
      const anchor = (analysis && analysis.anchor_event) || {};
      const source = String(anchor.source || "").trim();
      const eventType = String(anchor.event_type || "").trim();
      const domain = String(anchor.domain || "").toLowerCase();
      const eventKey = eventType.toLowerCase();
      const sourceKey = source.toLowerCase();
      const needle = source || eventType || "ERROR";
      const cards = [
        {
          phase: "Investigate",
          command: "grep -R " + shellQuote(needle) + " /app/data/logs -n | tail -80"
        },
        {
          phase: "Analyze",
          command: "grep -R " + shellQuote(eventType || needle) + " /app/data/logs -n | tail -80"
        }
      ];

      if (domain.includes("linux") || eventKey.includes("dns") || sourceKey.includes("dns")) {
        cards.push({
          phase: "Check",
          command: "journalctl --since '1 hour ago' -u named -u systemd-resolved --no-pager | tail -120"
        });
        cards.push({
          phase: "Validate",
          command: "dig @127.0.0.1 example.com +time=2 +tries=1"
        });
      }

      if (eventKey.includes("application") || eventKey.includes("timeout") || sourceKey.includes("web")) {
        cards.push({
          phase: "Check",
          command: "systemctl status nginx --no-pager && journalctl -u nginx --since '1 hour ago' --no-pager | tail -120"
        });
      }

      if (domain.includes("fortigate") || sourceKey.includes("fortigate") || eventKey.includes("session")) {
        cards.push({
          phase: "Check",
          command: "diagnose sys session stat && diagnose sys top 5 20"
        });
        cards.push({
          phase: "Investigate",
          command: "show firewall policy | grep -i " + shellQuote(eventType || "policy")
        });
      }

      if (domain.includes("windows") || sourceKey.includes("win")) {
        cards.push({
          phase: "Check",
          command: "Get-WinEvent -ComputerName " + powershellQuote(source || ".") + " -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddHours(-1)} | Select-Object -First 50"
        });
      }

      if (domain.includes("vmware") || sourceKey.includes("esx") || sourceKey.includes("vcenter")) {
        cards.push({
          phase: "Check",
          command: "esxcli system syslog mark --message " + shellQuote("RCA check " + (eventType || source)) + " && tail -120 /var/log/vmkernel.log"
        });
      }

      return cards.slice(0, 5).map(function(card) {
        return renderCommandCard(card.phase, card.command);
      }).join("");
    }

    function phaseClass(phase) {
      const key = String(phase || "").toLowerCase();
      if (["verify", "investigate", "remediate", "validate", "check", "analyze", "fix"].includes(key)) {
        return key;
      }
      return "verify";
    }

    function appendMessage(role, text, extraClass, options) {
      const row = document.createElement("div");
      row.className = "message " + role + (extraClass ? " " + extraClass : "");

      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = role === "user" ? "ME" : "AI";

      const bubble = document.createElement("div");
      bubble.className = "bubble";
      if (role === "agent") {
        bubble.innerHTML = extraClass === "typing"
          ? '<div class="typing-line">' + escapeHtml(text) + '</div>'
          : renderAgentContent(text);
      } else {
        bubble.innerHTML = linkify(text);
      }

      if (role === "user") {
        row.appendChild(bubble);
        row.appendChild(avatar);
      } else {
        row.appendChild(avatar);
        row.appendChild(bubble);
      }

      conversation.appendChild(row);
      conversation.parentElement.scrollTop = conversation.parentElement.scrollHeight;
      if (extraClass !== "typing" && !(options && options.skipHistory)) {
        saveChatMessage(role, text);
      }
      return row;
    }

    function readChatHistory() {
      try {
        const parsed = JSON.parse(window.localStorage.getItem(CHAT_HISTORY_KEY) || "[]");
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    }

    function writeChatHistory(history) {
      try {
        window.localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history.slice(0, 5)));
      } catch (error) {
        // Ignore storage failures; chat still works without persisted history.
      }
    }

    function sessionTitleFromMessages(messages) {
      const firstUser = (messages || []).find(function(message) {
        return message.role === "user" && message.text;
      });
      if (!firstUser) {
        return "New chat";
      }
      return firstUser.text.length > 52 ? firstUser.text.slice(0, 49) + "..." : firstUser.text;
    }

    function saveChatMessage(role, text) {
      if (!["user", "agent"].includes(role) || !String(text || "").trim()) {
        return;
      }
      const now = new Date().toISOString();
      const history = readChatHistory().filter(function(session) {
        return session && session.id !== conversationId;
      });
      const existing = readChatHistory().find(function(session) {
        return session && session.id === conversationId;
      }) || { id: conversationId, messages: [], createdAt: now };
      const hasUserMessage = (existing.messages || []).some(function(message) {
        return message.role === "user";
      });
      if (role === "agent" && !hasUserMessage && (
        String(text || "").includes("AI operations copilot") ||
        String(text || "").includes("AI operations & RCA copilot")
      )) {
        return;
      }
      if (role === "agent" && !hasUserMessage && String(text || "").startsWith("**New chat.**")) {
        return;
      }
      existing.messages = (existing.messages || []).concat({
        role: role,
        text: String(text),
        ts: now
      }).slice(-80);
      existing.updatedAt = now;
      existing.title = sessionTitleFromMessages(existing.messages);
      writeChatHistory([existing].concat(history).sort(function(a, b) {
        return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
      }));
      renderChatHistoryList();
    }

    function formatHistoryTime(value) {
      if (!value) {
        return "";
      }
      try {
        return new Date(value).toLocaleString([], { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
      } catch (error) {
        return "";
      }
    }

    function renderChatHistoryList() {
      if (!chatHistoryList) {
        return;
      }
      const history = readChatHistory().slice(0, 5);
      if (!history.length) {
        chatHistoryList.innerHTML = '<span class="history-empty">No saved sessions yet.</span>';
        return;
      }
      chatHistoryList.innerHTML = history.map(function(session) {
        const active = session.id === conversationId ? " is-active" : "";
        return '' +
          '<button class="history-item' + active + '" type="button" data-history-id="' + escapeHtml(session.id) + '">' +
            '<strong>' + escapeHtml(session.title || "Chat session") + '</strong>' +
            '<span>' + escapeHtml(formatHistoryTime(session.updatedAt)) + '</span>' +
          '</button>';
      }).join("");
    }

    function renderWelcomeMessage(text) {
      appendMessage("agent", text, "", { skipHistory: true });
    }

    function loadChatSession(sessionId) {
      const session = readChatHistory().find(function(item) {
        return item && item.id === sessionId;
      });
      if (!session) {
        return;
      }
      conversationId = session.id;
      try {
        window.localStorage.setItem(CHAT_SESSION_KEY, conversationId);
      } catch (error) {
        // Ignore storage failures.
      }
      conversation.innerHTML = "";
      (session.messages || []).forEach(function(message) {
        appendMessage(message.role || "agent", message.text || "", "", { skipHistory: true });
      });
      renderChatHistoryList();
      promptBox.focus();
    }

    function loadCurrentChatSession() {
      const session = readChatHistory().find(function(item) {
        return item && item.id === conversationId;
      });
      if (session && Array.isArray(session.messages) && session.messages.length) {
        loadChatSession(session.id);
        return;
      }
      renderWelcomeMessage("**Xin chào.** Mình đang vận hành ở chế độ AI operations & RCA copilot. Anh có thể hỏi về log hạ tầng, yêu cầu điều tra RCA/root cause, command kiểm tra, tạo report, gửi Gmail, hoặc điều khiển alert/log generator. Nếu câu lệnh có thể thay đổi runtime nhưng thiếu ngữ cảnh, mình sẽ hỏi lại trước.");
      renderChatHistoryList();
    }

    function startNewChatSession() {
      conversationId = newConversationId();
      try {
        window.localStorage.setItem(CHAT_SESSION_KEY, conversationId);
      } catch (error) {
        // Ignore storage failures; the in-memory id still separates this browser session.
      }
      conversation.innerHTML = "";
      renderWelcomeMessage("**New chat.** Mình đã tách ngữ cảnh hội thoại. Câu tiếp theo sẽ được xử lý như một Log Sentinel/RCA investigation mới.");
      renderChatHistoryList();
      promptBox.focus();
    }

    function readRcaHistory() {
      try {
        const parsed = JSON.parse(window.localStorage.getItem(RCA_HISTORY_KEY) || "[]");
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    }

    function writeRcaHistory(history) {
      try {
        window.localStorage.setItem(RCA_HISTORY_KEY, JSON.stringify(history.slice(0, 5)));
      } catch (error) {
        // Ignore storage failures; the current RCA result still stays visible.
      }
    }

    function compactHistoryLabel(value, fallback) {
      const text = String(value || fallback || "").trim();
      if (!text) {
        return "RCA search";
      }
      return text.length > 54 ? text.slice(0, 51) + "..." : text;
    }

    function rcaHistoryTitle(entry) {
      const analysis = (entry && entry.analysis) || {};
      return compactHistoryLabel(
        (entry && entry.impact) || analysis.impact || analysis.focus_text || analysis.incident_id,
        "RCA search from current logs"
      );
    }

    function rcaHistoryScope(entry) {
      const analysis = (entry && entry.analysis) || {};
      if (entry && entry.start && entry.end) {
        return String(entry.start) + " -> " + String(entry.end);
      }
      if (entry && entry.lookback) {
        return "last " + String(entry.lookback) + "h";
      }
      return analysis.scope_label || analysis.workspace_mode || "RCA";
    }

    function saveRcaHistory(entry) {
      const now = new Date().toISOString();
      const id = entry.id || "rca-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
      const normalized = Object.assign({}, entry, {
        id: id,
        title: rcaHistoryTitle(entry),
        updatedAt: now
      });
      const history = readRcaHistory().filter(function(item) {
        return item && item.id !== id;
      });
      writeRcaHistory([normalized].concat(history).sort(function(a, b) {
        return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
      }));
      return normalized;
    }

    function renderRcaHistoryList() {
      if (!rcaHistoryList) {
        return;
      }
      const history = readRcaHistory().slice(0, 5);
      if (!history.length) {
        rcaHistoryList.innerHTML = '<span class="history-empty">No RCA searches yet.</span>';
        return;
      }
      rcaHistoryList.innerHTML = history.map(function(item) {
        const active = item.id === state.activeRcaHistoryId ? " is-active" : "";
        const detail = [
          formatHistoryTime(item.updatedAt),
          rcaHistoryScope(item)
        ].filter(Boolean).join(" | ");
        return '' +
          '<button class="history-item' + active + '" type="button" data-rca-history-id="' + escapeHtml(item.id) + '">' +
            '<strong>' + escapeHtml(rcaHistoryTitle(item)) + '</strong>' +
            '<span>' + escapeHtml(detail) + '</span>' +
          '</button>';
      }).join("");
    }

    function loadRcaHistory(historyId) {
      const item = readRcaHistory().find(function(entry) {
        return entry && entry.id === historyId;
      });
      if (!item) {
        return;
      }
      const impact = document.getElementById("rca-impact");
      const lookback = document.getElementById("rca-lookback");
      const start = document.getElementById("rca-start");
      const end = document.getElementById("rca-end");
      if (impact) {
        impact.value = item.impact || "";
      }
      if (lookback) {
        lookback.value = item.lookback || "";
      }
      if (start) {
        start.value = item.start || "";
      }
      if (end) {
        end.value = item.end || "";
      }
      state.rcaWorkspaceHasRun = true;
      state.rcaWorkspaceAnalysis = item.analysis || null;
      state.activeRcaHistoryId = item.id;
      renderRcaWorkspaceAnalysis(state.rcaWorkspaceAnalysis);
      renderRcaHistoryList();
      switchRailTab("rca");
    }

    async function copyText(value, button) {
      try {
        await navigator.clipboard.writeText(value);
      } catch (error) {
        const textarea = document.createElement("textarea");
        textarea.value = value;
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
      }
      const original = button.textContent;
      button.textContent = "Copied";
      setTimeout(function() {
        button.textContent = original;
      }, 1400);
    }

    function setBusy(value) {
      state.busy = value;
      sendButton.disabled = value;
      sendButton.querySelector("span:first-child").textContent = value ? "Working" : "Send";
    }

    async function askAgent(message) {
      const text = message.trim();
      if (!text || state.busy) {
        return;
      }

      appendMessage("user", text);
      promptBox.value = "";
      setBusy(true);
      const typingRow = appendMessage("agent", "Đang phân tích ngữ cảnh, log và runbook...", "typing");

      try {
        const response = await fetch("/invocations", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            message: text,
            conversation_id: conversationId,
            dry_run: dryRunBox.checked
          })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.message || payload.error || "Request failed");
        }
        typingRow.remove();
        appendMessage("agent", payload.answer || "No answer returned.");
        refreshStatus();
      } catch (error) {
        typingRow.remove();
        appendMessage("agent", "Không xử lý được request: " + error.message);
      } finally {
        setBusy(false);
        promptBox.focus();
      }
    }

    function setText(id, value) {
      [id, "dash-" + id].forEach(function(targetId) {
        const el = document.getElementById(targetId);
        if (el) {
          el.textContent = value;
        }
      });
    }

    function setClassName(id, value) {
      [id, "dash-" + id].forEach(function(targetId) {
        const el = document.getElementById(targetId);
        if (el) {
          el.className = value;
        }
      });
    }

    function controlViewState(control, delivery) {
      const paused = Boolean(control && control.paused);
      const manualOff = Boolean(control && control.manual_off);
      if (delivery) {
        const effectiveState = String(delivery.state || "disabled").toLowerCase();
        const effectiveEnabled = !paused && !["disabled", "misconfigured", "worker_down", "worker-down", "error"].includes(effectiveState);
        return {
          state: delivery.state || "disabled",
          label: delivery.label || delivery.state || "unknown",
          detail: delivery.detail || "",
          enabled: effectiveEnabled
        };
      }
      if (manualOff) {
        return {
          state: "off",
          label: "off",
          detail: "Disabled until it is enabled again.",
          enabled: false
        };
      }
      if (paused) {
        return {
          state: "paused",
          label: "paused",
          detail: control.paused_until ? "Paused until " + control.paused_until : "Paused.",
          enabled: false
        };
      }
      return {
        state: "live",
        label: "on",
        detail: "Enabled.",
        enabled: true
      };
    }

    function controlBadgeClass(state) {
      const value = String(state || "").toLowerCase().replace(/_/g, "-");
      if (["live", "off", "paused", "dry-run", "disabled", "misconfigured", "worker-down", "error"].includes(value)) {
        return value;
      }
      return "disabled";
    }

    function updateControlWidget(uiKey, controlName, viewState) {
      const badge = document.getElementById("control-" + uiKey);
      const detail = document.getElementById("control-" + uiKey + "-detail");
      const toggle = document.querySelector('[data-runtime-control="' + controlName + '"]');
      if (badge) {
        badge.className = "control-badge " + controlBadgeClass(viewState.state);
        badge.textContent = viewState.label;
        badge.title = viewState.detail || "";
      }
      if (detail) {
        detail.textContent = viewState.detail || "Runtime control";
      }
      if (toggle) {
        toggle.classList.toggle("is-on", Boolean(viewState.enabled));
        toggle.setAttribute("aria-checked", viewState.enabled ? "true" : "false");
        toggle.title = viewState.enabled ? "Turn off" : "Turn on";
      }
    }

    function updateRuntimeControls(status) {
      const pauses = (status.runtime_controls && status.runtime_controls.pauses) || {};
      const delivery = status.delivery || {};
      updateControlWidget(
        "telegram",
        "telegram_alerts",
        controlViewState(pauses.telegram_alerts, delivery.telegram_alerts)
      );
      updateControlWidget("email", "email_reports", controlViewState(pauses.email_reports));
      updateControlWidget("loggen", "log_generation", controlViewState(pauses.log_generation));
      updateControlWidget("incident", "incident_generation", controlViewState(pauses.incident_generation));

      const config = status.config || {};
      const values = (status.runtime_controls && status.runtime_controls.values) || {};
      const interval = values.demo_log_interval_seconds || config.demo_log_interval_seconds || "";
      setText("control-interval", interval ? String(interval) + "s" : "-");
      const intervalInput = document.getElementById("control-interval-input");
      if (intervalInput && document.activeElement !== intervalInput) {
        intervalInput.value = interval || "";
      }
      const incidentInterval = values.incident_log_interval_seconds || config.incident_log_interval_seconds || "";
      setText("control-incident-interval", incidentInterval ? String(incidentInterval) + "s" : "-");
      const incidentIntervalInput = document.getElementById("control-incident-interval-input");
      if (incidentIntervalInput && document.activeElement !== incidentIntervalInput) {
        incidentIntervalInput.value = incidentInterval || "";
      }
      const reportTimeInput = document.getElementById("control-report-time-input");
      if (reportTimeInput && document.activeElement !== reportTimeInput) {
        reportTimeInput.value = config.report_time || "";
      }
      const scanIntervalInput = document.getElementById("control-scan-interval-input");
      if (scanIntervalInput && document.activeElement !== scanIntervalInput) {
        scanIntervalInput.value = config.scan_interval_seconds || "";
      }
    }

    function setRuntimeControlsBusy(value) {
      document.querySelectorAll("[data-runtime-control], #control-interval-save, #control-interval-input, #control-incident-interval-save, #control-incident-interval-input, #control-report-time-save, #control-report-time-input, #control-scan-interval-save, #control-scan-interval-input").forEach(function(element) {
        element.disabled = value;
      });
    }

    async function updateRuntimeControl(payload) {
      setRuntimeControlsBusy(true);
      try {
        const response = await fetch("/runtime-controls", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.message || result.error || "Runtime control update failed");
        }
        await refreshStatus();
      } catch (error) {
        appendMessage("agent", "Không cập nhật được runtime control: " + error.message);
      } finally {
        setRuntimeControlsBusy(false);
      }
    }

    function severityClass(severity) {
      const value = String(severity || "info").toLowerCase();
      if (["critical", "error", "warning"].includes(value)) {
        return value;
      }
      return "info";
    }

    function updatePosture(severity) {
      const critical = severity.critical || 0;
      const error = severity.error || 0;
      const warning = severity.warning || 0;
      if (critical > 0) {
        setText("posture-label", "Incident");
        setText("posture-detail", critical + " critical alert cần xử lý trước");
        return;
      }
      if (error > 0 || warning > 0) {
        setText("posture-label", "Watch");
        setText("posture-detail", (error + warning) + " alert cần theo dõi");
        return;
      }
      setText("posture-label", "Stable");
      setText("posture-detail", "Không có alert mức cao trong cửa sổ báo cáo");
    }

    function renderAlerts(alerts) {
      const lists = ["alert-list", "dash-alert-list"]
        .map(function(id) { return document.getElementById(id); })
        .filter(Boolean);
      if (!alerts || !alerts.length) {
        lists.forEach(function(list) {
          list.innerHTML = '<p class="empty">Không có warning/error/critical trong cửa sổ hiện tại.</p>';
        });
        return;
      }
      const html = alerts.slice(0, 5).map(function(alert) {
        const severity = severityClass(alert.severity);
        return '' +
          '<article class="alert-item">' +
            '<span class="mini-chip ' + severity + '">' + escapeHtml(String(alert.severity || "info").toUpperCase()) + '</span>' +
            '<strong>' + escapeHtml(alert.domain || "-") + " / " + escapeHtml(alert.source || "-") + '</strong>' +
            '<p>' + escapeHtml(alert.event_type || "-") + ': ' + escapeHtml(alert.message || "") + '</p>' +
          '</article>';
      }).join("");
      lists.forEach(function(list) {
        list.innerHTML = html;
      });
    }

    function renderRcaWorkspace(rca) {
      const scenarios = (rca && rca.available_log_scenarios) || [];
      updateRcaScenarioOptions(scenarios);
      if (!state.rcaWorkspaceHasRun) {
        renderRcaWorkspaceEmpty();
        return;
      }
      renderRcaWorkspaceAnalysis(state.rcaWorkspaceAnalysis);
    }

    function renderRcaWorkspaceEmpty(message) {
      const confidence = document.getElementById("rca-workspace-confidence");
      const result = document.getElementById("rca-workspace-result");
      if (!confidence || !result) {
        return;
      }
      const resultMessage = message || "Chưa chạy RCA search trong tab này.";
      const actionMessage = message
        ? "Kết quả RCA trước đó đã được xóa. Chạy Analyze Current Logs để phân tích lại log hiện tại."
        : "Nhập impact/symptom hoặc bật Incident generator trong Runtime controls, sau đó chạy Analyze Current Logs.";
      confidence.innerHTML = '--<span>confidence</span>';
      result.innerHTML = '' +
        '<div class="rca-result-block">' +
          '<h4>Most Likely Root Cause</h4>' +
          '<p class="rca-root-cause">' + escapeHtml(resultMessage) + '</p>' +
        '</div>' +
        '<div class="rca-result-block">' +
          '<h4>Evidence</h4>' +
          '<ul class="rca-compact-list"><li>Chưa có log evidence được chọn.</li></ul>' +
        '</div>' +
        '<div class="rca-result-block">' +
          '<h4>Analyze</h4>' +
          '<ul class="rca-compact-list"><li>' + escapeHtml(actionMessage) + '</li></ul>' +
        '</div>' +
        '<div class="rca-result-block">' +
          '<h4>Action</h4>' +
          '<ul class="rca-compact-list"><li>Chạy Analyze Current Logs khi đã có incident context.</li></ul>' +
        '</div>';
    }

    function updateRcaScenarioOptions(scenarios) {
      const select = document.getElementById("rca-scenario");
      if (!select || !scenarios.length) {
        return;
      }
      const current = select.value;
      const key = scenarios.join("|");
      if (state.rcaScenarios.join("|") === key) {
        return;
      }
      state.rcaScenarios = scenarios.slice();
      select.innerHTML = scenarios.map(function(name) {
        return '<option value="' + escapeHtml(name) + '">' + escapeHtml(name) + '</option>';
      }).join("");
      if (scenarios.includes(current)) {
        select.value = current;
      }
    }

    function renderRcaWorkspaceAnalysis(analysis) {
      const confidence = document.getElementById("rca-workspace-confidence");
      const result = document.getElementById("rca-workspace-result");
      if (!confidence || !result) {
        return;
      }
      if (!analysis || !analysis.incident_id || analysis.incident_id === "LOG-RCA-NONE") {
        const emptyScope = analysis && analysis.scope_label ? String(analysis.scope_label) : "selected log window";
        confidence.innerHTML = '--<span>confidence</span>';
        result.innerHTML = '' +
          '<div class="rca-result-block">' +
            '<h4>Most Likely Root Cause</h4>' +
            '<p class="rca-root-cause">Chưa tìm thấy RCA candidate đủ mạnh trong log window đã chọn.</p>' +
            '<p class="rca-scope-line"><strong>Scope:</strong> ' + escapeHtml(emptyScope) + '</p>' +
          '</div>' +
          '<div class="rca-result-block">' +
            '<h4>Evidence</h4>' +
            '<ul class="rca-compact-list"><li>Chưa thấy log evidence khớp với impact/symptom trong window này.</li></ul>' +
          '</div>' +
          '<div class="rca-result-block">' +
            '<h4>Analyze</h4>' +
            '<ul class="rca-compact-list"><li>Log window hiện tại chưa tạo được correlated event cluster đủ mạnh.</li></ul>' +
          '</div>' +
          '<div class="rca-result-block">' +
            '<h4>Action</h4>' +
            '<ul class="rca-compact-list"><li>Mở rộng time window hoặc nhập impact/symptom cụ thể hơn rồi chạy lại RCA.</li></ul>' +
          '</div>';
        return;
      }
      confidence.innerHTML = String(analysis.confidence ?? 0) + '%<span>confidence</span>';
      const actions = analysis.recommended_actions || {};
      const evidence = (analysis.evidence || []).slice(0, 5);
      const immediate = (actions.immediate_actions || []).slice(0, 3);
      const verification = (actions.verification_actions || []).slice(0, 2);
      const prevention = (actions.long_term_prevention || []).slice(0, 1);
      const focusTerms = (analysis.focus_terms || []).slice(0, 6);
      const timeline = (analysis.timeline || []).slice(0, 3);
      const missingData = (analysis.missing_data || []).slice(0, 2);
      const scenarioLabel = String(analysis.workspace_scenario || analysis.scenario || "");
      const modeLabel = analysis.workspace_mode === "generated_incident"
        ? "generated incident"
        : analysis.workspace_mode === "current_logs"
          ? "current logs"
          : "log window";
      const scopeLabel = String(analysis.scope_label || (scenarioLabel ? "generated " + scenarioLabel + " incident burst" : modeLabel));
      const scenarioScope = scenarioLabel
        ? ' <strong>Scenario:</strong> ' + escapeHtml(scenarioLabel)
        : "";
      const evidenceItems = evidence.length ? evidence.map(function(item) {
        return "Bằng chứng log: " + String(item);
      }) : timeline.map(function(item) {
        return "Bằng chứng timeline: " + [item.timestamp, item.source, item.event_type].filter(Boolean).join(" | ");
      });
      const analyzeItems = [
        String(analysis.summary || analysis.impact || "").trim()
          ? "Tóm tắt phân tích: " + String(analysis.summary || analysis.impact || "").trim()
          : "",
        "Trạng thái RCA: " + rcaVietnameseStatus(analysis.status) + "; confidence " + String(analysis.confidence ?? 0) + "%; " + String(analysis.correlated_events || 0) + " correlated event(s) trên " + String(analysis.analyzed_events || 0) + " analyzed event(s)."
      ].filter(Boolean);
      timeline.forEach(function(item) {
        analyzeItems.push(
          "Timeline: " + rcaTimelineText(item)
        );
      });
      missingData.forEach(function(item) {
        analyzeItems.push("Thiếu dữ liệu: " + String(item));
      });
      if (analysis.llm_guidance) {
        analyzeItems.push("Gợi ý LLM: " + String(analysis.llm_guidance));
      }
      const actionItems = immediate
        .concat(verification)
        .concat(prevention)
        .slice(0, 6);
      const finalActions = rcaVietnameseActions(analysis, actionItems.length ? actionItems : ["Collect more evidence before remediation."]);
      result.innerHTML = '' +
        '<div class="rca-result-block">' +
          '<h4>Most Likely Root Cause</h4>' +
          '<p class="rca-root-cause">Khả năng cao root cause là: ' + escapeHtml(analysis.most_likely_root_cause || analysis.summary || "-") + '</p>' +
          '<p class="rca-scope-line"><strong>Scope:</strong> ' + escapeHtml(scopeLabel) + scenarioScope + '</p>' +
          '<div class="rca-focus-chips">' +
            '<span>' + escapeHtml(String(analysis.severity || "info").toUpperCase()) + '</span>' +
            '<span>' + escapeHtml(String(analysis.status || "-")) + '</span>' +
            '<span>' + String(analysis.correlated_events || 0) + ' events</span>' +
            '<span>' + escapeHtml(modeLabel) + '</span>' +
            focusTerms.map(function(term) { return '<span>' + escapeHtml(term) + '</span>'; }).join("") +
          '</div>' +
        '</div>' +
        '<div class="rca-result-block">' +
          '<h4>Evidence</h4>' +
          '<ul class="rca-compact-list">' +
            evidenceItems.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join("") +
          '</ul>' +
        '</div>' +
        '<div class="rca-result-block">' +
          '<h4>Analyze</h4>' +
          '<ul class="rca-compact-list">' +
            analyzeItems.slice(0, 6).map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join("") +
          '</ul>' +
        '</div>' +
        '<div class="rca-result-block">' +
          '<h4>Action</h4>' +
          '<ul class="rca-compact-list">' +
            finalActions.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join("") +
          '</ul>' +
          '<div class="rca-command-list">' + rcaCommandCards(analysis) + '</div>' +
        '</div>';
    }

    function setRcaWorkspaceBusy(value) {
      ["rca-analyze", "rca-send-chat", "rca-clear", "rca-impact", "rca-lookback", "rca-start", "rca-end"].forEach(function(id) {
        const element = document.getElementById(id);
        if (element) {
          element.disabled = value;
        }
      });
    }

    function clearRcaWorkspace() {
      const impact = document.getElementById("rca-impact");
      const lookback = document.getElementById("rca-lookback");
      const start = document.getElementById("rca-start");
      const end = document.getElementById("rca-end");
      state.rcaWorkspaceHasRun = false;
      state.rcaWorkspaceAnalysis = null;
      state.activeRcaHistoryId = "";
      if (impact) {
        impact.value = "";
      }
      if (lookback) {
        lookback.value = "";
      }
      if (start) {
        start.value = "";
      }
      if (end) {
        end.value = "";
      }
      renderRcaWorkspaceEmpty();
      renderRcaHistoryList();
      if (impact) {
        impact.focus();
      }
    }

    async function runRcaWorkspace(mode) {
      const impact = document.getElementById("rca-impact").value.trim();
      const lookback = Number(document.getElementById("rca-lookback").value || 1);
      const start = document.getElementById("rca-start").value.trim();
      const end = document.getElementById("rca-end").value.trim();
      const scenarioSelect = document.getElementById("rca-scenario");
      const scenario = scenarioSelect ? scenarioSelect.value || "broadcast_loop" : "broadcast_loop";
      const endpoint = mode === "generate" ? "/rca/logs/generate" : "/rca/logs/analyze";
      const payload = {
        impact: impact,
        lookback_hours: Number.isFinite(lookback) && lookback > 0 ? lookback : 1
      };
      if (start && end) {
        payload.start_time = start;
        payload.end_time = end;
      }
      if (mode === "generate") {
        payload.scenario = scenario;
      }
      setRcaWorkspaceBusy(true);
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.message || result.error || "RCA request failed");
        }
        state.rcaWorkspaceHasRun = true;
        const analysis = result.analysis || {};
        if (mode === "generate") {
          analysis.workspace_mode = "generated_incident";
          analysis.workspace_scenario = String(result.scenario || scenario);
          analysis.scope_label = analysis.scope_label || "generated " + analysis.workspace_scenario + " incident burst";
        } else {
          analysis.workspace_mode = "current_logs";
          analysis.workspace_scenario = "";
          analysis.scope_label = analysis.scope_label || (start && end ? "selected time range" : "last " + String(payload.lookback_hours) + "h");
        }
        state.rcaWorkspaceAnalysis = analysis;
        const savedHistory = saveRcaHistory({
          mode: mode,
          scenario: mode === "generate" ? scenario : "",
          impact: impact,
          lookback: payload.lookback_hours,
          start: start,
          end: end,
          analysis: analysis
        });
        state.activeRcaHistoryId = savedHistory.id;
        renderRcaWorkspaceAnalysis(analysis);
        renderRcaHistoryList();
        switchRailTab("rca");
        const context = mode === "generate" ? "generated " + scenario : "current logs";
        appendMessage("agent", "RCA workspace updated (" + context + "): " + String(analysis.incident_id || "analysis complete"));
        await refreshStatus();
      } catch (error) {
        appendMessage("agent", "Không chạy được RCA workspace: " + error.message);
      } finally {
        setRcaWorkspaceBusy(false);
      }
    }

    function sendRcaWorkspaceAsChat() {
      const impactBox = document.getElementById("rca-impact");
      const lookbackBox = document.getElementById("rca-lookback");
      const startBox = document.getElementById("rca-start");
      const endBox = document.getElementById("rca-end");
      const impact = impactBox.value.trim();
      const lookback = Number(lookbackBox.value || 0);
      if (!impact) {
        switchRailTab("rca");
        appendMessage("agent", "RCA chat cần impact/symptom trước khi gửi sang agent.");
        impactBox.focus();
        return;
      }
      const windowText = Number.isFinite(lookback) && lookback > 0
        ? " trong " + String(lookback) + " gio"
        : "";
      const rangeText = startBox.value && endBox.value
        ? " tu " + startBox.value + " den " + endBox.value
        : windowText;
      askAgent("phan tich RCA dua tren log hien tai: " + impact + rangeText);
    }

    function renderDomainBars(domainCounts) {
      const roots = ["domain-bars", "dash-domain-bars"]
        .map(function(id) { return document.getElementById(id); })
        .filter(Boolean);
      const entries = Object.entries(domainCounts || {});
      if (!entries.length) {
        roots.forEach(function(root) {
          root.innerHTML = '<p class="empty">Chưa có domain count.</p>';
        });
        return;
      }
      const max = Math.max(...entries.map(function(item) { return Number(item[1]) || 0; }), 1);
      const html = entries.map(function(item) {
        const name = item[0];
        const value = Number(item[1]) || 0;
        const width = Math.round((value / max) * 100);
        return '' +
          '<div class="domain-row">' +
            '<span>' + escapeHtml(name) + '</span>' +
            '<div class="bar"><span style="width:' + width + '%"></span></div>' +
            '<strong>' + value + '</strong>' +
          '</div>';
      }).join("");
      roots.forEach(function(root) {
        root.innerHTML = html;
      });
    }

    async function refreshStatus() {
      try {
        const response = await fetch("/status");
        const status = await response.json();
        if (!response.ok) {
          throw new Error(status.message || "status failed");
        }

        setClassName("health-dot", "dot ok");
        setText("health-text", "online");

        const config = status.config || {};
        const severity = status.severity_counts || {};
        setText("metric-events", String(status.report_window_events ?? status.parsed_events ?? "-"));
        setText("metric-critical", String(severity.critical || 0));
        setText("metric-error", String(severity.error || 0));
        setText("metric-warning", String(severity.warning || 0));
        updatePosture(severity);

        const modelName = config.llm_model ? String(config.llm_model).split("/").pop() : "MiniMax M2.5";
        setText("model-chip", modelName);
        setText("window-chip", String(config.report_lookback_hours || 24) + "h");
        setText("mode-chip", config.log_source_mode || "runtime");
        setText("fact-report-time", config.report_time || "-");
        setText("fact-scan", String(config.scan_interval_seconds || "-") + "s");
        setText("fact-timezone", config.app_timezone || "-");
        setText("report-timezone-label", "(" + (config.app_timezone || "timezone") + ")");
        setText("fact-source", config.log_source_mode || "-");

        updateRuntimeControls(status);

        renderAlerts(status.top_alerts || []);
        renderRcaWorkspace(status.rca || {});
        renderDomainBars(status.domain_counts || {});
      } catch (error) {
        setClassName("health-dot", "dot bad");
        setText("health-text", "offline");
        setText("posture-label", "Degraded");
        setText("posture-detail", "Không đọc được endpoint status");
      }
    }

    form.addEventListener("submit", function(event) {
      event.preventDefault();
      askAgent(promptBox.value);
    });

    promptBox.addEventListener("keydown", function(event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    document.querySelectorAll("[data-prompt]").forEach(function(button) {
      button.dataset.promptBound = "true";
      button.addEventListener("click", function() {
        switchWorkspaceView("chat");
        askAgent(button.dataset.prompt);
      });
    });

    document.addEventListener("click", function(event) {
      const button = event.target.closest("[data-prompt]");
      if (!button || button.dataset.promptBound === "true") {
        return;
      }
      switchWorkspaceView("chat");
      askAgent(button.dataset.prompt);
    });

    document.querySelectorAll("[data-view-tab]").forEach(function(tab) {
      tab.addEventListener("click", function() {
        switchWorkspaceView(tab.dataset.viewTab);
      });
    });

    switchWorkspaceView(new URLSearchParams(window.location.search).get("view") || document.body.dataset.view);

    document.querySelectorAll("[data-rail-tab]").forEach(function(tab) {
      tab.addEventListener("click", function() {
        switchRailTab(tab.dataset.railTab);
      });
    });

    document.querySelectorAll("[data-runtime-control]").forEach(function(button) {
      button.addEventListener("click", function() {
        const currentlyEnabled = button.getAttribute("aria-checked") === "true";
        updateRuntimeControl({
          control: button.dataset.runtimeControl,
          enabled: !currentlyEnabled
        });
      });
    });

    document.getElementById("rca-analyze").addEventListener("click", function() {
      runRcaWorkspace("analyze");
    });

    document.getElementById("rca-send-chat").addEventListener("click", function() {
      sendRcaWorkspaceAsChat();
    });

    document.getElementById("rca-clear").addEventListener("click", function() {
      clearRcaWorkspace();
    });

    document.getElementById("new-chat").addEventListener("click", function() {
      startNewChatSession();
    });

    if (quickActionSelect) {
      quickActionSelect.addEventListener("change", function() {
        const prompt = quickActionSelect.value;
        quickActionSelect.value = "";
        if (!prompt) {
          return;
        }
        switchWorkspaceView("chat");
        askAgent(prompt);
      });
    }

    if (quickImpactSelect) {
      quickImpactSelect.addEventListener("change", function() {
        const prompt = quickImpactSelect.value;
        quickImpactSelect.value = "";
        if (!prompt) {
          return;
        }
        switchWorkspaceView("chat");
        askAgent(prompt);
      });
    }

    if (chatHistoryList) {
      chatHistoryList.addEventListener("click", function(event) {
        const button = event.target.closest("[data-history-id]");
        if (!button) {
          return;
        }
        switchWorkspaceView("chat");
        loadChatSession(button.dataset.historyId);
      });
    }

    if (rcaHistoryList) {
      rcaHistoryList.addEventListener("click", function(event) {
        const button = event.target.closest("[data-rca-history-id]");
        if (!button) {
          return;
        }
        switchWorkspaceView("rca");
        loadRcaHistory(button.dataset.rcaHistoryId);
      });
    }

    document.getElementById("control-interval-save").addEventListener("click", function() {
      const input = document.getElementById("control-interval-input");
      const seconds = Number(input.value);
      if (!Number.isFinite(seconds) || seconds < 1 || seconds > 86400) {
        appendMessage("agent", "Interval phải nằm trong khoảng 1 đến 86400 giây.");
        input.focus();
        return;
      }
      updateRuntimeControl({
        setting: "demo_log_interval_seconds",
        seconds: seconds
      });
    });

    document.getElementById("control-incident-interval-save").addEventListener("click", function() {
      const input = document.getElementById("control-incident-interval-input");
      const seconds = Number(input.value);
      if (!Number.isFinite(seconds) || seconds < 1 || seconds > 86400) {
        appendMessage("agent", "Incident interval must be between 1 and 86400 seconds.");
        input.focus();
        return;
      }
      updateRuntimeControl({
        setting: "incident_log_interval_seconds",
        seconds: seconds
      });
    });

    document.getElementById("control-report-time-save").addEventListener("click", function() {
      const input = document.getElementById("control-report-time-input");
      const value = input.value;
      if (!/^\d{2}:\d{2}$/.test(value || "")) {
        appendMessage("agent", "Report time must use HH:MM format.");
        input.focus();
        return;
      }
      updateRuntimeControl({
        setting: "report_time",
        value: value
      });
    });

    document.getElementById("control-scan-interval-save").addEventListener("click", function() {
      const input = document.getElementById("control-scan-interval-input");
      const seconds = Number(input.value);
      if (!Number.isFinite(seconds) || seconds < 1 || seconds > 86400) {
        appendMessage("agent", "Scan interval must be between 1 and 86400 seconds.");
        input.focus();
        return;
      }
      updateRuntimeControl({
        setting: "scan_interval_seconds",
        seconds: seconds
      });
    });

    function handleCopyClick(event) {
      const button = event.target.closest("[data-copy]");
      if (!button) {
        return;
      }
      const codeBlock = button.closest(".code-block");
      const commandCard = button.closest(".command-card");
      if (codeBlock) {
        const code = codeBlock.querySelector("code");
        copyText(code ? code.textContent : "", button);
        return;
      }
      if (commandCard) {
        const command = commandCard.querySelector(".command-text");
        copyText(command ? command.textContent : "", button);
      }
    }

    conversation.addEventListener("click", handleCopyClick);
    document.getElementById("rca-workspace-result").addEventListener("click", handleCopyClick);

    appendMessage(
      "agent",
      "**Xin chào.** Mình đang vận hành ở chế độ AI operations & RCA copilot. Anh có thể hỏi về log hạ tầng, yêu cầu điều tra RCA/root cause, command kiểm tra, tạo report, gửi Gmail, hoặc điều khiển alert/log generator. Nếu câu lệnh có thể thay đổi runtime nhưng thiếu ngữ cảnh, mình sẽ hỏi lại trước."
    );
    conversation.innerHTML = "";
    loadCurrentChatSession();
    renderRcaHistoryList();
    refreshStatus();
    setInterval(refreshStatus, 15000);
  </script>
</body>
</html>
"""
