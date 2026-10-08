"""Neron tools subsystem."""

from neron.os.base import OSController, get_os_controller
from neron.security.policy import PermissionManager
from neron.tools.base import BaseTool, ToolResult
from neron.tools.filesystem.tools import (
    FilesystemDeleteTool,
    FilesystemListTool,
    FilesystemReadTool,
    FilesystemSearchTool,
    FilesystemWriteTool,
)
from neron.tools.registry import (
    ToolNotFoundError,
    ToolRegistry,
    ToolValidationError,
)
from neron.tools.system.tools import (
    SystemCloseAppTool,
    SystemLaunchAppTool,
    SystemTelemetryTool,
    SystemVolumeTool,
)
from neron.tools.terminal.tools import TerminalExecuteTool
from neron.tools.vision.tools import (
    VisionClickElementTool,
    VisionFindElementTool,
    VisionScreenshotTool,
    VisionTypeTextTool,
)
from neron.tools.memory.tools import (
    MemoryForgetTool,
    MemoryRecallTool,
    MemoryRememberTool,
)
from neron.tools.network.tools import (
    NetworkFetchPageTool,
    NetworkSearchTool,
    NetworkStatusTool,
)
from neron.tools.diagnostics.tools import (
    DiagnosticsRunTool,
    DiagnosticsHardwareTool,
)
from neron.tools.developer.tools import (
    DevInspectSourceTool,
    DevRunTestsTool,
    DevValidateCodeTool,
    DevCreatePluginScaffoldTool,
)


def create_default_registry(
    permission_manager: PermissionManager = None,
    os_controller: OSController = None,
) -> ToolRegistry:
    """Build and populate registry with all default built-in PC tools."""
    ctrl = os_controller or get_os_controller()
    registry = ToolRegistry(permission_manager=permission_manager)

    # Register filesystem tools
    registry.register(FilesystemSearchTool())
    registry.register(FilesystemReadTool())
    registry.register(FilesystemWriteTool())
    registry.register(FilesystemListTool())
    registry.register(FilesystemDeleteTool())

    # Register terminal tool
    registry.register(TerminalExecuteTool(os_controller=ctrl))

    # Register system tools
    registry.register(SystemTelemetryTool(os_controller=ctrl))
    registry.register(SystemLaunchAppTool(os_controller=ctrl))
    registry.register(SystemCloseAppTool(os_controller=ctrl))
    registry.register(SystemVolumeTool(os_controller=ctrl))

    # Register computer vision tools
    registry.register(VisionScreenshotTool())
    registry.register(VisionFindElementTool())
    registry.register(VisionClickElementTool())
    registry.register(VisionTypeTextTool())

    # Register memory tools
    registry.register(MemoryRememberTool())
    registry.register(MemoryRecallTool())
    registry.register(MemoryForgetTool())

    # Register network tools
    registry.register(NetworkStatusTool())
    registry.register(NetworkSearchTool())
    registry.register(NetworkFetchPageTool())

    # Register diagnostics tools (Stage 12)
    registry.register(DiagnosticsRunTool())
    registry.register(DiagnosticsHardwareTool())

    # Register developer tools (Stage 13)
    registry.register(DevInspectSourceTool())
    registry.register(DevRunTestsTool())
    registry.register(DevValidateCodeTool())
    registry.register(DevCreatePluginScaffoldTool())

    return registry


__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "ToolNotFoundError",
    "ToolValidationError",
    "create_default_registry",
    "VisionScreenshotTool",
    "VisionFindElementTool",
    "VisionClickElementTool",
    "VisionTypeTextTool",
    "MemoryRememberTool",
    "MemoryRecallTool",
    "MemoryForgetTool",
    "NetworkStatusTool",
    "NetworkSearchTool",
    "NetworkFetchPageTool",
    "DiagnosticsRunTool",
    "DiagnosticsHardwareTool",
    "DevInspectSourceTool",
    "DevRunTestsTool",
    "DevValidateCodeTool",
    "DevCreatePluginScaffoldTool",
]



