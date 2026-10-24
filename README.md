# Code Analysis Agent (`code-agent`)

基于 Python 的全功能智能代码分析与安全审计 Agent。结合 **AST 结构化骨架解析**、**多语言漏洞规则引擎**、**跨文件符号与依赖拓扑**、**增量哈希缓存**、**技术债与重复代码评估**、**桌面图形弹窗客户端 (GUI)**、**Windows 单文件 .exe 一键打包**、**Model Context Protocol (MCP) 服务** 与 **大模型多轮思考调度 (ReAct / Tool-Calling)**。

---

## 核心特性

- **桌面图形弹窗客户端 (`gui_app` / `gui_server` / `gui_tk`)**：
  - 提供美观、现代的深色主题桌面弹窗软件，可视化选择目录，一键执行扫描、深度 Agent 思考链、技术债计算与测试生成。
  - 双模渲染支持：基于本地无依赖 Webview/App 模式桌面弹窗，或基于原生 Win32 Tkinter 窗口。
- **Windows .exe 一键打包支持 (`build_exe.py`)**：
  - 零外部硬依赖优势：打包后的 `code-agent-gui.exe` 或 `code-agent.exe` 体积精简（约 15MB~20MB），目标电脑**无需安装任何 Python** 即可双击运行。
  - 配套 GitHub Actions 自动化流水线 (`.github/workflows/build-exe.yml`)，推送代码即可自动在云端 Windows 虚拟机编译并产出 `.exe`。
- **Model Context Protocol (MCP) 服务端 (`mcp_server`)**：原生实现 JSON-RPC 2.0 MCP 协议，支持接入 Cursor、Claude Desktop、VS Code (Cline/Roo Code) 与 Windsurf，供各类外部 AI 客户端远程调用代码分析工具。
- **技术债与可维护性评估 (`debt_estimator`)**：计算代码库 Maintainability Index (MI 评级 A/B/C/D)、预估各问题修复时长（Debt Hours），并检测跨文件连续重复代码块（Clone Detection）。
- **多语言代码分析与漏洞审计 (`multi_lang`)**：支持 Python、JavaScript/TypeScript、Go 与 Shell 脚本的结构解析与高危反模式检测。
- **团队自定义规则引擎 (`custom_rules`)**：支持从 `.code-agent.json` 或自定义 JSON 文件动态加载组织专有的正则与安全约束。
- **智能 PR 审查评论生成器 (`pr_reviewer`)**：结合 Git Diff 过滤与 `call_graph` 级联影响半径（Blast Radius），生成 GitHub Flavored Markdown 评审意见。
- **跨文件依赖拓扑与影响半径 (`call_graph`)**：自动解析项目模块拓扑，反向追踪函数调用点（`find_callers`），并计算变更的影响扩散范围（`get_blast_radius`）。
- **OASIS SARIF v2.1.0 导出器 (`sarif`)**：原生对接 GitHub Code Scanning (Security Tab)、GitLab SAST、SonarQube 与 VS Code。
- **AST 驱动自动化单测生成 (`test_generator`)**：基于函数签名、参数类型与异常推断，自动生成覆盖边界用例的 `pytest` / `unittest` 测试骨架。
- **Git Pre-commit 拦截钩子 (`hook`)**：一键安装 `.git/hooks/pre-commit`，在提交前拦截包含 CRITICAL 或 HIGH 级别隐患的代码。
- **交互式终端控制台 / REPL (`repl`)**：提供实时交互终端 (`code-agent chat`)，支持自然语言多轮对话及斜杠指令 (`/scan`、`/outline`、`/diff`、`/callers`、`/blast`)。
- **自包含交互式 HTML 报告 (`html_report`)**：生成带统计卡片、严重度筛选与实时搜索的自包含单页 HTML 报告。
- **静态性能瓶颈与算法热点诊断 (`perf_advisor`)**：静态检测循环内高频正则表达式重复编译、低效字符串连续拼接 (`+=`)、循环内反复文件 I/O 以及 Pandas `iterrows` 等典型性能瓶颈。
- **自动化项目架构与 API 文档生成 (`doc_generator`)**：基于 AST 结构树与跨文件依赖图，一键提取类定义、方法签名、文档字符串及模块拓扑，自动合成 `ARCHITECTURE.md` 与 `API.md`。
- **开源许可证与 SPDX 合规性审计 (`license_checker`)**：自动识别 `LICENSE`、`pyproject.toml` 及源文件内 SPDX 协议声明，智能排查 GPL/AGPL 等强传染性开源协议引入的商业分发风险。
- **确定性漏洞批量自动修复引擎 (`batch_fixer`)**：针对 `yaml.load`、`verify=False`、`tempfile.mktemp` 等已知确定性高危反模式提供安全一键自动批量重构，并附带 AST 语法树回滚保护。
- **自动化补丁与语法安全修复 (`patcher`)**：支持生成差异补丁，内置语法树校验保护与备份机制。

