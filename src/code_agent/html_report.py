"""Interactive HTML Report Generator Module.

Produces a standalone, zero-external-asset HTML report with responsive styling,
metric cards, and interactive JavaScript search and severity filters.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import List

from .models import Finding

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>代码审计与质量分析报告 - {target_name}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-dim: #94a3b8;
      --red: #ef4444;
      --orange: #f97316;
      --yellow: #eab308;
      --blue: #3b82f6;
      --cyan: #06b6d4;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
    }}
    h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
    .subtitle {{ color: var(--text-dim); font-size: 14px; }}
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }}
    .metric-val {{ font-size: 28px; font-weight: bold; margin-top: 4px; }}
    .controls {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }}
    input[type="text"] {{
      flex: 1;
      min-width: 200px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 6px;
    }}
    .btn {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
    }}
    .btn.active {{
      background: #2563eb;
      border-color: #3b82f6;
    }}
    .findings-list {{ display: flex; flex-direction: column; gap: 12px; }}
    .finding-item {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      transition: border-color 0.2s;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: bold;
    }}
    .badge-CRITICAL {{ background: rgba(239, 68, 68, 0.2); color: var(--red); border: 1px solid var(--red); }}
    .badge-HIGH {{ background: rgba(249, 115, 22, 0.2); color: var(--orange); border: 1px solid var(--orange); }}
    .badge-MEDIUM {{ background: rgba(234, 179, 8, 0.2); color: var(--yellow); border: 1px solid var(--yellow); }}
    .badge-LOW {{ background: rgba(6, 182, 212, 0.2); color: var(--cyan); border: 1px solid var(--cyan); }}
    .badge-INFO {{ background: rgba(59, 130, 246, 0.2); color: var(--blue); border: 1px solid var(--blue); }}
    .finding-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .finding-title {{ font-weight: 600; font-size: 16px; }}
    .loc {{ font-family: monospace; font-size: 13px; color: var(--text-dim); margin-bottom: 8px; }}
    .code-box {{
      background: #090d16;
      border: 1px solid #1e293b;
      padding: 10px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 13px;
      color: #f1f5f9;
      overflow-x: auto;
      margin-bottom: 8px;
    }}
    .rec {{ font-size: 14px; color: #cbd5e1; }}
  </style>
</head>
<body>
<div class="container">
  <header>
    <h1>🛡️ 代码审计与安全质量报告</h1>
    <div class="subtitle">目标路径: {target_name} | 规则扫描发现: {total_count} 项</div>
  </header>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="subtitle">CRITICAL</div>
      <div class="metric-val" style="color: var(--red);">{crit_count}</div>
    </div>
    <div class="metric-card">
      <div class="subtitle">HIGH</div>
      <div class="metric-val" style="color: var(--orange);">{high_count}</div>
    </div>
    <div class="metric-card">
      <div class="subtitle">MEDIUM</div>
      <div class="metric-val" style="color: var(--yellow);">{med_count}</div>
    </div>
    <div class="metric-card">
      <div class="subtitle">LOW / INFO</div>
      <div class="metric-val" style="color: var(--cyan);">{low_count}</div>
    </div>
  </div>

  <div class="controls">
    <input type="text" id="searchInput" placeholder="搜索规则、文件名、标题..." oninput="filterItems()">
    <button class="btn active" onclick="setFilter('ALL', this)">全部 ({total_count})</button>
    <button class="btn" onclick="setFilter('CRITICAL', this)">CRITICAL ({crit_count})</button>
    <button class="btn" onclick="setFilter('HIGH', this)">HIGH ({high_count})</button>
    <button class="btn" onclick="setFilter('MEDIUM', this)">MEDIUM ({med_count})</button>
    <button class="btn" onclick="setFilter('LOW', this)">LOW ({low_count})</button>
  </div>

  <div class="findings-list" id="findingsList">
    {items_html}
  </div>
</div>

<script>
  let currentFilter = 'ALL';
  function setFilter(sev, el) {{
    currentFilter = sev;
    document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    filterItems();
  }}

  function filterItems() {{
    const search = document.getElementById('searchInput').value.toLowerCase();
    const items = document.querySelectorAll('.finding-item');
    items.forEach(it => {{
      const sev = it.getAttribute('data-sev');
      const text = it.innerText.toLowerCase();
      const matchSev = (currentFilter === 'ALL' || sev === currentFilter);
      const matchText = (!search || text.includes(search));
      it.style.display = (matchSev && matchText) ? 'block' : 'none';
    }});
  }}
</script>
</body>
</html>
"""


class HTMLReportGenerator:
    """Generates interactive HTML reports."""

    @classmethod
    def generate(cls, findings: List[Finding], target_name: str = "") -> str:
        crit_count = sum(1 for f in findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in findings if f.severity == "HIGH")
        med_count = sum(1 for f in findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in findings if f.severity in ("LOW", "INFO"))

        items = []
        for f in findings:
            snippet_box = ""
            if f.snippet:
                snippet_box = f'<div class="code-box">{html.escape(f.snippet)}</div>'

            item_html = f"""
            <div class="finding-item" data-sev="{html.escape(f.severity)}">
              <div class="finding-header">
                <span class="badge badge-{html.escape(f.severity)}">{html.escape(f.severity)}</span>
                <span class="finding-title">{html.escape(f.title)} ({html.escape(f.rule_id)})</span>
              </div>
              <div class="loc">📍 {html.escape(f.file_path)} : 第 {f.line_number} 行</div>
              {snippet_box}
              <div class="rec">💡 <strong>建议:</strong> {html.escape(f.recommendation)}</div>
            </div>
            """
            items.append(item_html)

        return HTML_TEMPLATE.format(
            target_name=html.escape(target_name),
            total_count=len(findings),
            crit_count=crit_count,
            high_count=high_count,
            med_count=med_count,
            low_count=low_count,
            items_html="\n".join(items) if items else '<div class="finding-item">✔ 未发现任何代码漏洞或质量违规。</div>',
        )

    @classmethod
    def export(cls, findings: List[Finding], output_path: str | Path, target_name: str = "") -> Path:
        p = Path(output_path)
        content = cls.generate(findings, target_name=target_name)
        p.write_text(content, encoding="utf-8")
        return p
