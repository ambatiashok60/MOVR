"""Process-lifetime singletons.

Everything here is constructed exactly once at import time. Stateful AI Workspace stores use
SQLite by default so sessions, executions, plans, review decisions, and selected context survive
backend restarts. Set AI_WORKSPACE_STATE_BACKEND=mysql to use a shared MySQL instance, or
AI_WORKSPACE_STATE_BACKEND=memory only for throwaway local demos.
"""

from worktop.ai_workspace.app.ai_workspace.application.tools.apply_patch_tool import ApplyPatchTool
from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import BaseTool
from worktop.ai_workspace.app.ai_workspace.application.tools.git_diff_tool import GitDiffTool
from worktop.ai_workspace.app.ai_workspace.application.tools.list_files_tool import ListFilesTool
from worktop.ai_workspace.app.ai_workspace.application.tools.read_file_tool import ReadFileTool
from worktop.ai_workspace.app.ai_workspace.application.tools.run_test_command_tool import RunTestCommandTool
from worktop.ai_workspace.app.ai_workspace.application.tools.search_repository_tool import SearchRepositoryTool
from worktop.ai_workspace.app.ai_workspace.application.tools.tool_registry import ToolRegistry
from worktop.ai_workspace.app.ai_workspace.application.tools.write_file_tool import WriteFileTool
from worktop.ai_workspace.app.ai_workspace.infrastructure.in_memory_execution_store import InMemoryExecutionStore
from worktop.ai_workspace.app.ai_workspace.infrastructure.in_memory_plan_store import InMemoryPlanStore
from worktop.ai_workspace.app.ai_workspace.infrastructure.in_memory_review_store import InMemoryReviewStore
from worktop.ai_workspace.app.ai_workspace.infrastructure.in_memory_runtime_store import InMemoryRuntimeStore
from worktop.ai_workspace.app.ai_workspace.infrastructure.in_memory_session_store import InMemorySessionStore
from worktop.ai_workspace.app.ai_workspace.infrastructure.local_workspace_provider import LocalWorkspaceProvider
from worktop.ai_workspace.app.ai_workspace.infrastructure.mysql_state_store import MySQLStateStore
from worktop.ai_workspace.app.ai_workspace.infrastructure.sqlite_state_store import (
    SQLiteExecutionStore,
    SQLitePlanStore,
    SQLiteReviewStore,
    SQLiteRuntimeStore,
    SQLiteSessionStore,
    SQLiteStateStore,
)
from worktop.ai_workspace.app.ai_workspace.infrastructure.sse_event_publisher import SseEventPublisher
from worktop.ai_workspace.app.config.settings import get_settings
from worktop.ai_workspace.app.repository.application.file_read_service import FileReadService
from worktop.ai_workspace.app.repository.application.file_write_service import FileWriteService
from worktop.ai_workspace.app.repository.application.git_diff_service import GitDiffService
from worktop.ai_workspace.app.repository.application.repository_access_service import RepositoryAccessService
from worktop.ai_workspace.app.repository.application.repository_scan_service import RepositoryScanService
from worktop.ai_workspace.app.repository.application.repository_search_service import RepositorySearchService
from worktop.ai_workspace.app.repository.application.repository_tree_service import RepositoryTreeService
from worktop.ai_workspace.app.repository.application.workspace_transaction_service import WorkspaceTransactionService
from worktop.ai_workspace.app.repository.application.isolated_workspace_service import IsolatedWorkspaceService
from worktop.ai_workspace.app.ai_workspace.application.context.repository_memory_service import RepositoryMemoryService
from worktop.ai_workspace.app.repository.infrastructure.git_cli_provider import GitCliProvider
from worktop.ai_workspace.app.repository.infrastructure.local_file_writer import LocalFileWriter
from worktop.ai_workspace.app.repository.infrastructure.local_repository_access_provider import LocalRepositoryAccessProvider
from worktop.ai_workspace.app.utils.logging_utils import build_log_context, log_step


class Container:
    def __init__(self):
        settings = get_settings()

        # Repository layer
        self.repository_access_provider = LocalRepositoryAccessProvider()
        self.file_writer = LocalFileWriter()
        self.git_cli_provider = GitCliProvider()
        self.local_workspace_provider = LocalWorkspaceProvider()

        self.repository_access_service = RepositoryAccessService(self.repository_access_provider)
        self.repository_scan_service = RepositoryScanService(self.repository_access_provider)
        self.repository_tree_service = RepositoryTreeService(self.repository_scan_service)
        self.repository_search_service = RepositorySearchService(self.repository_access_provider)
        self.file_read_service = FileReadService(self.repository_access_service)
        self.file_write_service = FileWriteService(self.file_writer)
        self.workspace_transaction_service = WorkspaceTransactionService(
            settings.transaction_root,
            self.file_write_service,
            settings.workspace_stale_lock_seconds,
        )
        self.isolated_workspace_service = IsolatedWorkspaceService(settings.transaction_root)
        self.repository_memory_service = RepositoryMemoryService(settings.transaction_root)
        self.git_diff_service = GitDiffService(self.git_cli_provider)

        # AI Workspace infrastructure
        self._configure_state_stores(settings)
        self.sse_publisher = SseEventPublisher()

        # Tools
        self.tool_registry = ToolRegistry(self._build_tools())

    def _build_tools(self) -> list[BaseTool]:
        return [
            ReadFileTool(self.file_read_service),
            WriteFileTool(self.file_write_service),
            SearchRepositoryTool(self.repository_search_service),
            ListFilesTool(self.repository_tree_service),
            GitDiffTool(self.git_diff_service),
            RunTestCommandTool(),
            ApplyPatchTool(self.review_store, self.file_write_service, self.workspace_transaction_service),
        ]

    def _configure_state_stores(self, settings) -> None:
        log_step(
            "ai_workspace_state_store_configuring",
            build_log_context(state_backend=settings.state_backend, stage="state_store"),
        )
        if settings.state_backend == "memory":
            self.runtime_store = InMemoryRuntimeStore()
            self.session_store = InMemorySessionStore()
            self.review_store = InMemoryReviewStore()
            self.execution_store = InMemoryExecutionStore()
            self.plan_store = InMemoryPlanStore()
            log_step(
                "ai_workspace_state_store_configured",
                build_log_context(state_backend="memory", stage="state_store"),
            )
            return

        if settings.state_backend == "sqlite":
            state = SQLiteStateStore(settings.state_db_path)
        elif settings.state_backend == "mysql":
            state = MySQLStateStore(
                host=settings.mysql_host,
                port=settings.mysql_port,
                database=settings.mysql_database,
                user=settings.mysql_user,
                password=settings.mysql_password,
                table_name=settings.mysql_state_table,
            )
        else:
            raise RuntimeError(f"Unsupported AI Workspace state backend: {settings.state_backend}")

        self.runtime_store = SQLiteRuntimeStore(state)
        self.session_store = SQLiteSessionStore(state)
        self.review_store = SQLiteReviewStore(state)
        self.execution_store = SQLiteExecutionStore(state)
        self.plan_store = SQLitePlanStore(state)
        log_step(
            "ai_workspace_state_store_configured",
            build_log_context(state_backend=settings.state_backend, stage="state_store"),
        )


container = Container()