---

## 桌面弹窗软件与 .exe 打包指南

### 1. 本地启动桌面弹窗应用
```bash
# 启动本地桌面图形窗口控制台
PYTHONPATH=src python3 -m code_agent gui
```

### 2. 打包为 Windows 单文件 .exe 应用程序
在 Windows 开发环境中执行：
```bash
# 1. 安装 PyInstaller 打包工具
pip install pyinstaller

# 2. 一键打包桌面图形应用 (生成 dist/code-agent-gui.exe，双击无黑框弹窗)
python build_exe.py --mode gui

# 3. 或一键打包命令行应用 (生成 dist/code-agent.exe)
python build_exe.py --mode cli
```

### 3. 云端自动打包 (.exe 下载)
项目已内置 `.github/workflows/build-exe.yml`，在 GitHub 仓库中触发该工作流，GitHub Actions 会在 Windows 虚拟机中自动编译并提供 `code-agent-windows-binaries` 压缩包供一键下载。

---

## 自定义大语言模型 (LLM) Base URL 与 API Key

本项目**全面支持在软件界面与各类调用模式中自定义 Base URL 与 API Key**，优先级遵循：
`命令行参数 / 界面输入 > 环境变量 (OPENAI_BASE_URL / OPENAI_API_KEY) > 配置文件 (.code-agent.json) > 默认端点`。

### 1. 在桌面图形弹窗客户端中自定义 (GUI)
启动桌面应用后：
- 点击侧边栏 **「⚙️ 模型接口设置」** 页面；
- 提供了主流模型服务商的一键预设快捷按钮：
  - **DeepSeek (深度求索)**：`https://api.deepseek.com/v1` (`deepseek-chat`)
  - **Ollama (完全离线本地运行)**：`http://localhost:11434/v1` (`qwen2.5-coder:7b`)
  - **OpenAI 官方**：`https://api.openai.com/v1` (`gpt-4o`)
  - **SiliconFlow (硅基流动)**：`https://api.siliconflow.cn/v1`
  - **阿里云 DashScope**：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 填入对应端点与 API Key，点击 **「⚡ 测试连接与可用性」** 即可实时校验网络握手与模型返回；
- 点击 **「💾 保存接口配置」**，将直接同步至本地 `.code-agent.json` 并立即生效。

### 2. 通过 CLI 命令行临时指定
在执行 `analyze`（Agent 深度思考）或 `chat`（交互式控制台）时通过参数传入：
```bash
# 接入 DeepSeek
PYTHONPATH=src python3 -m code_agent analyze src/ \
  --base-url https://api.deepseek.com/v1 \
  --api-key sk-xxxxxxxxxxxxxxxxxxxxxxxx \
  --model deepseek-chat

# 接入本地 Ollama
PYTHONPATH=src python3 -m code_agent chat \
  --base-url http://localhost:11434/v1 \
  --api-key ollama \
  --model qwen2.5-coder:7b
```

### 3. 一键初始化或更新配置文件 (.code-agent.json)
```bash
PYTHONPATH=src python3 -m code_agent init-config \
  --base-url "https://api.deepseek.com/v1" \
  --api-key "sk-xxxxxxxx" \
  --model "deepseek-chat"
```

