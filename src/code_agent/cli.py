"""Command-Line Interface for the Code Analysis Agent."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import AgentStep, CodeAnalysisAgent
from .ast_parser import ASTParser
from .call_graph import DependencyGraph
from .config import AgentConfig
from .git_tools import GitTools
from .llm_client import OfflineHeuristicEngine, OpenAICompatibleClient
from .patcher import Patcher
from .sarif import SARIFExporter
from .test_generator import TestGenerator
from .hook import PreCommitHook
from .repl import InteractiveREPL
from .gui_app import launch_gui
from .gui_server import start_server
from .mcp_server import MCPServer
from .debt_estimator import DebtEstimator
from .pr_reviewer import PRReviewer
from .custom_rules import CustomRuleLoader
from .ci_integration import CIIntegration
from .html_report import HTMLReportGenerator
from .multi_lang import MultiLangScanner
from .report_formatter import BOLD, CYAN, DIM, GREEN, MAGENTA, RED, RESET, YELLOW, ReportFormatter
from .security_rules import CodeRuleEngine
from .batch_fixer import BatchFixer
from .doc_generator import DocGenerator
from .license_checker import LicenseChecker
from .perf_advisor import PerformanceAdvisor


def print_step(step: AgentStep) -> None:
    print(f"\n{BOLD}[Turn {step.turn}]{RESET}")
    if step.thought:
        print(f"{CYAN}Agent 思考:{RESET} {step.thought.strip()}")
    if step.tool_name:
        print(f"{YELLOW}调用工具:{RESET} `{step.tool_name}` | 参数: {step.tool_args}")
    if step.tool_result:
        preview = step.tool_result[:250].replace("\n", " ")
        if len(step.tool_result) > 250:
            preview += "..."
        print(f"{DIM}工具返回预览:{RESET} {preview}")


def cmd_scan(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    config = AgentConfig.load()
    custom_rules = []
    if getattr(args, "custom_rules", None):
        custom_rules = CustomRuleLoader.load_from_file(args.custom_rules)

    use_cache = not getattr(args, "no_cache", False)
    print(f"{BOLD}🔍 正在扫描目标: {target} ...{RESET}")

    if target.is_file():
        findings = CodeRuleEngine.scan_file(target, config=config)
    else:
        findings = CodeRuleEngine.scan_directory(target, config=config, use_cache=use_cache)

    if getattr(args, "perf", False):
        if target.is_file():
            perf_findings = PerformanceAdvisor.scan_file(target)
        else:
            perf_findings = PerformanceAdvisor.scan_directory(target)
        findings.extend(perf_findings)
    if custom_rules:
        # scan with custom rules
        for fpath in (target.rglob("*") if target.is_dir() else [target]):
            if fpath.is_file():
                try:
                    c = fpath.read_text(encoding="utf-8", errors="replace")
                    findings.extend(CustomRuleLoader.scan_content(c, str(fpath), custom_rules))
                except Exception:
                    pass


    print(ReportFormatter.format_terminal_findings(findings))

    # Print summary metrics
    crit = sum(1 for f in findings if f.severity == "CRITICAL")
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    print(f"{BOLD}📊 审计汇总统计:{RESET}")
    print(f"  {RED}● CRITICAL: {crit:<3}{RESET} {MAGENTA}● HIGH: {high:<3}{RESET} {YELLOW}● MEDIUM: {med:<3}{RESET} {CYAN}● LOW: {low:<3}{RESET} (总计: {len(findings)})")

    if getattr(args, "ci_github", False):
        CIIntegration.emit_github_annotations(findings)
        CIIntegration.write_step_summary(findings)
        print(f"{GREEN}✔ 已输出 GitHub Actions 注解与 Step Summary{RESET}")

    if args.json:
        ReportFormatter.export_json(findings, args.json)
        print(f"{GREEN}✔ JSON 报告已保存至: {args.json}{RESET}")

    if args.markdown:
        md = ReportFormatter.format_markdown(findings, target_name=str(target))
        Path(args.markdown).write_text(md, encoding="utf-8")
        print(f"{GREEN}✔ Markdown 报告已保存至: {args.markdown}{RESET}")

    if getattr(args, "html", None):
        HTMLReportGenerator.export(findings, args.html, target_name=str(target))
        print(f"{GREEN}✔ 交互式 HTML 报告已保存至: {args.html}{RESET}")

    if getattr(args, "sarif", None):
        SARIFExporter.export(findings, args.sarif)
        print(f"{GREEN}✔ SARIF v2.1.0 报告已保存至: {args.sarif}{RESET}")


def cmd_outline(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.is_file():
        print(f"Error: Path '{target}' must be a Python file.", file=sys.stderr)
        sys.exit(1)

    content = target.read_text(encoding="utf-8", errors="replace")
    print(f"{BOLD}📄 文件结构大纲 (AST Skeleton): {target}{RESET}\n")
    skeleton = ASTParser.get_skeleton(content)
    print(skeleton)

    symbols = ASTParser.parse_file(target)
    print(f"\n{BOLD}符号统计 ({len(symbols)}):{RESET}")
    for sym in symbols:
        comp_badge = f"{YELLOW}[复杂度: {sym.complexity}]{RESET}" if sym.complexity > 1 else ""
        print(f"- {sym.kind:<14} {BOLD}{sym.name}{RESET} (L{sym.start_line}-L{sym.end_line}) {comp_badge}")


def cmd_graph(args: argparse.Namespace) -> None:
    workspace = GitTools.get_repo_root() or Path.cwd()
    graph = DependencyGraph(root_dir=workspace)

    if args.symbol:
        callers = graph.find_callers(args.symbol)
        print(f"{BOLD}🔎 符号 '{args.symbol}' 的跨文件调用点 ({len(callers)}):{RESET}")
        for c in callers:
            print(f"  - 在 {CYAN}{c.caller_file}:{c.line_number}{RESET} (函数: `{c.caller_function}`)")
        if not callers:
            print(f"  {DIM}未发现任何显式调用。{RESET}")
        return

    if args.blast_radius:
        affected = graph.get_blast_radius(args.blast_radius)
        print(f"{BOLD}💥 文件 '{args.blast_radius}' 的影响传播范围 (Blast Radius, {len(affected)} 个关联文件):{RESET}")
        for f in affected:
            print(f"  - {f}")
        if not affected:
            print(f"  {DIM}没有其他模块直接或间接导入该文件。{RESET}")
        return

    data = graph.to_dict()
    print(f"{BOLD}🕸️ 项目模块依赖拓扑 ({data['total_files']} 个源文件):{RESET}")
    for mod, deps in data["dependencies"].items():
        if deps:
            print(f"{BOLD}{mod}{RESET} 导入了:")
            for d in deps:
                print(f"  └── {CYAN}{d}{RESET}")


def cmd_fix(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "auto", False):
        print(f"{BOLD}🛠️ 正在执行确定性安全漏洞自动批量修复: {target} ...{RESET}")
        backup = not args.no_backup
        if target.is_file():
            results = BatchFixer.fix_file(target, backup=backup)
        else:
            results = BatchFixer.fix_directory(target, backup=backup)

        success_count = sum(1 for r in results if r.success)
        print(f"\n{BOLD}修复完成: 成功修复 {success_count} 处, 失败 {len(results) - success_count} 处{RESET}")
        for r in results:
            status = f"{GREEN}✔ [FIXED]{RESET}" if r.success else f"{RED}✖ [FAILED]{RESET}"
            print(f"  {status} {r.file_path} ({r.rule_id}): `{r.old_snippet}` -> `{r.new_snippet}`")
        return

    if not args.old_code or not args.new_code:
        print(f"Error: Manual fix requires both --old-code and --new-code (or use --auto for automatic remediation).", file=sys.stderr)
        sys.exit(1)

    if not target.is_file():
        print(f"Error: Manual patch target '{target}' must be a file.", file=sys.stderr)
        sys.exit(1)

    res = Patcher.apply_replacement(
        file_path=target,
        old_snippet=args.old_code,
        new_snippet=args.new_code,
        backup=not args.no_backup,
    )
    if res["success"]:
        print(f"{GREEN}✔ 成功应用代码补丁！{RESET}")
        if res.get("diff"):
            print(f"\n{BOLD}变更差异 (Diff):{RESET}\n{res['diff']}")
        if res.get("backup_file"):
            print(f"{DIM}备份文件: {res['backup_file']}{RESET}")
    else:
        print(f"{RED}✖ 补丁应用失败: {res.get('error')}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_docgen(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    gen_api = args.api or (not args.api and not args.arch)
    gen_arch = args.arch or (not args.api and not args.arch)

    out_arg = getattr(args, "output", None)
    out_dir = Path(out_arg) if out_arg else None

    if gen_arch:
        arch_doc = DocGenerator.generate_architecture_doc(target if target.is_dir() else target.parent)
        if out_dir:
            if out_dir.suffix == ".md":
                out_path = out_dir
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / "ARCHITECTURE.md"
            out_path.write_text(arch_doc, encoding="utf-8")
            print(f"{GREEN}✔ 架构设计文档已生成至: {out_path}{RESET}")
        else:
            print(f"{BOLD}=== ARCHITECTURE.md ==={RESET}\n{arch_doc}\n")

    if gen_api:
        api_doc = DocGenerator.generate_api_doc(target)
        if out_dir:
            if out_dir.suffix == ".md" and not gen_arch:
                out_path = out_dir
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / "API.md"
            out_path.write_text(api_doc, encoding="utf-8")
            print(f"{GREEN}✔ API 接口参考文档已生成至: {out_path}{RESET}")
        else:
            print(f"{BOLD}=== API.md ==={RESET}\n{api_doc}\n")


def cmd_license(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"{BOLD}📜 正在审计开源协议与合规性: {target} ...{RESET}")
    report = LicenseChecker.audit(target if target.is_dir() else target.parent)

    if getattr(args, "json", False):
        import json
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    print(f"\n{BOLD}许可证检测报告:{RESET}")
    print(f"  根目录许可证文件: {GREEN if report.has_license_file else RED}{report.license_file_name or '未检测到'}{RESET}")
    print(f"  识别出的开源协议: {', '.join(report.detected_licenses) if report.detected_licenses else '无'}")
    print(f"  SPDX 标头覆盖率: {report.files_with_spdx} / {report.total_files_scanned} 个源文件")

    if report.risk_warnings:
        print(f"\n{BOLD}风险警告与合规提示:{RESET}")
        for w in report.risk_warnings:
            print(f"  {YELLOW}{w}{RESET}")
    else:
        print(f"\n{GREEN}✔ 未检测到强传染性协议或严重合规风险。{RESET}")


def cmd_perf(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"{BOLD}⚡ 正在进行静态代码性能与算法热点分析: {target} ...{RESET}")
    if target.is_file():
        findings = PerformanceAdvisor.scan_file(target)
    else:
        findings = PerformanceAdvisor.scan_directory(target)

    print(ReportFormatter.format_terminal_findings(findings))
    print(f"{BOLD}📊 性能建议汇总: 共发现 {len(findings)} 处潜在性能瓶颈{RESET}")


def cmd_ci_init(args: argparse.Namespace) -> None:
    workspace = GitTools.get_repo_root() or Path.cwd()
    path = CIIntegration.generate_workflow_file(workspace)
    print(f"{GREEN}✔ 已生成 GitHub Actions 工作流配置: {path}{RESET}")


def cmd_chat(args: argparse.Namespace) -> None:
    workspace = GitTools.get_repo_root() or Path.cwd()
    repl = InteractiveREPL(
        workspace_root=workspace,
        model=args.model,
        base_url=getattr(args, "base_url", None),
        api_key=getattr(args, "api_key", None),
    )
    repl.run()


def cmd_testgen(args: argparse.Namespace) -> None:
    target = Path(args.path)
    if not target.is_file():
        print(f"Error: Target '{target}' must be a Python file.", file=sys.stderr)
        sys.exit(1)

    code = TestGenerator.generate_test_file(target, output_framework=args.framework)
    if args.output:
        Path(args.output).write_text(code, encoding="utf-8")
        print(f"{GREEN}✔ 已生成自动化测试代码至: {args.output}{RESET}")
    else:
        print(code)


def cmd_install_hook(args: argparse.Namespace) -> None:
    try:
        hook_path = PreCommitHook.install()
        print(f"{GREEN}✔ 已成功安装 Git Pre-commit Hook 至: {hook_path}{RESET}")
    except Exception as e:
        print(f"{RED}安装失败: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_uninstall_hook(args: argparse.Namespace) -> None:
    if PreCommitHook.uninstall():
        print(f"{GREEN}✔ 已成功移除 Git Pre-commit Hook{RESET}")
    else:
        print(f"{YELLOW}未找到已安装的 Pre-commit Hook{RESET}")


def cmd_mcp(args: argparse.Namespace) -> None:
    workspace = GitTools.get_repo_root() or Path.cwd()
    server = MCPServer(workspace_root=workspace)
    server.run()


def cmd_debt(args: argparse.Namespace) -> None:
    target = Path(args.path) if args.path else (GitTools.get_repo_root() or Path.cwd())
    print(f"{BOLD}📊 计算代码可维护性指数与技术债: {target} ...{RESET}\n")

    report = DebtEstimator.analyze(target)

    grade_colors = {"A": GREEN, "B": CYAN, "C": YELLOW, "D": RED}
    color = grade_colors.get(report.maintainability_grade, RESET)

    print(f"{BOLD}可维护性评级 (Maintainability Index):{RESET} {color}{BOLD}[Grade {report.maintainability_grade}] ({report.maintainability_index:.1f}/100){RESET}")
    print(f"{BOLD}分析代码行数 (LOC):{RESET} {report.total_loc:,} 行 ({report.total_files} 个文件)")
    print(f"{BOLD}预估技术债偿还时间:{RESET} {YELLOW}{report.total_debt_hours:.1f} 小时{RESET} (共 {report.total_findings} 处待优化项)")
    print(f"{BOLD}跨文件重复代码块:{RESET} {report.duplicates_count} 处\n")

    if report.duplicates:
        print(f"{BOLD}⚠️ 重复代码块 Top 热点:{RESET}")
        for i, d in enumerate(report.duplicates[:5], start=1):
            print(f"  #{i} 连续 {d.line_count} 行重复 (出现在 {len(d.instances)} 个位置):")
            for f, s, e in d.instances[:3]:
                print(f"     - {CYAN}{f}:{s}-{e}{RESET}")
            print()


def cmd_gui(args: argparse.Namespace) -> None:
    launch_gui(port=args.port)

def cmd_init_config(args: argparse.Namespace) -> None:
    cfg = AgentConfig.load()
    if getattr(args, "base_url", None):
        cfg.openai_base_url = args.base_url
    if getattr(args, "api_key", None):
        cfg.openai_api_key = args.api_key
    if getattr(args, "model", None):
        cfg.default_model = args.model
    target = cfg.save()
    print(f"{GREEN}✔ 配置文件已保存至: {target}{RESET}")
    if cfg.openai_base_url:
        print(f"  Base URL: {cfg.openai_base_url}")
    if cfg.openai_api_key:
        masked = cfg.openai_api_key[:4] + "****" + cfg.openai_api_key[-4:] if len(cfg.openai_api_key) > 8 else "****"
        print(f"  API Key:  {masked}")
    if cfg.default_model:
        print(f"  Model:    {cfg.default_model}")


def cmd_review(args: argparse.Namespace) -> None:
    repo_root = GitTools.get_repo_root()
    if not repo_root:
        print("Error: Current directory is not a Git repository.", file=sys.stderr)
        sys.exit(1)

    print(f"{BOLD}🔍 检查 Git 变更 (Ref: {args.ref}) ...{RESET}")
    changed_files = GitTools.get_changed_files(repo_path=repo_root, ref=args.ref)
    if not changed_files:
        print(f"{GREEN}✔ 没有检测到待分析的代码变更。{RESET}")
        return

    print(f"发现 {len(changed_files)} 个变更文件:")
    for f in changed_files:
        print(f"  - {f}")

    if getattr(args, "pr", False):
        comment = PRReviewer.generate_review_comment(repo_root=repo_root, ref=args.ref)
        print(comment)
        return

    diff_text = GitTools.get_diff(repo_path=repo_root, ref=args.ref)
    file_diffs = GitTools.parse_unified_diff(diff_text)

    all_findings = []
    config = AgentConfig.load(repo_root)

    for fd in file_diffs:
        target_file = repo_root / fd.new_path
        if target_file.is_file() and target_file.suffix == ".py":
            findings = CodeRuleEngine.scan_file(target_file, config=config)
            changed_lines = set(fd.changed_line_numbers)
            if changed_lines:
                relevant = [f for f in findings if f.line_number in changed_lines]
                all_findings.extend(relevant)
            else:
                all_findings.extend(findings)

    print(ReportFormatter.format_terminal_findings(all_findings))


def cmd_analyze(args: argparse.Namespace) -> None:
    target = Path(args.path)
    workspace = GitTools.get_repo_root() or Path.cwd()

    cfg = AgentConfig.load()
    api_key = getattr(args, "api_key", None) or os.environ.get("OPENAI_API_KEY") or cfg.openai_api_key
    base_url = getattr(args, "base_url", None) or os.environ.get("OPENAI_BASE_URL") or cfg.openai_base_url

    if args.offline or not api_key:
        if not args.offline and not api_key:
            print(f"{YELLOW}提示: 未检测到 API Key，自动启用离线启发式推理引擎。{RESET}")
        llm = OfflineHeuristicEngine(model=args.model)
    else:
        llm = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=args.model)

    print(f"{BOLD}🤖 启动代码分析 Agent ...{RESET}")
    print(f"目标路径: {target}")
    print(f"分析任务: {args.goal}")
    print(f"运行模型: {args.model} ({'离线模式' if isinstance(llm, OfflineHeuristicEngine) else '在线 API'})\n")

    agent = CodeAnalysisAgent(
        workspace_root=workspace,
        llm_client=llm,
        max_turns=args.max_turns,
        on_step=print_step,
    )

    result = agent.run(goal=args.goal, target_path=str(target))

    print(f"\n{BOLD}══════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}                      Agent 最终分析报告                         {RESET}")
    print(f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}\n")
    print(result.final_response)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="code-agent",
        description="基于 Python 的智能代码分析与安全审计 Agent",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="执行静态 AST 与安全规则扫描")
    p_scan.add_argument("path", help="扫描的目标文件或目录路径")
    p_scan.add_argument("--json", help="导出 JSON 结果文件路径")
    p_scan.add_argument("--markdown", help="导出 Markdown 报告路径")
    p_scan.add_argument("--html", help="导出交互式 HTML 报告文件路径")
    p_scan.add_argument("--sarif", help="导出 OASIS SARIF v2.1.0 格式报告")
    p_scan.add_argument("--custom-rules", help="加载团队自定义规则 JSON 文件")
    p_scan.add_argument("--ci-github", action="store_true", help="启用 GitHub Actions 注解输出格式")
    p_scan.add_argument("--no-cache", action="store_true", help="禁用增量缓存，强制全量重扫")
    p_scan.add_argument("--perf", action="store_true", help="同时执行静态性能瓶颈与热点分析")

    # outline
    p_outline = subparsers.add_parser("outline", help="提取 Python 代码的 AST 骨架与函数签名")
    p_outline.add_argument("path", help="目标 Python 文件")

    # graph
    p_graph = subparsers.add_parser("graph", help="分析跨文件依赖图、调用点与影响半径")
    p_graph.add_argument("--symbol", help="查找特定函数的跨文件调用点")
    p_graph.add_argument("--blast-radius", help="计算修改指定文件所影响的全部模块")

    # fix
    p_fix = subparsers.add_parser("fix", help="安全应用代码替换补丁或自动批量修复已知缺陷")
    p_fix.add_argument("path", help="目标文件或目录路径")
    p_fix.add_argument("--auto", action="store_true", help="启用确定性安全漏洞自动识别与批量修复")
    p_fix.add_argument("--old-code", default=None, help="待替换的原始代码片段 (手动模式)")
    p_fix.add_argument("--new-code", default=None, help="替换后的新代码片段 (手动模式)")
    p_fix.add_argument("--no-backup", action="store_true", help="不生成 .bak 备份文件")

    # docgen
    p_docgen = subparsers.add_parser("docgen", help="自动生成项目架构指南与 API 参考文档")
    p_docgen.add_argument("path", nargs="?", default=".", help="目标路径 (默认当前目录)")
    p_docgen.add_argument("--api", action="store_true", help="仅生成 API 接口文档")
    p_docgen.add_argument("--arch", action="store_true", help="仅生成项目架构依赖图文档")
    p_docgen.add_argument("-o", "--output", help="输出 Markdown 文件或保存目录路径 (默认输出到控制台)")

    # license
    p_license = subparsers.add_parser("license", help="审计代码库开源许可证合规性与传染性风险")
    p_license.add_argument("path", nargs="?", default=".", help="目标路径 (默认当前目录)")
    p_license.add_argument("--json", action="store_true", help="输出 JSON 格式审计报告")

    # perf
    p_perf = subparsers.add_parser("perf", help="静态分析循环内正则重编、低效拼接与 I/O 等性能瓶颈")
    p_perf.add_argument("path", nargs="?", default=".", help="目标路径 (默认当前目录)")

    # init-config
        # chat
    p_chat = subparsers.add_parser("chat", help="启动终端交互式对话 REPL 模式")
    p_chat.add_argument("--model", default="gpt-4o", help="LLM 模型名称")
    p_chat.add_argument("--base-url", help="自定义 LLM Base URL (如 https://api.deepseek.com/v1)")
    p_chat.add_argument("--api-key", help="自定义 LLM API Key")

    # testgen
    p_testgen = subparsers.add_parser("testgen", help="基于 AST 自动为 Python 代码生成单元测试骨架")
    p_testgen.add_argument("path", help="待生成测试的目标 Python 文件")
    p_testgen.add_argument("--framework", default="pytest", choices=["pytest", "unittest"], help="测试框架类型")
    p_testgen.add_argument("--output", help="测试代码输出文件路径 (默认输出到控制台)")

    # hooks
    subparsers.add_parser("install-hook", help="安装 Git pre-commit 安全拦截钩子")
    subparsers.add_parser("uninstall-hook", help="移除 Git pre-commit 安全拦截钩子")

        # mcp
        # gui
    p_gui = subparsers.add_parser("gui", help="启动本地桌面图形窗口应用程序")
    p_gui.add_argument("--port", type=int, default=8765, help="本地服务监听端口 (默认 8765)")

    subparsers.add_parser("mcp", help="以 Model Context Protocol (MCP) 标准 JSON-RPC 模式运行服务")

    # debt
    p_debt = subparsers.add_parser("debt", help="评估代码可维护性指数 (MI)、技术债修复时长与重复代码")
    p_debt.add_argument("path", nargs="?", default=".", help="目标路径 (默认当前目录)")

    p_init = subparsers.add_parser("init-config", help="在当前目录生成或更新 .code-agent.json 配置文件")
    p_init.add_argument("--base-url", help="预设自定义 LLM Base URL")
    p_init.add_argument("--api-key", help="预设自定义 LLM API Key")
    p_init.add_argument("--model", help="预设默认模型名称")
    subparsers.add_parser("ci-init", help="在 .github/workflows 中生成自动化审计流水线")

    # review
    p_review = subparsers.add_parser("review", help="审查 Git 变更 (Diff Review)")
    p_review.add_argument("--ref", default="HEAD", help="Git 目标比较引用 (默认 HEAD)")
    p_review.add_argument("--pr", action="store_true", help="输出 GitHub PR 格式的 Markdown 评审评论")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="运行多轮 ReAct 思考与工具调用的 Agent")
    p_analyze.add_argument("path", help="目标文件或目录路径")
    p_analyze.add_argument("--goal", default="全面审计代码中的安全漏洞、异常处理、边界条件与性能缺陷", help="分析目标")
    p_analyze.add_argument("--offline", action="store_true", help="强制使用本地离线启发式引擎")
    p_analyze.add_argument("--model", default="gpt-4o", help="LLM 模型名称")
    p_analyze.add_argument("--base-url", help="自定义 LLM Base URL (如 https://api.deepseek.com/v1)")
    p_analyze.add_argument("--api-key", help="自定义 LLM API Key")
    p_analyze.add_argument("--max-turns", type=int, default=8, help="最大交互轮次")

    args = parser.parse_args()

    dispatch = {
        "scan": cmd_scan,
        "outline": cmd_outline,
        "graph": cmd_graph,
        "fix": cmd_fix,
        "docgen": cmd_docgen,
        "license": cmd_license,
        "perf": cmd_perf,
        "chat": cmd_chat,
        "testgen": cmd_testgen,
        "install-hook": cmd_install_hook,
        "uninstall-hook": cmd_uninstall_hook,
                "gui": cmd_gui,
        "mcp": cmd_mcp,
        "debt": cmd_debt,
        "init-config": cmd_init_config,
        "ci-init": cmd_ci_init,
        "review": cmd_review,
        "analyze": cmd_analyze,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
