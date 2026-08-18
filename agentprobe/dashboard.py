"""AgentProbe Web Dashboard: 自包含 HTML(内联 CSS/JS),零额外依赖。

提供:
- /dashboard          — 首页:体检历史总览,指标卡片 + 趋势微图
- /dashboard/{run_id} — 详情:Trace 时间线可视化 + 评分明细 + 标签分布
- /dashboard/compare  — 对比:两次运行差异分析 + CI 门禁判定
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from .regression import compare as compare_reports
from .regression import gate as gate_check
from .regression import load_report
from .report import aggregate
from .schemas import CaseResult, RunReport


# ═══════════ Morandi 莫兰迪浅色系 CSS ═══════════

_COLOR = """
:root {
  /* Base — warm cream */
  --bg: #f6f3ef; --bg-warm: #faf8f5;
  --page-gradient: linear-gradient(180deg, #faf8f5 0%, #f3f0eb 40%, #efe9e2 100%);

  /* Card color families — 6 variants for rotation */
  --c-rose-bg: #fbf7f7; --c-rose-border: #e5d5d5; --c-rose-accent: #c4a0a0; --c-rose-hover: #f0e2e2;
  --c-sage-bg: #f6f9f6; --c-sage-border: #d4e2d4; --c-sage-accent: #95b095; --c-sage-hover: #e2eee2;
  --c-sky-bg: #f5f7fa; --c-sky-border: #d3dce6; --c-sky-accent: #95a8bd; --c-sky-hover: #e0e8f0;
  --c-lav-bg: #f8f6fb; --c-lav-border: #dbd5e5; --c-lav-accent: #b0a0c4; --c-lav-hover: #eae2f2;
  --c-cha-bg: #faf9f4; --c-cha-border: #e2ddc8; --c-cha-accent: #b8ab88; --c-cha-hover: #f0ecd8;
  --c-stone-bg: #f7f5f2; --c-stone-border: #dbd6cf; --c-stone-accent: #b0a898; --c-stone-hover: #e8e4dc;

  /* Card defaults (rose) */
  --card-bg: var(--c-rose-bg); --card-border: var(--c-rose-border);
  --card-accent: var(--c-rose-accent); --card-hover: var(--c-rose-hover);

  /* Text */
  --text: #3d3833; --text2: #7a736b; --text3: #b0a9a0; --text4: #d0c9c2;

  /* Status — Morandi muted */
  --green: #7aaa8a; --green-bg: #e8f2ea; --green-border: #c5dcc8;
  --red: #c4887a; --red-bg: #f5e8e5; --red-border: #e5ccc5;
  --amber: #c4a860; --amber-bg: #f5f0e0; --amber-border: #e5d8b8;
  --purple: #9a8ab8; --purple-bg: #ede8f5; --purple-border: #d8cfe5;
  --blue: #8a9fb8; --blue-bg: #e8eef5; --blue-border: #d0dae5;
  --cyan: #7a9a9a; --cyan-bg: #e5f0f0; --cyan-border: #c8dcdc;

  /* Accent */
  --accent: #8a9fb8; --accent-glow: rgba(138,159,184,.15);

  /* Layout */
  --radius: 16px; --radius-sm: 10px; --radius-xs: 6px;
  --shadow-sm: 0 1px 3px rgba(60,50,40,.04);
  --shadow: 0 2px 12px rgba(60,50,40,.06);
  --shadow-lg: 0 4px 24px rgba(60,50,40,.08);

  font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg); color: var(--text);
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  max-width: 1280px; margin: 0 auto; padding: 36px 28px; line-height: 1.6;
  background: var(--page-gradient);
  min-height: 100vh;
}

/* ── nav ── */
.nav {
  display: flex; align-items: center; gap: 16px; padding: 16px 24px;
  background: rgba(255,255,255,.7); backdrop-filter: blur(12px);
  border: 1px solid var(--text4); border-radius: var(--radius);
  margin-bottom: 32px; box-shadow: var(--shadow-sm);
}
.nav-brand {
  font-size: 19px; font-weight: 800; letter-spacing: -.02em; text-decoration: none;
  color: var(--text); display: flex; align-items: center; gap: 8px;
}
.nav-brand .brand-dot { width: 10px; height: 10px; border-radius: 50%;
  background: linear-gradient(135deg, var(--c-rose-accent), var(--c-lav-accent)); }
.nav-spacer { flex: 1; }
.nav-link {
  color: var(--text2); text-decoration: none; font-size: 13px; font-weight: 500;
  padding: 8px 16px; border-radius: 20px; transition: all .2s;
  background: transparent; border: 1px solid transparent;
}
.nav-link:hover { color: var(--text); background: rgba(255,255,255,.8); border-color: var(--text4); }
.nav-link.active { color: var(--c-rose-accent); background: var(--c-rose-bg); border-color: var(--c-rose-border); }
.nav-badge {
  font-size: 11px; color: var(--text3); background: rgba(255,255,255,.6);
  padding: 5px 12px; border-radius: 20px; border: 1px solid var(--text4);
}

/* ── hero ── */
.hero {
  background: linear-gradient(135deg, #fdfcfb 0%, #f7f3f0 40%, #f2eeea 100%);
  border: 1px solid var(--text4); border-radius: var(--radius);
  padding: 32px 36px; margin-bottom: 28px; position: relative; overflow: hidden;
  box-shadow: var(--shadow);
}
.hero::before {
  content: ''; position: absolute; top: -60px; right: -40px;
  width: 200px; height: 200px; border-radius: 50%;
  background: radial-gradient(circle, rgba(196,160,160,.12) 0%, transparent 70%);
  pointer-events: none;
}
.hero::after {
  content: ''; position: absolute; bottom: -30px; right: 140px;
  width: 100px; height: 100px; border-radius: 50%;
  background: radial-gradient(circle, rgba(176,160,196,.1) 0%, transparent 70%);
  pointer-events: none;
}
.hero h1 { font-size: 26px; font-weight: 800; letter-spacing: -.03em; position: relative; z-index: 1; color: var(--text); }
.hero p { color: var(--text2); font-size: 14px; margin-top: 6px; position: relative; z-index: 1; max-width: 600px; }
.hero-meta { display: flex; gap: 18px; margin-top: 14px; position: relative; z-index: 1; flex-wrap: wrap; }
.hero-meta-item { font-size: 13px; color: var(--text2); display: flex; align-items: center; gap: 5px;
  background: rgba(255,255,255,.5); padding: 5px 14px; border-radius: 20px; border: 1px solid var(--text4); }
.hero-meta-item strong { color: var(--text); font-weight: 600; }

/* ── stat row ── */
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-bottom: 28px; }
.stat {
  background: #fff; border: 1px solid var(--text4); border-radius: var(--radius);
  padding: 22px 24px; transition: transform .2s, box-shadow .2s;
  cursor: default; position: relative; overflow: hidden; box-shadow: var(--shadow-sm);
}
.stat::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
  border-radius: var(--radius) var(--radius) 0 0;
}
.stat:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); }
.stat-icon { font-size: 22px; margin-bottom: 8px; display: block; }
.stat-value { font-size: 32px; font-weight: 800; letter-spacing: -.03em; line-height: 1.1; }
.stat-label { font-size: 11px; color: var(--text2); margin-top: 6px;
  text-transform: uppercase; letter-spacing: .05em; font-weight: 700; }