> ⚠️ **安全提示**：`.code-agent.json` 会以**明文**保存 API Key，因此该文件已在 `.gitignore` 中排除，**切勿提交到仓库**。
> 需要纳入版本管理的默认配置请使用 `.code-agent.example.json` 模板，密钥优先通过环境变量 `OPENAI_API_KEY` 注入。

### 4. 在交互式终端 REPL 中动态热切换
在终端控制台（`code-agent chat`）内，无需重启即可通过斜杠指令切换：
```text
/config                # 查看当前 Base URL、模型及脱敏 API Key
/set url <base_url>    # 动态切换 Base URL
/set key <api_key>     # 动态设置 API Key 并激活在线模式
/set model <name>      # 动态切换使用的模型名称
```

---

## 常用 CLI 命令

### 1. 启动桌面弹窗客户端
```bash
PYTHONPATH=src python3 -m code_agent gui
```

### 2. 运行 Model Context Protocol (MCP) 服务
在 Cursor 或 Claude Desktop 中配置启动命令即可无缝集成：
```bash
PYTHONPATH=src python3 -m code_agent mcp
```

### 3. 评估代码可维护性指数与技术债
```bash
PYTHONPATH=src python3 -m code_agent debt src/code_agent
```

### 4. 生成 GitHub PR 审查报告 (含 Blast Radius 级联影响)
```bash
PYTHONPATH=src python3 -m code_agent review --pr
```

### 5. 静态代码分析与多格式报告导出
```bash
# 导出交互式 HTML 报告
PYTHONPATH=src python3 -m code_agent scan . --html report.html

# 导出 OASIS SARIF 2.1.0 格式 (供 GitHub Security Tab 或 SonarQube 读取)
PYTHONPATH=src python3 -m code_agent scan . --sarif results.sarif

# 挂载团队自定义规则
PYTHONPATH=src python3 -m code_agent scan . --custom-rules custom_rules.json

# 质量门禁：存在 HIGH 及以上隐患时以退出码 1 结束 (供 CI / pre-commit 使用)
PYTHONPATH=src python3 -m code_agent scan . --fail-on high
```

### 6. 静态性能瓶颈分析与诊断
```bash
# 静态分析循环内正则重复编译、字符串拼接与 I/O 等性能反模式
PYTHONPATH=src python3 -m code_agent perf src/

# 或者在执行常规安全扫描时一并合并性能分析
PYTHONPATH=src python3 -m code_agent scan src/ --perf
```

### 7. 自动生成架构拓扑与 API 文档
```bash
# 在 docs/ 目录下生成 ARCHITECTURE.md 与 API.md
PYTHONPATH=src python3 -m code_agent docgen src/code_agent -o docs/

# 仅在控制台预览 API 接口文档
PYTHONPATH=src python3 -m code_agent docgen src/code_agent/tools.py --api
```

### 8. 开源协议合规性与传染性风险审计
```bash
# 审计当前项目根目录的许可证文件、SPDX 标头与传染性协议风险
PYTHONPATH=src python3 -m code_agent license .

# 输出 JSON 格式合规数据
PYTHONPATH=src python3 -m code_agent license . --json
```

### 9. 确定性漏洞与反模式一键批量自动修复
```bash
# 自动批量修复目录内所有 yaml.load, verify=False, tempfile.mktemp 等漏洞
PYTHONPATH=src python3 -m code_agent fix src/ --auto
```

### 10. 启动终端交互式对话 REPL
```bash
PYTHONPATH=src python3 -m code_agent chat
```

### 11. 基于 AST 自动生成单元测试用例
```bash
PYTHONPATH=src python3 -m code_agent testgen src/code_agent/patcher.py --framework pytest
```

### 12. 安装 / 卸载 Git Pre-commit 安全拦截钩子
```bash
PYTHONPATH=src python3 -m code_agent install-hook
PYTHONPATH=src python3 -m code_agent uninstall-hook
```
钩子会在提交前执行 `review --ref HEAD --fail-on high`，一旦发现 HIGH 及以上隐患即以非零退出码中止提交。

---

## 运行自动化测试

运行全部 48 项单元测试：
```bash
# 在项目根目录执行
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
