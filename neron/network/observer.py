"""Network connectivity observer and offline/online transition monitor."""

import socket
import threading
import time
from typing import Any, Dict, Optional

from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import Event
from neron.utils.logger import get_logger

logger = get_logger("network.observer")

EVENT_NETWORK_CHANGED = "network.status_changed"


class NetworkObserver:
    """
    Monitors internet connectivity with low overhead and zero-latency cached reads.
    Publishes events to EventBus when network state transitions.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        cache_ttl_seconds: float = 5.0,
        probe_host: str = "1.1.1.1",
        probe_port: int = 53,
    ):
        self.event_bus = event_bus or get_default_bus()
        self.cache_ttl = cache_ttl_seconds
        self.probe_host = probe_host
        self.probe_port = probe_port

        self._lock = threading.RLock()
        self._is_online: Optional[bool] = None
        self._last_check_time: float = 0.0
        self._last_latency_ms: float = 0.0
        self._mock_online: Optional[bool] = None

    def set_mock_status(self, is_online: Optional[bool]) -> None:
        """Inject simulated network status for testing and deterministic environments."""
        with self._lock:
            self._mock_online = is_online
            if is_online is not None:
                self._is_online = is_online

    def check_connection(self, force: bool = False) -> Dict[str, Any]:
        """
        Check if internet is reachable. Returns status dictionary.
        Uses cached result if checked within cache_ttl_seconds unless force=True.
        """
        with self._lock:
            now = time.time()
            if not force and (now - self._last_check_time) < self.cache_ttl and self._is_online is not None:
                return {
                    "online": self._is_online,
                    "latency_ms": round(self._last_latency_ms, 2),
                    "cached": True,
                }

            if self._mock_online is not None:
                self._is_online = self._mock_online
                self._last_latency_ms = 5.0 if self._mock_online else 0.0
                self._last_check_time = now
                return {
                    "online": self._is_online,
                    "latency_ms": self._last_latency_ms,
                    "cached": False,
                }

            # Probe raw socket connection with 1-second timeout
            previous_status = self._is_online
            start = time.time()
            try:
                with socket.create_connection((self.probe_host, self.probe_port), timeout=1.0):
                    latency = (time.time() - start) * 1000.0
                    current_status = True
            except (OSError, socket.timeout):
                latency = 0.0
                current_status = False

            self._is_online = current_status
            self._last_latency_ms = latency
            self._last_check_time = now

            # If status changed, publish event
            if previous_status is not None and previous_status != current_status:
                logger.info(f"Network transition detected: {'ONLINE' if current_status else 'OFFLINE'}")
                self.event_bus.publish(
                    Event(
                        event_type=EVENT_NETWORK_CHANGED,
                        payload={
                            "online": current_status,
                            "latency_ms": latency,
                            "timestamp": now,
                        },
                    )
                )

            return {
                "online": current_status,
                "latency_ms": round(latency, 2),
                "cached": False,
            }

    @property
    def is_online(self) -> bool:
        """Quick cached property check."""
        return self.check_connection()["online"]