.stat-sub { font-size: 11px; color: var(--text3); margin-top: 2px; }

/* stat color variants */
.stat.s-rose::before { background: linear-gradient(90deg, var(--c-rose-accent), #d4b8b8); }
.stat.s-rose .stat-value { color: var(--c-rose-accent); }
.stat.s-sage::before { background: linear-gradient(90deg, var(--c-sage-accent), #b0ccb0); }
.stat.s-sage .stat-value { color: var(--c-sage-accent); }
.stat.s-sky::before { background: linear-gradient(90deg, var(--c-sky-accent), #b0bed0); }
.stat.s-sky .stat-value { color: var(--c-sky-accent); }
.stat.s-lav::before { background: linear-gradient(90deg, var(--c-lav-accent), #c4b8d8); }
.stat.s-lav .stat-value { color: var(--c-lav-accent); }
.stat.s-cha::before { background: linear-gradient(90deg, var(--c-cha-accent), #ccc0a0); }
.stat.s-cha .stat-value { color: var(--c-cha-accent); }

/* ── card ── */
.card {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: var(--radius); padding: 22px 26px; margin-bottom: 16px;
  transition: transform .2s, box-shadow .2s, border-color .2s;
  box-shadow: var(--shadow-sm);
}
.card:hover { border-color: var(--card-accent); box-shadow: var(--shadow); }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.card-title { font-weight: 700; font-size: 15px; letter-spacing: -.01em; }
.card-subtitle { font-size: 12px; color: var(--text3); margin-top: 3px; }
.card-badge { display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 14px; border-radius: 20px; font-size: 11px; font-weight: 700; }
.badge-pass { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }
.badge-fail { background: var(--red-bg); color: var(--red); border: 1px solid var(--red-border); }
.badge-warn { background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber-border); }
.badge-info { background: var(--blue-bg); color: var(--blue); border: 1px solid var(--blue-border); }

/* ── card color variants (rotated per item) ── */
.card.c-rose { --card-bg: var(--c-rose-bg); --card-border: var(--c-rose-border); --card-accent: var(--c-rose-accent); }
.card.c-sage { --card-bg: var(--c-sage-bg); --card-border: var(--c-sage-border); --card-accent: var(--c-sage-accent); }
.card.c-sky  { --card-bg: var(--c-sky-bg);  --card-border: var(--c-sky-border);  --card-accent: var(--c-sky-accent); }
.card.c-lav  { --card-bg: var(--c-lav-bg);  --card-border: var(--c-lav-border);  --card-accent: var(--c-lav-accent); }
.card.c-cha  { --card-bg: var(--c-cha-bg);  --card-border: var(--c-cha-border);  --card-accent: var(--c-cha-accent); }
.card.c-stone { --card-bg: var(--c-stone-bg); --card-border: var(--c-stone-border); --card-accent: var(--c-stone-accent); }

/* ── progress ── */
.progress { height: 8px; background: rgba(0,0,0,.06); border-radius: 6px; overflow: hidden; margin: 8px 0; }
.progress-fill { height: 100%; border-radius: 6px; transition: width .8s cubic-bezier(.4,0,.2,1); }
.progress-fill.green { background: linear-gradient(90deg, var(--green), #a0c8a5); }
.progress-fill.red { background: linear-gradient(90deg, var(--red), #d4a098); }
.progress-fill.amber { background: linear-gradient(90deg, var(--amber), #d4c088); }
.progress-fill.blue { background: linear-gradient(90deg, var(--blue), #b0c0d8); }
.progress-fill.purple { background: linear-gradient(90deg, var(--purple), #c0b0d8); }

/* ── tag ── */
.tag { display: inline-block; padding: 4px 12px; border-radius: 20px;
  font-size: 11px; font-weight: 600; margin: 2px 4px; letter-spacing: .01em; }
.tag-blue { background: var(--blue-bg); color: var(--blue); }
.tag-green { background: var(--green-bg); color: var(--green); }
.tag-red { background: var(--red-bg); color: var(--red); }
.tag-purple { background: var(--purple-bg); color: var(--purple); }
.tag-cyan { background: var(--cyan-bg); color: var(--cyan); }
.tag-amber { background: var(--amber-bg); color: var(--amber); }
.tag-rose { background: var(--c-rose-bg); color: var(--c-rose-accent); }
.tag-lav { background: var(--c-lav-bg); color: var(--c-lav-accent); }

/* ── trace ── */
.trace-container { margin: 8px 0 0 0; }
.trace-row { display: flex; align-items: flex-start; gap: 12px; padding: 7px 0; position: relative; }
.trace-row::before { content: ''; position: absolute; left: 10px; top: 28px;
  width: 2px; height: calc(100% - 18px); background: var(--text4); border-radius: 1px; }
.trace-row:last-child::before { display: none; }
.trace-dot { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 8px; font-weight: 800; margin-top: 2px; position: relative; z-index: 1; }
.dot-llm { background: var(--purple-bg); color: var(--purple); border: 2px solid var(--purple); }
.dot-tool { background: var(--blue-bg); color: var(--blue); border: 2px solid var(--blue); }
.dot-agent { background: var(--green-bg); color: var(--green); border: 2px solid var(--green); }
.dot-judge { background: var(--red-bg); color: var(--red); border: 2px solid var(--red); }
.trace-body { flex: 1; min-width: 0; }
.trace-name { font-weight: 700; font-size: 12px; }
.trace-meta { font-size: 10px; color: var(--text3); margin-top: 1px; }
.trace-io { font-size: 11px; color: var(--text2); margin-top: 2px;
  background: rgba(0,0,0,.02); padding: 5px 10px; border-radius: var(--radius-xs);
  word-break: break-all; max-height: 40px; overflow: hidden;
  border: 1px solid var(--text4); }
.trace-error { color: var(--red); font-weight: 700; font-size: 11px; margin-top: 2px; }

/* ── compare ── */
.compare-hero { display: grid; grid-template-columns: 1fr auto 1fr; gap: 20px;
  align-items: center; margin-bottom: 24px; }
.compare-col { text-align: center; padding: 20px; border-radius: var(--radius); }
.compare-col.c-base { background: var(--c-stone-bg); border: 1px solid var(--c-stone-border); }
.compare-col.c-new  { background: var(--c-sky-bg); border: 1px solid var(--c-sky-border); }
.compare-col .run-label { font-size: 11px; color: var(--text3); text-transform: uppercase;
  letter-spacing: .05em; font-weight: 700; margin-bottom: 8px; }
.compare-col .run-id { font-size: 14px; font-weight: 700; color: var(--text); word-break: break-all; }
.compare-col .run-agent { font-size: 12px; color: var(--text2); margin-top: 4px; }
.compare-vs {
  width: 48px; height: 48px; border-radius: 50%;
  background: #fff; border: 2px solid var(--text4);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800; color: var(--text3); flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.compare-summary {
  background: linear-gradient(135deg, #fdfcfb, #f8f5f2);
  border: 1px solid var(--text4); border-radius: var(--radius);
  padding: 20px 26px; margin-bottom: 20px; box-shadow: var(--shadow-sm);
}
.compare-summary h3 { font-size: 15px; font-weight: 700; margin-bottom: 6px; color: var(--text); }
.compare-summary p { font-size: 13px; color: var(--text2); line-height: 1.7; }

.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-bottom: 20px; }
.metric-card {
  background: #fff; border: 1px solid var(--text4); border-radius: var(--radius);
  padding: 18px 22px; box-shadow: var(--shadow-sm); transition: box-shadow .2s;
}
.metric-card:hover { box-shadow: var(--shadow); }
.metric-card .metric-name { font-size: 12px; font-weight: 700; color: var(--text2);
  text-transform: uppercase; letter-spacing: .04em; margin-bottom: 10px; }
.metric-card .metric-values { display: flex; align-items: flex-end; gap: 14px; }
.metric-card .metric-base, .metric-card .metric-new { flex: 1; }
.metric-card .metric-base .val, .metric-card .metric-new .val {
  font-size: 24px; font-weight: 800; letter-spacing: -.02em; line-height: 1;
}
.metric-card .metric-base .val { color: var(--text3); }
.metric-card .metric-new .val { color: var(--text); }
.metric-card .metric-base .lbl, .metric-card .metric-new .lbl {
  font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: .04em; margin-top: 3px;
}
.metric-card .metric-arrow { font-size: 18px; flex-shrink: 0; align-self: center; }
.metric-card .delta-bar {
  margin-top: 8px; height: 6px; border-radius: 3px;
  background: rgba(0,0,0,.05); overflow: hidden; position: relative;
}
.metric-card .delta-bar-fill {
  height: 100%; border-radius: 3px; transition: width .6s ease; position: absolute; left: 50%;
}
.metric-card .delta-bar-fill.better { background: linear-gradient(90deg, transparent, var(--green)); right: 50%; }
.metric-card .delta-bar-fill.worse { background: linear-gradient(90deg, var(--red), transparent); left: 0; }
.metric-card .delta-text { font-size: 12px; font-weight: 700; margin-top: 6px; }
.metric-card .metric-desc {
  font-size: 11px; color: var(--text3); margin-top: 8px; line-height: 1.4;
  border-top: 1px solid var(--text4); padding-top: 8px;
}

.gate-banner { padding: 16px 24px; border-radius: var(--radius);
  font-weight: 800; font-size: 15px; text-align: center; margin: 16px 0;
  box-shadow: var(--shadow-sm);
}
.gate-banner.pass { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }
.gate-banner.fail { background: var(--red-bg); color: var(--red); border: 1px solid var(--red-border); }

.case-section { margin-bottom: 16px; }
.case-section h4 { font-size: 13px; font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
.case-grid { display: flex; flex-wrap: wrap; gap: 6px; }

/* ── details ── */
details { margin: 4px 0; }
details summary { cursor: pointer; padding: 8px 0; font-size: 13px;
  color: var(--c-rose-accent); font-weight: 600; user-select: none; transition: color .15s; }
details summary:hover { color: var(--c-lav-accent); }
details[open] summary { margin-bottom: 8px; }

/* ── form ── */
.form-row { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 11px; color: var(--text3); text-transform: uppercase;
  font-weight: 700; letter-spacing: .05em; }
select, .btn {
  background: #fff; color: var(--text); border: 1px solid var(--text4);
  padding: 10px 16px; border-radius: var(--radius-sm); font-size: 13px;
  font-family: inherit; cursor: pointer; transition: all .2s; outline: none;
}
select:hover, .btn:hover { border-color: var(--c-sky-accent); }
select:focus-visible, .btn:focus-visible { border-color: var(--c-sky-accent); box-shadow: 0 0 0 3px rgba(138,159,184,.12); }
.btn-primary {
  background: var(--c-sage-accent); border-color: transparent; color: #fff;
  font-weight: 700; letter-spacing: .01em;
}
.btn-primary:hover { opacity: .9; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(149,176,149,.3); }
.btn-ghost { background: transparent; border-color: var(--text4); color: var(--text2); }
.btn-ghost:hover { background: #fff; color: var(--text); }

/* ── grids ── */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }

/* ── table ── */
.table-wrap { overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--text4); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { text-align: left; padding: 11px 14px; color: var(--text3);
  font-size: 10px; text-transform: uppercase; letter-spacing: .05em;
  border-bottom: 1px solid var(--text4); font-weight: 700; background: rgba(0,0,0,.015); }
tbody td { padding: 10px 14px; border-bottom: 1px solid var(--text4); vertical-align: middle; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:nth-child(even) td { background: rgba(0,0,0,.01); }

/* ── delta ── */
.delta { font-size: 13px; font-weight: 700; margin-left: 6px; white-space: nowrap; }
.delta-up { color: var(--green); }
.delta-down { color: var(--red); }
.delta-neutral { color: var(--text3); }

/* ── tooltip ── */
[data-tip] { cursor: help; }

/* ── animations ── */
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); } }
.anim { animation: fadeIn .45s ease both; }
.anim-d1 { animation-delay: .06s; } .anim-d2 { animation-delay: .12s; }
.anim-d3 { animation-delay: .18s; } .anim-d4 { animation-delay: .24s; }

/* ── empty state ── */
.empty-state { text-align: center; padding: 80px 24px; color: var(--text3); }
.empty-state .icon { font-size: 52px; margin-bottom: 16px; opacity: .4; }
.empty-state h3 { font-size: 17px; margin-bottom: 6px; color: var(--text2); font-weight: 700; }
.empty-state p { font-size: 13px; max-width: 420px; margin: 0 auto; }

/* ── run identity card ── */
.identity-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 24px; }
.identity-chip {
  display: inline-flex; align-items: center; gap: 7px;
  background: #fff; border: 1px solid var(--text4); border-radius: 20px;
  padding: 8px 16px; font-size: 13px; font-weight: 600; color: var(--text);
  box-shadow: var(--shadow-sm);
}
.identity-chip .chip-icon { font-size: 16px; }
.identity-chip .chip-label { font-size: 10px; color: var(--text3); font-weight: 500; }

/* ── responsive ── */
@media (max-width: 768px) {
  body { padding: 18px 12px; }
  .grid-2 { grid-template-columns: 1fr; }
  .compare-hero { grid-template-columns: 1fr; gap: 10px; }
  .compare-vs { margin: 0 auto; }
  .stat-row { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
  .metric-grid { grid-template-columns: 1fr; }
  .identity-row { flex-direction: column; }
}

/* ── scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text4); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text3); }
"""

_JS_INTERACT = """
<script>
document.addEventListener('DOMContentLoaded', function(){
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.querySelectorAll('.progress-fill').forEach(el => {
          const w = el.style.width;
          el.style.width = '0%';
          requestAnimationFrame(() => { el.style.width = w; });
        });
        e.target.querySelectorAll('.delta-bar-fill').forEach(el => {
          const w = el.style.width;
          el.style.width = '0%';
          requestAnimationFrame(() => { el.style.width = w; });
        });
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });
  document.querySelectorAll('.card, .metric-card, .stat').forEach(c => observer.observe(c));

  // tooltips
  document.querySelectorAll('[data-tip]').forEach(el => {
    let tip = null;
    el.addEventListener('mouseenter', function() {
      tip = document.createElement('div');
      tip.textContent = this.dataset.tip;
      tip.style.cssText = 'position:fixed;background:#fff;color:var(--text);'
        + 'padding:10px 16px;border-radius:8px;font-size:12px;z-index:9999;'
        + 'border:1px solid var(--text4);pointer-events:none;max-width:300px;'
        + 'line-height:1.5;box-shadow:var(--shadow-lg);';
      document.body.appendChild(tip);
    });
    el.addEventListener('mousemove', function(e) {
      if (tip) { tip.style.left = (e.clientX+16)+'px'; tip.style.top = (e.clientY-48)+'px'; }
    });
    el.addEventListener('mouseleave', function() {
      if (tip) { tip.remove(); tip = null; }
    });
  });
});
</script>
"""

# ── 指标中文名 ──

_METRIC_ZH = {
    "pass_rate": ("📊 通过率", "Pass Rate", "所有执行的通过比例。越高越好，但容易有虚假安全感。"),
    "pass_pow_k": ("🎯 可靠性", "Pass^k", "同一用例 k 次执行全过的比例。衡量的是「每次都对」的能力，比 pass rate 更严格。"),
    "avg_quality": ("⭐ 质量评分", "Quality", "LLM 判官对回答质量的 1-5 分主观评价。4+ 较好，仅供参考。"),
    "avg_tokens": ("🔤 Token 用量", "Tokens", "平均每次执行消耗的 Token 数量（输入+输出）。"),
    "avg_latency_ms": ("⏱️ 平均延迟", "Latency", "平均每次执行的端到端耗时（毫秒）。越低越快。"),
}

_METRIC_BETTER = {
    "pass_rate": True, "pass_pow_k": True, "avg_quality": True,
    "avg_tokens": False, "avg_latency_ms": False,
}

# ── 卡片颜色轮换 ──
_CARD_COLORS = ["c-rose", "c-sage", "c-sky", "c-lav", "c-cha", "c-stone"]

# ── Tag → 中文名映射 ──
_TAG_ZH = {
    "math": "🧮 数学计算",
    "multi_step": "🔄 多步推理",
    "tool": "🔧 工具调用",
    "weather": "🌤️ 天气查询",
    "ambiguous": "❓ 歧义理解",
    "behavior": "🎭 行为规范",
    "efficiency": "⚡ 效率优化",
    "flaky": "🌊 稳定性",
    "injection": "💉 注入安全",
    "kb": "📚 知识库",
    "rag": "🔍 检索增强",
    "security": "🔒 安全防护",
    "search": "🔎 信息检索",
    "code": "💻 代码生成",
    "qa": "💬 问答",
    "summarization": "📝 摘要",
    "translation": "🌐 翻译",
}

_MODEL_ZH = {
    "mock-v1": "📦 Mock (演示)",
    "qwen2.5:3b": "🤖 Qwen 2.5 3B",
    "qwen2.5:7b": "🤖 Qwen 2.5 7B",
    "qwen2.5:14b": "🤖 Qwen 2.5 14B",
    "gpt-4o-mini": "🧠 GPT-4o Mini",
    "gpt-4o": "🧠 GPT-4o",
    "claude-sonnet-5": "🧠 Claude Sonnet 5",
}


def _tag_label(tag: str) -> str:
    """返回 tag 的中文显示名。"""
    return _TAG_ZH.get(tag, f"🏷️ {tag}")


# ── 运行命名 ──

def _run_label(run: dict) -> str:
    """基于 run 内容生成人类可读的名称。

    返回 (display_name, subtitle_parts)
    例如: ("Qwen-3B · 数学工具", ["qwen2.5:3b", "11 用例 × 1 重复"])
    """
    agent = run.get("agent", "?")
    model = run.get("model", "")
    tags = sorted(run.get("by_tag", {}).keys()) if isinstance(run.get("by_tag"), dict) else []
    cases = run.get("cases", 0)
    repeat = run.get("repeat", 1)

    # Agent 简称
    agent_short = agent
    for old, new in [("demo-tool-agent", "🛠️ Demo Agent"), ("qwen-agent-v2", "🤖 Qwen V2"),
                     ("qwen-agent", "🤖 Qwen"), ("mock", "📦 Mock")]:
        agent_short = agent_short.replace(old.replace("🛠️ ", "").replace("🤖 ", "").replace("📦 ", ""), new)
        if new in agent_short:
            break
    if "qwen" in agent.lower():
        if "v2" in agent.lower():
            agent_short = "🤖 Qwen V2"
        else:
            agent_short = "🤖 Qwen"

    # 任务类型
    task_desc = " · ".join(_tag_label(t) for t in tags[:3]) if tags else "📋 通用任务"

    # 模型
    model_short = _MODEL_ZH.get(model, model) if model else ""

    name = f"{agent_short} · {task_desc}"
    sub = [f"{cases} 用例 × {repeat} 次", model_short] if model_short else [f"{cases} 用例 × {repeat} 次"]

    return name, sub


def _dataset_label(dataset_path: str) -> str:
    """数据集路径 -> 可读名称。"""
    name = Path(dataset_path).stem
    if name == "dataset":
        return "📦 标准工具调用数据集"
    return f"📦 {name}"


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · AgentProbe</title><style>{_COLOR}</style></head>
<body>
{body}
{_JS_INTERACT}
</body></html>"""


# ═══════════ 首页 ═══════════

def render_index(runs_dir: str, runs: list[dict]) -> str:
    if not runs:
        return _page("体检历史", f"""
<div class="nav"><span class="nav-brand"><span class="brand-dot"></span>AgentProbe</span><span class="nav-spacer"></span>
<a href="/dashboard/compare" class="nav-link">📊 对比</a></div>
<div class="empty-state"><div class="icon">🔬</div>
<h3>暂无体检报告</h3><p>运行 <code style="background:rgba(0,0,0,.04);padding:2px 8px;border-radius:4px">agentprobe run</code> 开始第一次 Agent 体检</p></div>""")

    items = ""
    for i, r in enumerate(runs):
        pr = r.get("pass_rate", 0)
        pk = r.get("pass_pow_k", 0)
        q = r.get("avg_quality", 0)
        cases = r.get("cases", 0)
        repeat = r.get("repeat", 1)
        label, sub_parts = _run_label(r)
        color = _CARD_COLORS[i % len(_CARD_COLORS)]

        pr_cls = "green" if pr >= .85 else ("amber" if pr >= .6 else "red")
        pk_cls = "green" if pk >= .85 else ("amber" if pk >= .6 else "red")

        tags_html = ""
        for t, v in sorted(r.get("by_tag", {}).items()):
            tc = "green" if v >= .8 else ("red" if v < .5 else "amber")
            tags_html += f'<span class="tag tag-{tc}">{_tag_label(t)} {v:.0%}</span>'

        sub_info = " · ".join(sub_parts)

        items += f"""
<div class="card {color} anim anim-d{i%4+1}">
  <div class="card-header">
    <div style="flex:1;min-width:0">
      <a href="/dashboard/{r['run_id']}" style="color:var(--text);text-decoration:none">
        <span class="card-title">{label}</span>
      </a>
      <div class="card-subtitle">{sub_info}</div>
      <div style="font-size:10px;color:var(--text3);margin-top:1px;font-family:monospace">{r['run_id'][:12]}</div>
    </div>
    <div style="display:flex;gap:16px;text-align:center;flex-shrink:0">
      <div><div style="font-size:22px;font-weight:800;color:var(--{pr_cls});letter-spacing:-.02em">{pr:.0%}</div>
        <div style="font-size:9px;color:var(--text3);letter-spacing:.03em;font-weight:600">通过率</div></div>
      <div><div style="font-size:22px;font-weight:800;color:var(--{pk_cls});letter-spacing:-.02em">{pk:.0%}</div>
        <div style="font-size:9px;color:var(--text3);letter-spacing:.03em;font-weight:600">可靠</div></div>
      <div><div style="font-size:22px;font-weight:800;color:var(--c-lav-accent);letter-spacing:-.02em">{q:.1f}</div>
        <div style="font-size:9px;color:var(--text3);letter-spacing:.03em;font-weight:600">质量</div></div>
    </div>
  </div>
  <div class="progress" style="height:5px"><div class="progress-fill {pr_cls}" style="width:{pr*100}%"></div></div>
  <div style="margin-top:6px">{tags_html}</div>
</div>"""

    best = runs[0]
    best_label, _ = _run_label(best)

    body = f"""
<div class="nav">
  <span class="nav-brand"><span class="brand-dot"></span>AgentProbe</span><span class="nav-spacer"></span>
  <span class="nav-badge">📁 {runs_dir}</span>
  <a href="/dashboard/compare" class="nav-link">📊 对比两次运行</a>
</div>

<div class="hero">
  <h1>🔬 Agent 体检历史</h1>
  <p>每次运行 <code style="background:rgba(0,0,0,.04);padding:2px 8px;border-radius:4px;font-size:12px">agentprobe run</code> 生成一份报告。点击任一卡片查看 Trace 时间线与评分明细。</p>
</div>

<div class="stat-row">
  <div class="stat s-rose anim" data-tip="所有历史报告的总数。每次运行 agentprobe run 生成一份。">
    <span class="stat-icon">📋</span>
    <div class="stat-value">{len(runs)}</div>
    <div class="stat-label">历史报告</div>
    <div class="stat-sub">累计体检</div>
  </div>
  <div class="stat s-sage anim anim-d1" data-tip="最新一次运行的通过率。≥85% 较好，<60% 需关注。">
    <span class="stat-icon">✅</span>
    <div class="stat-value">{best.get('pass_rate',0):.0%}</div>
    <div class="stat-label">最新通过率</div>
    <div class="stat-sub">{best_label[:24]}…</div>
  </div>
  <div class="stat s-sky anim anim-d2" data-tip="可靠性指标：同一用例 k 次执行全过才算通过。比 pass rate 更严格。">
    <span class="stat-icon">🎯</span>
    <div class="stat-value">{best.get('pass_pow_k',0):.0%}</div>
    <div class="stat-label">最新可靠性</div>
    <div class="stat-sub">Pass^k · 全过比例</div>
  </div>
  <div class="stat s-lav anim anim-d3" data-tip="LLM 判官对回答质量的 1-5 分评分均值。4+ 较好。">
    <span class="stat-icon">⭐</span>
    <div class="stat-value">{best.get('avg_quality',0):.1f}</div>
    <div class="stat-label">最新质量评分</div>
    <div class="stat-sub">判官均分 / 5</div>
  </div>
</div>

<div style="font-size:14px;font-weight:700;color:var(--text2);margin-bottom:14px;display:flex;align-items:center;gap:8px">
  <span>📋 所有报告</span><span style="font-weight:400;color:var(--text3);font-size:12px">共 {len(runs)} 份 · 按时间倒序</span>
</div>
{items}
"""
    return _page("体检历史", body)


# ═══════════ 详情页 ═══════════

def _render_trace(spans: list[dict]) -> str:
    sorted_spans = sorted(spans, key=lambda s: s.get("start", 0))
    rows = ""
    for sp in sorted_spans:
        kind = sp.get("kind", "agent")
        name = sp.get("name", "?")
        err = sp.get("error")
        inp = str(sp.get("input", "") or "")[:80]
        out = str(sp.get("output", "") or "")[:80]
        start = sp.get("start", 0)
        end = sp.get("end", 0) or start
        dur_ms = (end - start) * 1000
        pt = sp.get("prompt_tokens", 0)
        ct = sp.get("completion_tokens", 0)

        dot_cls = f"dot-{kind}" if kind in ("llm", "tool", "agent", "judge") else "dot-agent"
        kind_icon = {"llm": "🧠", "tool": "🔧", "agent": "🤖", "judge": "⚖️"}.get(kind, "•")
        kind_label = kind.upper()

        err_html = f'<div class="trace-error">❌ {err}</div>' if err else ""
        io_html = ""
        if inp:
            io_html += f'<div class="trace-io">📥 {inp}</div>'
        if out:
            io_html += f'<div class="trace-io">📤 {out}</div>'

        rows += f"""
<div class="trace-row">
  <div class="trace-dot {dot_cls}">{kind_icon}</div>
  <div class="trace-body">
    <div class="trace-name">{kind_label} · {name}
      <span style="font-weight:400;color:var(--text3);font-size:10px;margin-left:6px">
        ⏱ {dur_ms:.0f}ms · {pt + ct} tokens</span></div>
    {err_html}{io_html}
  </div>
</div>"""

    return f'<div class="trace-container">{rows}</div>' if rows else '<div style="color:var(--text3);font-size:12px;padding:8px 0">📭 无 trace 记录</div>'


def _render_score_table(scores: list[dict]) -> str:
    if not scores:
        return '<div style="color:var(--text3);font-size:12px;padding:8px 0">📭 无评分记录</div>'
    rows = ""
    for s in scores:
        p = s.get("passed")
        icon = "✅" if p is True else ("❌" if p is False else "⬜")
        cls = "green" if p is True else ("red" if p is False else "text2")
        reason = (s.get('reason', '') or '')[:120]
        rows += f"""<tr>
<td style="font-weight:700;font-size:14px">{icon}</td>
<td style="font-weight:600">{s.get('evaluator', '')}</td>
<td style="font-family:monospace;font-size:12px">{s.get('metric', '')}</td>
<td style="font-family:monospace;font-weight:700">{s.get('value', '')}</td>
<td style="color:var(--text3);font-size:12px;max-width:260px">{reason}</td></tr>"""
    return f"""<div class="table-wrap"><table>
<thead><tr><th style="width:30px"></th><th>评测器</th><th>指标</th><th>值</th><th>原因</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""


def render_detail(report: RunReport) -> str:
    a = aggregate(report)
    results = report.results
    pr = a["pass_rate"]
    pk = a["pass_pow_k"]

    # 构建 run dict 以生成标签
    run_info = {"agent": report.agent, "model": report.model, "by_tag": a.get("by_tag", {}),
                "cases": a["cases"], "repeat": report.repeat}
    label, sub_parts = _run_label(run_info)
    dataset_label = _dataset_label(report.dataset)

    # 分组
    order: list[str] = []
    by: dict[str, list[CaseResult]] = {}
    for r in results:
        if r.case.id not in by:
            by[r.case.id] = []
            order.append(r.case.id)
        by[r.case.id].append(r)

    # 用例卡片
    cases_html = ""
    for ci, cid in enumerate(order):
        g = by[cid]
        ok = sum(1 for r in g if r.passed)
        total = len(g)
        pct = ok / total * 100 if total else 0
        bar_cls = "green" if ok == total else ("red" if ok == 0 else "amber")
        badge_cls = "pass" if ok == total else ("fail" if ok == 0 else "warn")
        badge_text = f"{ok}/{total} 通过" if total > 1 else ("✅ 通过" if ok else "❌ 失败")
        color = _CARD_COLORS[ci % len(_CARD_COLORS)]

        task = g[0].case.task[:100]
        tags_html = " ".join(
            f'<span class="tag tag-blue">{_tag_label(t)}</span>' for t in g[0].case.tags)

        fail = next((r for r in g if not r.passed), g[0])
        trace_html = _render_trace([s.model_dump() for s in fail.trace.spans])
        score_html = _render_score_table([s.model_dump() for s in fail.scores])

        if total > 1:
            repeats_info = " · ".join(
                f"<span style='color:var(--{'green' if r.passed else 'red'})'>{'✓' if r.passed else '✗'} #{ri + 1}</span>"
                for ri, r in enumerate(g))
        else:
            repeats_info = ""

        cases_html += f"""
<div class="card {color} anim">
  <div class="card-header">
    <div style="flex:1;min-width:0">
      <span class="card-title" style="font-family:monospace;font-size:12px">{cid}</span>
      <div style="font-size:12px;color:var(--text2);margin-top:3px;line-height:1.5">{task}</div>
      {f'<div style="font-size:10px;color:var(--text3);margin-top:2px">{repeats_info}</div>' if repeats_info else ''}
    </div>
    <span class="card-badge badge-{badge_cls}">{badge_text}</span>
  </div>
  <div class="progress" style="height:6px"><div class="progress-fill {bar_cls}" style="width:{pct}%"></div></div>
  <div style="margin-top:6px">{tags_html}</div>
  <details>
    <summary>🔍 Trace 时间线 ({len(fail.trace.spans)} 步) + 评分明细</summary>
    <div style="margin-top:4px">
      <div style="font-size:11px;color:var(--text3);margin-bottom:4px">📝 最终输出:</div>
      <div style="font-size:12px;color:var(--text2);background:rgba(0,0,0,.02);padding:8px 12px;border-radius:var(--radius-xs);margin-bottom:4px;max-height:56px;overflow:hidden;border:1px solid var(--text4)">{fail.output[:300] or '(空)'}</div></div>
    {trace_html}
    <div style="margin-top:12px"><span style="font-size:11px;color:var(--text3)">📊 评分明细:</span></div>
    {score_html}
  </details>
</div>"""

    # 标签分布
    tag_bars = ""
    tag_colors = ["var(--c-rose-accent)", "var(--c-sage-accent)", "var(--c-sky-accent)", "var(--c-lav-accent)",
                   "var(--c-cha-accent)", "var(--c-stone-accent)"]
    for ti, (t, v) in enumerate(sorted(a["by_tag"].items())):
        tc = tag_colors[ti % len(tag_colors)]
        bc = "green" if v >= .8 else ("red" if v < .5 else "amber")
        tag_bars += f"""<div style="display:flex;align-items:center;gap:10px;margin:8px 0">
<span class="tag tag-blue" style="min-width:90px;text-align:center">{_tag_label(t)}</span>
<div class="progress" style="flex:1;height:7px"><div class="progress-fill {bc}" style="width:{v * 100}%"></div></div>
<span style="font-size:12px;font-weight:700;min-width:38px;text-align:right;color:var(--{bc})">{v:.0%}</span></div>"""

    pr_cls = "green" if pr >= .85 else ("amber" if pr >= .6 else "red")
    pk_cls = "green" if pk >= .85 else ("amber" if pk >= .6 else "red")
    total_cases = len(order)
    total_pass = sum(1 for cid in order if all(r.passed for r in by[cid]))

    body = f"""
<div class="nav">
  <a href="/dashboard" class="nav-brand"><span class="brand-dot"></span>AgentProbe</a><span class="nav-spacer"></span>
  <span class="nav-badge" style="font-size:11px">{report.run_id[:12]}</span>
</div>

<div class="hero">
  <h1>📋 {label}</h1>
  <div class="hero-meta">
    <div class="hero-meta-item">🤖 <strong>{report.agent}</strong></div>
    <div class="hero-meta-item">🧠 <strong>{report.model}</strong></div>
    <div class="hero-meta-item">📦 {dataset_label}</div>
    <div class="hero-meta-item">📊 <strong>{a['cases']} 用例</strong> × {report.repeat} 次</div>
    <div class="hero-meta-item">🔢 <strong>{a['attempts']} 次</strong>总执行</div>
  </div>
</div>

<div class="stat-row">
  <div class="stat s-rose anim" data-tip="所有执行的通过比例。≥85% 较好，<60% 需要关注。">
    <span class="stat-icon">📊</span>
    <div class="stat-value">{pr:.1%}</div>
    <div class="stat-label">通过率 Pass Rate</div>
    <div class="stat-sub">{a['attempts']} 次执行中的通过比例</div>
  </div>
  <div class="stat s-sage anim anim-d1" data-tip="同一用例 k 次执行全过的比例。衡量的是「每次都对」的能力。">
    <span class="stat-icon">🎯</span>
    <div class="stat-value">{pk:.1%}</div>
    <div class="stat-label">可靠性 Pass^k (k={report.repeat})</div>
    <div class="stat-sub">{total_pass}/{total_cases} 用例全部重复通过</div>
  </div>
  <div class="stat s-lav anim anim-d2" data-tip="LLM 判官对回答质量的 1-5 分主观评价。4+ 较好。">
    <span class="stat-icon">⭐</span>
    <div class="stat-value">{a['avg_quality']}</div>
    <div class="stat-label">质量评分 / 5</div>
    <div class="stat-sub">判官对每次回答的均分</div>
  </div>
  <div class="stat s-sky anim anim-d3" data-tip="平均每次执行的 LLM 调用次数 + 工具调用次数。太高说明反复尝试。">
    <span class="stat-icon">⚡</span>
    <div class="stat-value">{a['avg_llm_calls']}<span style="font-size:18px;color:var(--text3)">/{a['avg_tool_calls']}</span></div>
    <div class="stat-label">LLM / 工具调用</div>
    <div class="stat-sub">{a['avg_tokens']:.0f} tokens · {a['avg_latency_ms']:.0f}ms</div>
  </div>
</div>

<div class="grid-2">
  <div class="card c-lav anim">
    <div class="card-title" style="margin-bottom:14px">🏷️ 按任务类型分布</div>
    {tag_bars or '<div style="color:var(--text3);font-size:12px">📭 无标签数据</div>'}
  </div>
  <div class="card c-sky anim anim-d1">
    <div class="card-title" style="margin-bottom:14px">💡 指标说明</div>
    <div style="font-size:12px;color:var(--text2);line-height:2">
      <p>📊 <strong style="color:var(--green)">通过率</strong> — 所有执行的通过比例。容易有虚假安全感。</p>
      <p>🎯 <strong style="color:var(--c-cha-accent)">可靠性 Pass^k</strong> — 同一用例 k 次全过才算通过，衡量 <em>稳定性</em>。</p>
      <p>⭐ <strong style="color:var(--c-lav-accent)">质量评分</strong> — LLM 判官 1-5 分主观评价，关键决策以规则断言为准。</p>
      <p>🔍 展开每条用例可查看 Trace 时间线与评分明细。</p>
    </div>
  </div>
</div>

<h2 style="font-size:18px;font-weight:800;margin:28px 0 14px;letter-spacing:-.02em">📝 用例明细</h2>
{cases_html}
"""
    return _page(label[:30], body)


# ═══════════ 对比页 ═══════════

def _run_list(runs_dir: str) -> list[dict]:
    out = []
    for p in sorted(Path(runs_dir).glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            rep = load_report(p)
            a = aggregate(rep)
            out.append({"id": rep.run_id, "agent": rep.agent, "model": rep.model, "date": rep.created, **a})
        except Exception:
            continue
    return out


def _fmt_val(v, key: str) -> str:
    if key in ("pass_rate", "pass_pow_k"):
        return f"{v:.1%}"
    if key in ("avg_tokens", "avg_latency_ms"):
        return f"{v:,.0f}"
    return f"{v:.2f}"


def render_compare(runs_dir: str, base_id: str = "", new_id: str = "") -> str:
    summaries = _run_list(runs_dir)

    base_info = None
    new_info = None
    for s in summaries:
        if s["id"] == base_id: base_info = s
        if s["id"] == new_id: new_info = s

    # 为下拉框生成可读标签
    def _opt_label(s: dict) -> str:
        label, _ = _run_label(s)
        return f"{label} · {s.get('pass_rate',0):.0%}"

    opts = "".join(
        f'<option value="{s["id"]}" {"selected" if s["id"] == base_id else ""}>{_opt_label(s)}</option>'
        for s in summaries)

    result_html = ""
    if base_id and new_id:
        try:
            base_r = load_report(_find_report(runs_dir, base_id))
            new_r = load_report(_find_report(runs_dir, new_id))
            cmp = compare_reports(base_r, new_r)
            result_html = _cmp_result(cmp, base_info, new_info)
        except Exception as e:
            result_html = f'<div class="card c-rose"><p style="color:var(--red)">❌ 对比失败: {e}</p></div>'

    body = f"""
<div class="nav">
  <a href="/dashboard" class="nav-brand"><span class="brand-dot"></span>AgentProbe</a><span class="nav-spacer"></span>
  <a href="/dashboard" class="nav-link">← 📋 返回首页</a>
</div>

<div class="hero">
  <h1>📊 回归对比</h1>
  <p>对比两次 Agent 评测运行之间的指标变化 —— 就像代码的 <strong>git diff</strong>。看看新版本比基线是变好了还是变差了。如果通过率下降或出现新失败用例，CI 门禁会自动拦截。</p>
</div>

<div class="card c-sky">
  <div class="card-title" style="margin-bottom:14px">🔍 选择两次运行进行对比</div>
  <div style="font-size:12px;color:var(--text2);margin-bottom:14px;line-height:1.6">
    🟫 <strong>基线 Base</strong> = 改动前的版本（参照物）<br>
    🟦 <strong>新报告 New</strong> = 改动后的版本（被评估的）<br>
    对比结果告诉你：你的改动是让 Agent <span style="color:var(--green)">变好了 ↗</span> 还是 <span style="color:var(--red)">变差了 ↘</span>？
  </div>
  <form method="get" action="/dashboard/compare" class="form-row">
    <div class="form-group"><span class="form-label">🟫 基线 Base（改动前）</span>
      <select name="base" style="min-width:300px"><option value="">-- 选择基线 --</option>{opts}</select></div>
    <div style="color:var(--text3);font-weight:800;padding-top:18px;font-size:15px">VS</div>
    <div class="form-group"><span class="form-label">🟦 新报告 New（改动后）</span>
      <select name="new" style="min-width:300px"><option value="">-- 选择新报告 --</option>{opts}</select></div>
    <button type="submit" class="btn btn-primary">⚡ 开始对比</button>
  </form>
</div>

{result_html}
"""
    return _page("回归对比", body)


def _cmp_result(cmp: dict, base_info: dict | None = None, new_info: dict | None = None) -> str:
    b = cmp["base"]
    n = cmp["new"]
    d = cmp["delta"]

    # 门禁
    ok, _ = gate_check(cmp)
    gate_cls = "pass" if ok else "fail"
    gate_icon = "✅ 门禁通过 — 新版本未出现显著退化" if ok else "🚫 门禁拦截 — 新版本存在回归风险"

    # 通俗总结
    summary_parts = []
    for k in b:
        zh_name, _, _ = _METRIC_ZH.get(k, (k, k, ""))
        delta = d[k]
        better_up = _METRIC_BETTER.get(k, True)
        improved = (delta > 0 and better_up) or (delta < 0 and not better_up)
        worse = (delta < 0 and better_up) or (delta > 0 and not better_up)
        if abs(delta) < 0.001 and isinstance(delta, float):
            continue
        direction = "📈 提升" if improved else ("📉 下降" if worse else "持平")
        summary_parts.append(f"{zh_name} {direction}")

    summary_text = "、".join(summary_parts) if summary_parts else "各项指标基本持平"
    regressed_count = len(cmp.get("regressed_cases", []))
    fixed_count = len(cmp.get("fixed_cases", []))
    extra_notes = []
    if regressed_count: extra_notes.append(f"⚠️ {regressed_count} 个用例回归")
    if fixed_count: extra_notes.append(f"🎉 {fixed_count} 个用例修复")
    extra_text = "；".join(extra_notes)

    # 指标卡片
    metric_colors = ["c-rose", "c-sage", "c-sky", "c-lav", "c-cha"]
    metric_cards = ""
    for mi, k in enumerate(b):
        zh_name, en_name, desc = _METRIC_ZH.get(k, (k, k, ""))
        delta = d[k]
        better_up = _METRIC_BETTER.get(k, True)
        improved = (delta > 0 and better_up) or (delta < 0 and not better_up)
        worse = (delta < 0 and better_up) or (delta > 0 and not better_up)
        base_val = b[k]
        new_val = n[k]

        if improved:
            arrow = '<span style="color:var(--green);font-size:20px">▲</span>'
            delta_cls = "delta-up"; delta_sign = "+"
        elif worse:
            arrow = '<span style="color:var(--red);font-size:20px">▼</span>'
            delta_cls = "delta-down"; delta_sign = ""
        else:
            arrow = '<span style="color:var(--text3);font-size:16px">─</span>'
            delta_cls = "delta-neutral"; delta_sign = ""

        bv = _fmt_val(base_val, k)
        nv = _fmt_val(new_val, k)
        dv = f"{delta_sign}{_fmt_val(abs(delta), k)}" if delta != 0 else "0"

        max_val = max(abs(base_val), abs(new_val), 0.001)
        bar_pct = min(abs(delta) / max_val * 100, 100)
        bar_cls = "better" if improved else ("worse" if worse else "")
        bar_html = ""
        if bar_cls and bar_pct > 0.5:
            bar_html = f'<div class="delta-bar"><div class="delta-bar-fill {bar_cls}" style="width:{bar_pct}%"></div></div>'

        pct_str = ""
        if isinstance(delta, float) and abs(base_val) > 0.0001:
            pct = delta / abs(base_val)
            if abs(pct) >= 0.001:
                pct_str = f'（{pct:+.1%}）'

        mc = metric_colors[mi % len(metric_colors)]

        metric_cards += f"""
<div class="metric-card anim">
  <div class="metric-name">{zh_name} <span style="font-weight:400;color:var(--text3);font-size:10px">({en_name})</span></div>
  <div class="metric-values">
    <div class="metric-base"><div class="val">{bv}</div><div class="lbl">基线</div></div>
    <div class="metric-arrow">{arrow}</div>
    <div class="metric-new"><div class="val">{nv}</div><div class="lbl">新版本</div></div>
  </div>
  {bar_html}
  <div class="delta-text">
    <span class="delta {delta_cls}">Δ {dv}{pct_str}</span>
    <span style="font-size:10px;color:var(--text3);margin-left:4px">{'← 变好' if improved else ('← 变差' if worse else '← 无变化')}</span>
  </div>
  <div class="metric-desc">{desc}</div>
</div>"""

    # 回归/修复用例
    regressed = cmp.get("regressed_cases", [])
    fixed = cmp.get("fixed_cases", [])

    regressed_html = f"""<div class='case-section'>
<h4>⚠️ 回归的用例 <span style="font-weight:400;color:var(--text3);font-size:11px">(之前通过 → 现在失败)</span></h4>
<div class='case-grid'>""" + ("".join(
        f'<span class="tag tag-red" style="font-size:12px;padding:5px 14px">❌ {c}</span>' for c in regressed)
        if regressed else '<span style="color:var(--green);font-size:12px">✅ 无回归用例</span>') + "</div></div>"

    fixed_html = f"""<div class='case-section'>
<h4>🎉 修复的用例 <span style="font-weight:400;color:var(--text3);font-size:11px">(之前失败 → 现在通过)</span></h4>
<div class='case-grid'>""" + ("".join(
        f'<span class="tag tag-green" style="font-size:12px;padding:5px 14px">✅ {c}</span>' for c in fixed)
        if fixed else '<span style="color:var(--text3);font-size:12px">📭 无新修复用例</span>') + "</div></div>"

    # 拦截原因
    failure_reasons = []
    if not ok:
        if d.get("pass_rate", 0) < -0.02:
            failure_reasons.append(f"📊 通过率下降 <strong>{abs(d['pass_rate']):.1%}</strong>，超过 2% 阈值")
        if d.get("pass_pow_k", 0) < -0.02:
            failure_reasons.append(f"🎯 可靠性下降 <strong>{abs(d['pass_pow_k']):.1%}</strong>，超过 2% 阈值")
        if regressed:
            failure_reasons.append(f"⚠️ 出现 <strong>{len(regressed)} 个</strong>新失败用例：{', '.join(regressed)}")

    failure_html = ""
    if failure_reasons:
        failure_html = "<div style='margin-top:12px;padding:14px 18px;background:var(--red-bg);border:1px solid var(--red-border);border-radius:var(--radius-sm);font-size:12px;line-height:1.9'>"
        failure_html += "<strong style='color:var(--red)'>🚫 拦截原因：</strong><br>"
        failure_html += "<br>".join(f"• {r}" for r in failure_reasons)
        failure_html += "</div>"

    base_label, _ = _run_label(base_info) if base_info else (cmp["base_run"][:12], [])
    new_label, _ = _run_label(new_info) if new_info else (cmp["new_run"][:12], [])

    return f"""
<div style="margin-top:24px">
  <div class="compare-hero anim">
    <div class="compare-col c-base">
      <div class="run-label">🟫 基线 Base（改动前）</div>
      <div class="run-id">{base_label}</div>
      <div class="run-agent" style="font-family:monospace;font-size:10px">{cmp['base_run'][:12]}</div>
    </div>
    <div class="compare-vs">VS</div>
    <div class="compare-col c-new">
      <div class="run-label">🟦 新版本 New（改动后）</div>
      <div class="run-id">{new_label}</div>
      <div class="run-agent" style="font-family:monospace;font-size:10px">{cmp['new_run'][:12]}</div>
    </div>
  </div>

  <div class="gate-banner {gate_cls} anim anim-d1">{gate_icon}</div>
  {failure_html}

  <div class="compare-summary anim anim-d2">
    <h3>📝 一句话总结</h3>
    <p>相比基线，新版本 {summary_text}。{extra_text or '整体变化不显著。'}</p>
  </div>

  <h3 style="font-size:15px;font-weight:700;margin:20px 0 12px;display:flex;align-items:center;gap:8px">📈 指标逐项对比</h3>
  <div class="metric-grid">{metric_cards}</div>

  <div class="grid-2" style="margin-top:16px">
    <div class="card c-rose">{regressed_html}</div>
    <div class="card c-sage">{fixed_html}</div>
  </div>
</div>"""


def _find_report(runs_dir: str, run_id: str) -> Path:
    for p in Path(runs_dir).glob("*.json"):
        if p.stem == run_id or p.stem.startswith(run_id):
            return p
    raise FileNotFoundError(f"run {run_id} not found")


def register_dashboard_routes(app, runs_dir: str = "runs"):
    from fastapi.responses import HTMLResponse

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_index():
        runs = []
        for p in sorted(Path(runs_dir).glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                rep = load_report(p)
                runs.append({
                    "run_id": rep.run_id, "agent": rep.agent, "model": rep.model,
                    "file": p.name, **aggregate(rep),
                })
            except Exception:
                continue
        return render_index(runs_dir, runs)

    @app.get("/dashboard/compare", response_class=HTMLResponse)
    def dashboard_compare(base: str = "", new: str = ""):
        return render_compare(runs_dir, base, new)

    @app.get("/dashboard/{run_id}", response_class=HTMLResponse)
    def dashboard_detail(run_id: str):
        path = _find_report(runs_dir, run_id)
        return render_detail(load_report(path))
