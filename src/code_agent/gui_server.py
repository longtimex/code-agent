"""Desktop GUI Application Server.

Hosts an interactive local desktop interface with zero external dependencies,
providing a visual control dashboard for code analysis, agent reasoning,
technical debt evaluation, and test generation.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .agent import CodeAnalysisAgent
from .ast_parser import ASTParser
from .call_graph import DependencyGraph
from .config import AgentConfig
from .debt_estimator import DebtEstimator
from .git_tools import GitTools
from .html_report import HTMLReportGenerator
from .llm_client import OfflineHeuristicEngine, OpenAICompatibleClient
from .pr_reviewer import PRReviewer
from .sarif import SARIFExporter
from .security_rules import CodeRuleEngine
from .test_generator import TestGenerator

DESKTOP_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Code Analysis Agent - 桌面控制台</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg: #0f172a;
      --panel: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-dim: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --cyan: #06b6d4;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 0;
      display: flex;
      height: 100vh;
      overflow: hidden;
    }
    #sidebar {
      width: 240px;
      background: #090d16;
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 16px;
    }
    .logo {
      font-size: 18px;
      font-weight: bold;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 24px;
    }
    .nav-btn {
      background: transparent;
      border: none;
      color: var(--text-dim);
      padding: 10px 12px;
      border-radius: 6px;
      text-align: left;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 4px;
      transition: all 0.2s;
    }
    .nav-btn:hover { background: rgba(255,255,255,0.05); color: var(--text); }
    .nav-btn.active { background: var(--primary); color: #fff; }
    #main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 24px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }
    h2 { margin-top: 0; font-size: 20px; }
    label { font-size: 13px; color: var(--text-dim); display: block; margin-bottom: 6px; }
    input[type="text"], select, textarea {
      width: 100%;
      background: #090d16;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 6px;
      font-size: 14px;
      margin-bottom: 16px;
    }
    textarea { height: 100px; resize: vertical; font-family: monospace; }
    .btn {
      background: var(--primary);
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary { background: #475569; }
    .btn-secondary:hover { background: #334155; }
    .badge {
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: bold;
    }
    .badge-CRITICAL { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
    .badge-HIGH { background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }
    .badge-MEDIUM { background: rgba(234, 179, 8, 0.2); color: #eab308; }
    .badge-LOW { background: rgba(6, 182, 212, 0.2); color: var(--cyan); }
    #logOutput {
      background: #000;
      color: #10b981;
      font-family: monospace;
      padding: 14px;
      border-radius: 6px;
      height: 280px;
      overflow-y: auto;
      white-space: pre-wrap;
      font-size: 13px;
    }
    .stat-row { display: flex; gap: 16px; margin-bottom: 16px; }
    .stat-box { flex: 1; background: #090d16; border: 1px solid var(--border); border-radius: 6px; padding: 12px; text-align: center; }
    .stat-num { font-size: 24px; font-weight: bold; margin-top: 4px; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
  </style>
</head>
<body>

  <div id="sidebar">
    <div class="logo">🛡️ Code Agent</div>
    <button class="nav-btn active" onclick="switchTab('scanTab', this)">🔍 静态安全扫描</button>
    <button class="nav-btn" onclick="switchTab('agentTab', this)">🤖 Agent 深度审计</button>
    <button class="nav-btn" onclick="switchTab('debtTab', this)">📊 技术债与重复率</button>
    <button class="nav-btn" onclick="switchTab('testgenTab', this)">🧪 自动化测试生成</button>
    <button class="nav-btn" onclick="switchTab('reviewTab', this)">🔀 Git 变更审查</button>
    <button class="nav-btn" onclick="switchTab('settingsTab', this)">⚙️ 模型接口设置</button>
  </div>

  <div id="main">
    <!-- SCAN TAB -->
    <div id="scanTab" class="tab-content active">
      <div class="card">
        <h2>🔍 静态代码安全与质量扫描</h2>
        <label>目标路径 (项目目录或单文件):</label>
        <input type="text" id="scanPath" value=".">
        <button class="btn" onclick="runScan()">开始全量扫描</button>
      </div>
    </div>

    <!-- AGENT TAB -->
    <div id="agentTab" class="tab-content">
      <div class="card">
        <h2>🤖 Agent 多轮思考审计</h2>
        <label>目标代码文件或目录:</label>
        <input type="text" id="agentPath" value="src">
        <label>分析任务 (Goal):</label>
        <textarea id="agentGoal">全面审计代码中的潜在漏洞、异常处理、边界条件与性能缺陷，给出修复方案。</textarea>
        <button class="btn" onclick="runAgent()">启动 Agent 思考链</button>
      </div>
    </div>

    <!-- DEBT TAB -->
    <div id="debtTab" class="tab-content">
      <div class="card">
        <h2>📊 代码可维护性指数与技术债评估</h2>
        <label>分析目录:</label>
        <input type="text" id="debtPath" value=".">
        <button class="btn" onclick="runDebt()">计算技术债与重复块</button>
      </div>
    </div>

    <!-- TESTGEN TAB -->
    <div id="testgenTab" class="tab-content">
      <div class="card">
        <h2>🧪 自动化单元测试生成</h2>
        <label>目标 Python 源码文件:</label>
        <input type="text" id="testgenPath" value="src/code_agent/patcher.py">
        <label>测试框架:</label>
        <select id="testgenFramework">
          <option value="pytest">pytest</option>
          <option value="unittest">unittest</option>
        </select>
        <button class="btn" onclick="runTestgen()">生成测试用例代码</button>
      </div>
    </div>

    <!-- REVIEW TAB -->
    <div id="reviewTab" class="tab-content">
      <div class="card">
        <h2>🔀 Git 变更与 PR 审查</h2>
        <label>Git 对比引用 (Ref):</label>
        <input type="text" id="reviewRef" value="HEAD">
        <button class="btn" onclick="runReview()">审查变更与影响传播</button>
      </div>
    </div>

    <!-- SETTINGS TAB -->
    <div id="settingsTab" class="tab-content">
      <div class="card">
        <h2>⚙️ 大语言模型 (LLM) 接口与密钥自定义配置</h2>
        <p style="color: var(--text-dim); font-size: 13px; line-height: 1.6;">
          支持接入任何兼容 OpenAI 协议的远程大模型或本地模型（如 DeepSeek、Ollama、通义千问、SiliconFlow 等）。<br>
          配置将直接保存至 <code>.code-agent.json</code>，并在当前桌面运行时中立即生效。
        </p>

        <label style="font-weight: 600; margin-top: 12px;">快捷预设 (点击一键填入地址与模型):</label>
        <div style="display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;">
          <button class="btn btn-secondary" type="button" onclick="applyPreset('deepseek')">DeepSeek (深度求索)</button>
          <button class="btn btn-secondary" type="button" onclick="applyPreset('ollama')">Ollama (本地运行)</button>
          <button class="btn btn-secondary" type="button" onclick="applyPreset('openai')">OpenAI 官方</button>
          <button class="btn btn-secondary" type="button" onclick="applyPreset('siliconflow')">SiliconFlow (硅基流动)</button>
          <button class="btn btn-secondary" type="button" onclick="applyPreset('qwen')">阿里云 DashScope</button>
        </div>

        <label>API Base URL (端点接口地址):</label>
        <input type="text" id="cfgBaseUrl" placeholder="例如: https://api.deepseek.com/v1 或 http://localhost:11434/v1">

        <label>API Key (密钥令牌):</label>
        <div style="display: flex; gap: 8px; margin-bottom: 16px;">
          <input type="password" id="cfgApiKey" placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx" style="margin-bottom: 0;">
          <button class="btn btn-secondary" type="button" onclick="toggleApiKeyVisibility()" style="white-space: nowrap;">显示/隐藏</button>
        </div>

        <label>模型名称 (Model Identifier):</label>
        <input type="text" id="cfgModel" placeholder="例如: deepseek-chat, gpt-4o, qwen2.5-coder:7b">

        <div style="display: flex; gap: 12px; margin-top: 8px;">
          <button class="btn" type="button" onclick="saveSettings()">💾 保存接口配置</button>
          <button class="btn btn-secondary" type="button" onclick="testConnection()">⚡ 测试连接与可用性</button>
        </div>
        <div id="settingsStatus" style="margin-top: 14px; font-size: 13px; font-weight: 500;"></div>
      </div>
    </div>

    <!-- OUTPUT LOGS -->
    <div class="card" style="flex: 1; display: flex; flex-direction: column;">
      <h2>📋 执行结果与分析报告</h2>
      <div id="logOutput">等待执行指令...</div>
    </div>
  </div>

  <script>
    function switchTab(tabId, el) {
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      el.classList.add('active');
    }

    async function postAPI(endpoint, data) {
      const output = document.getElementById('logOutput');
      output.innerText = "⏳ 正在执行中，请稍候...";
      try {
        const resp = await fetch(endpoint, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const result = await resp.json();
        output.innerText = result.output || JSON.stringify(result, null, 2);
      } catch (e) {
        output.innerText = "❌ 执行出错: " + e.message;
      }
    }

    function runScan() {
      const p = document.getElementById('scanPath').value;
      postAPI('/api/scan', {path: p});
    }

    function runAgent() {
      const p = document.getElementById('agentPath').value;
      const g = document.getElementById('agentGoal').value;
      postAPI('/api/agent', {path: p, goal: g});
    }

    function runDebt() {
      const p = document.getElementById('debtPath').value;
      postAPI('/api/debt', {path: p});
    }

    function runTestgen() {
      const p = document.getElementById('testgenPath').value;
      const fw = document.getElementById('testgenFramework').value;
      postAPI('/api/testgen', {path: p, framework: fw});
    }

    function runReview() {
      const r = document.getElementById('reviewRef').value;
      postAPI('/api/review', {ref: r});
    }

    const presets = {
      deepseek: { url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
      ollama: { url: "http://localhost:11434/v1", model: "qwen2.5-coder:7b" },
      openai: { url: "https://api.openai.com/v1", model: "gpt-4o" },
      siliconflow: { url: "https://api.siliconflow.cn/v1", model: "deepseek-ai/DeepSeek-V3" },
      qwen: { url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" }
    };

    function applyPreset(name) {
      const p = presets[name];
      if (p) {
        document.getElementById('cfgBaseUrl').value = p.url;
        document.getElementById('cfgModel').value = p.model;
        const status = document.getElementById('settingsStatus');
        status.innerHTML = `<span style="color: var(--cyan);">已载入 ${name} 预设参数，请输入对应 API Key 并点击保存。</span>`;
      }
    }

    function toggleApiKeyVisibility() {
      const el = document.getElementById('cfgApiKey');
      el.type = el.type === 'password' ? 'text' : 'password';
    }

    async function loadSettings() {
      try {
        const resp = await fetch('/api/config');
        const data = await resp.json();
        if (data.base_url) document.getElementById('cfgBaseUrl').value = data.base_url;
        if (data.model) document.getElementById('cfgModel').value = data.model;
        // The raw key is never sent to the browser; show a masked hint only.
        const keyInput = document.getElementById('cfgApiKey');
        keyInput.value = '';
        keyInput.placeholder = data.has_api_key
          ? `已保存 (${data.api_key_masked})，留空则不修改`
          : 'sk-... (尚未配置)';
      } catch (e) {
        console.error("加载配置失败", e);
      }
    }

    async function saveSettings() {
      const url = document.getElementById('cfgBaseUrl').value.trim();
      const key = document.getElementById('cfgApiKey').value.trim();
      const model = document.getElementById('cfgModel').value.trim();
      const status = document.getElementById('settingsStatus');
      status.innerHTML = `<span style="color: var(--text-dim);">正在保存配置...</span>`;
      const payload = {base_url: url, model: model};
      if (key) payload.api_key = key;
      try {
        const resp = await fetch('/api/config', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (res.success) {
          status.innerHTML = `<span style="color: var(--success);">✔ ${res.message || "配置已成功保存！"}</span>`;
        } else {
          status.innerHTML = `<span style="color: var(--danger);">✖ 保存失败: ${res.error}</span>`;
        }
      } catch (e) {
        status.innerHTML = `<span style="color: var(--danger);">✖ 保存出错: ${e.message}</span>`;
      }
    }

    async function testConnection() {
      const url = document.getElementById('cfgBaseUrl').value.trim();
      const key = document.getElementById('cfgApiKey').value.trim();
      const model = document.getElementById('cfgModel').value.trim();
      const status = document.getElementById('settingsStatus');
      status.innerHTML = `<span style="color: var(--warning);">⏳ 正在向 ${url || "默认端点"} 发起连接握手测试...</span>`;
      try {
        const resp = await fetch('/api/llm/test', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({base_url: url, api_key: key, model: model})
        });
        const res = await resp.json();
        if (res.success) {
          status.innerHTML = `<span style="color: var(--success);">✔ 握手成功！模型 ${res.model} 响应正常: "${res.response}"</span>`;
        } else {
          status.innerHTML = `<span style="color: var(--danger);">✖ 连接失败: ${res.error}</span>`;
        }
      } catch (e) {
        status.innerHTML = `<span style="color: var(--danger);">✖ 请求出错: ${e.message}</span>`;
      }
    }

    window.addEventListener('DOMContentLoaded', loadSettings);
  </script>
</body>
</html>
"""


class GUIRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from the desktop UI."""

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress default noisy console logs

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = DESKTOP_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/config":
            cfg = AgentConfig.load()
            key = cfg.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
            url = cfg.openai_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            model = cfg.default_model or "gpt-4o"
            # Never echo the raw credential back to the client: any local page
            # that can reach this port would otherwise be able to read it.
            if len(key) > 8:
                masked = f"{key[:4]}****{key[-4:]}"
            else:
                masked = "****" if key else ""
            self._send_json({
                "base_url": url,
                "api_key_masked": masked,
                "has_api_key": bool(key),
                "model": model,
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        try:
            payload = self._handle_post()
        except Exception as exc:  # keep the UI alive instead of dropping the socket
            self._send_json(
                {"success": False, "output": "", "error": f"服务器内部错误: {exc}"},
                status=500,
            )
            return
        self._send_json(payload)

    def _handle_post(self) -> Dict[str, Any]:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body) if body else {}

        handler = {
            "/api/scan": self._api_scan,
            "/api/config": self._api_save_config,
            "/api/llm/test": self._api_llm_test,
            "/api/agent": self._api_agent,
            "/api/debt": self._api_debt,
            "/api/testgen": self._api_testgen,
            "/api/review": self._api_review,
        }.get(parsed.path)

        if handler is None:
            return {"success": False, "output": "", "error": f"未知接口: {parsed.path}"}
        return handler(data)

    def _api_scan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        target = Path(data.get("path", "."))
        findings = CodeRuleEngine.scan_directory(target) if target.is_dir() else CodeRuleEngine.scan_file(target)
        crit = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        med = sum(1 for f in findings if f.severity == "MEDIUM")
        low = sum(1 for f in findings if f.severity in ("LOW", "INFO"))

        lines = [
            "=== 静态代码安全与质量扫描结果 ===",
            f"扫描目标: {target}",
            f"发现总数: {len(findings)} 处 (CRITICAL: {crit}, HIGH: {high}, MEDIUM: {med}, LOW: {low})\n",
        ]
        for i, f in enumerate(findings, start=1):
            lines.append(f"#{i} [{f.severity}] {f.title} ({f.rule_id})")
            lines.append(f"   位置: {f.file_path}:{f.line_number}")
            if f.snippet:
                lines.append(f"   代码: {f.snippet}")
            lines.append(f"   建议: {f.recommendation}\n")
        return {"output": "\n".join(lines)}

    def _api_save_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cfg = AgentConfig.load()
        if "base_url" in data:
            cfg.openai_base_url = data["base_url"]
            os.environ["OPENAI_BASE_URL"] = data["base_url"]
        # An empty field means "keep the stored key" — the UI never receives
        # the real value, so blank must not wipe it.
        if data.get("api_key"):
            cfg.openai_api_key = data["api_key"]
            os.environ["OPENAI_API_KEY"] = data["api_key"]
        if data.get("model"):
            cfg.default_model = data["model"]
        cfg.save()
        return {"success": True, "message": "配置已成功保存至 .code-agent.json，并立即生效！"}

    def _api_llm_test(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cfg = AgentConfig.load()
        base_url = (
            data.get("base_url") or cfg.openai_base_url
            or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        )
        api_key = data.get("api_key") or cfg.openai_api_key or os.environ.get("OPENAI_API_KEY") or ""
        model = data.get("model") or cfg.default_model or "gpt-4o"

        is_local = "localhost" in base_url or "127.0.0.1" in base_url
        if not api_key and not is_local:
            return {"success": False, "error": "未提供 API Key (本地服务如 Ollama 除外)"}

        client = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model, timeout=10)
        return client.ping()

    def _api_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        target = data.get("path", ".")
        goal = data.get("goal", "审计代码中的安全漏洞")
        cfg = AgentConfig.load()
        base_url = data.get("base_url") or cfg.openai_base_url or os.environ.get("OPENAI_BASE_URL")
        api_key = data.get("api_key") or cfg.openai_api_key or os.environ.get("OPENAI_API_KEY")
        model = data.get("model") or cfg.default_model or "gpt-4o"

        if api_key:
            llm = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)
        else:
            llm = OfflineHeuristicEngine(model=model)

        result = CodeAnalysisAgent(llm_client=llm).run(goal=goal, target_path=target)
        return {"output": result.final_response}

    def _api_debt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        target = Path(data.get("path", "."))
        report = DebtEstimator.analyze(target)
        lines = [
            "=== 代码可维护性指数与技术债评估 ===",
            f"可维护性评级 (MI): Grade {report.maintainability_grade} ({report.maintainability_index:.1f} / 100)",
            f"总代码行数 (LOC): {report.total_loc:,} 行 ({report.total_files} 个文件)",
            f"预估技术债偿还工时: {report.total_debt_hours:.1f} 小时 (共 {report.total_findings} 处发现)",
            f"跨文件重复代码块: {report.duplicates_count} 处\n",
        ]
        if report.duplicates:
            lines.append("--- 重复代码热点 ---")
            for i, d in enumerate(report.duplicates[:5], start=1):
                lines.append(f"#{i} 连续 {d.line_count} 行重复 (出现在 {len(d.instances)} 个位置):")
                for f, s, e in d.instances[:2]:
                    lines.append(f"   - {f}:{s}-{e}")
        return {"output": "\n".join(lines)}

    def _api_testgen(self, data: Dict[str, Any]) -> Dict[str, Any]:
        target = Path(data.get("path", ""))
        code = TestGenerator.generate_test_file(target, output_framework=data.get("framework", "pytest"))
        return {"output": code}

    def _api_review(self, data: Dict[str, Any]) -> Dict[str, Any]:
        comment = PRReviewer.generate_review_comment(ref=data.get("ref", "HEAD"))
        return {"output": comment}


def start_server(port: int = 8765) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), GUIRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
