"""Code Analysis Agent Package."""

from .agent import CodeAnalysisAgent
from .ast_parser import ASTParser, CodeSymbol
from .batch_fixer import BatchFixer, FixResult
from .cache import IncrementalCache
from .call_graph import DependencyGraph
from .ci_integration import CIIntegration
from .cli import main
from .config import AgentConfig
from .custom_rules import CustomRule, CustomRuleLoader
from .debt_estimator import DebtEstimator, TechnicalDebtReport
from .doc_generator import DocGenerator
from .git_tools import GitTools
from .gui_app import launch_gui
from .gui_server import start_server
from .gui_tk import TkinterDesktopApp
from .hook import PreCommitHook
from .html_report import HTMLReportGenerator
from .license_checker import LicenseChecker, LicenseReport
from .mcp_server import MCPServer
from .models import Finding
from .multi_lang import MultiLangScanner
from .patcher import Patcher
from .perf_advisor import PerformanceAdvisor
from .pr_reviewer import PRReviewer
from .repl import InteractiveREPL
from .report_formatter import ReportFormatter
from .sarif import SARIFExporter
from .security_rules import CodeRuleEngine
from .test_generator import TestGenerator
from .tools import ToolRegistry

__all__ = [
    "CodeAnalysisAgent",
    "ASTParser",
    "CodeSymbol",
    "BatchFixer",
    "FixResult",
    "DependencyGraph",
    "DocGenerator",
    "IncrementalCache",
    "CIIntegration",
    "HTMLReportGenerator",
    "LicenseChecker",
    "LicenseReport",
    "MultiLangScanner",
    "MCPServer",
    "DebtEstimator",
    "TechnicalDebtReport",
    "PRReviewer",
    "PerformanceAdvisor",
    "CustomRule",
    "CustomRuleLoader",
    "AgentConfig",
    "GitTools",
    "Patcher",
    "PreCommitHook",
    "InteractiveREPL",
    "SARIFExporter",
    "TestGenerator",
    "CodeRuleEngine",
    "Finding",
    "ToolRegistry",
    "ReportFormatter",
    "launch_gui",
    "start_server",
    "TkinterDesktopApp",
    "main",
]
