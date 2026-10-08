"""Implementation of neron-system-monitor plugin."""

from typing import Any, Dict, List

from neron.os.base import get_os_controller
from neron.plugins.base import PluginBase
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.tools.registry import ToolRegistry


class SysmonCheckStatusTool(BaseTool):
    """Tool that checks hardware metrics against alert thresholds."""

    def __init__(self, cpu_threshold: int = 85, ram_threshold: int = 90):
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.os_ctrl = get_os_controller()

    @property
    def name(self) -> str:
        return "sysmon.check_status"

    @property
    def description(self) -> str:
        return "Check system hardware load against warning thresholds and return health summary."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.SYSTEM_INSPECT]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            telem = self.os_ctrl.get_telemetry()
            cpu_alert = telem.cpu_percent > self.cpu_threshold
            ram_alert = telem.memory_percent > self.ram_threshold
            status = "WARNING" if (cpu_alert or ram_alert) else "HEALTHY"

            return ToolResult(
                success=True,
                output={
                    "status": status,
                    "cpu_percent": telem.cpu_percent,
                    "cpu_alert": cpu_alert,
                    "memory_percent": telem.memory_percent,
                    "memory_alert": ram_alert,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Sysmon check failed: {e}")


class SystemMonitorPlugin(PluginBase):
    """Lifecycle controller for the System Monitor plugin."""

    def __init__(self, metadata=None, config=None):
        super().__init__(metadata=metadata, config=config)
        cpu_t = self.config.get("cpu_threshold", 85)
        ram_t = self.config.get("ram_threshold", 90)
        self.tool = SysmonCheckStatusTool(cpu_threshold=cpu_t, ram_threshold=ram_t)

    def on_load(self) -> bool:
        self.logger.debug("SystemMonitorPlugin loaded.")
        return True

    def on_enable(self, registry: ToolRegistry) -> None:
        registry.register(self.tool)
        self.logger.info("SystemMonitorPlugin registered sysmon.check_status tool.")

    def on_disable(self, registry: ToolRegistry) -> None:
        registry.unregister("sysmon.check_status")
        self.logger.info("SystemMonitorPlugin unregistered sysmon.check_status tool.")
