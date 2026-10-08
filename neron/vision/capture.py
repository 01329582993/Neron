"""Multi-monitor screen capture module supporting MSS and Pillow ImageGrab."""

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from neron.utils.logger import get_logger

logger = get_logger("vision.capture")


class ScreenCaptureError(Exception):
    """Raised when screen capture fails."""
    pass


@dataclass
class ScreenshotResult:
    """Encapsulates captured screen image data and metadata."""
    image: Image.Image
    image_bytes: bytes
    width: int
    height: int
    monitor: int
    timestamp: float
    file_path: Optional[str] = None

    def save(self, path: str) -> str:
        """Save captured image to a file path."""
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(p, format="PNG")
        self.file_path = str(p)
        return str(p)


class ScreenCapture:
    """
    High-performance desktop screenshot capture.

    Tries MSS first for multi-monitor support and fast grabbing,
    falls back to Pillow ImageGrab if MSS is unavailable or fails.
    Supports mock/headless injection for testing and CI environments.
    """

    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or "auto"
        self._mock_image: Optional[Image.Image] = None

    def set_mock_image(self, img: Optional[Image.Image]) -> None:
        """Inject a mock image for automated testing without an active display."""
        self._mock_image = img

    def get_monitors(self) -> List[Dict[str, int]]:
        """Return information about all connected displays."""
        if self._mock_image:
            return [{"top": 0, "left": 0, "width": self._mock_image.width, "height": self._mock_image.height}]

        try:
            import mss
            with mss.mss() as sct:
                return list(sct.monitors)
        except Exception:
            # Fallback to single primary monitor resolution
            w, h = self.get_resolution()
            return [{"top": 0, "left": 0, "width": w, "height": h}]

    def get_resolution(self) -> Tuple[int, int]:
        """Return dimensions (width, height) of the primary display."""
        if self._mock_image:
            return (self._mock_image.width, self._mock_image.height)

        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            return (img.width, img.height)
        except Exception:
            return (1920, 1080)

    def capture(
        self,
        monitor: int = 1,
        region: Optional[Tuple[int, int, int, int]] = None,
        output_path: Optional[str] = None,
    ) -> ScreenshotResult:
        """
        Capture the screen or a specific region.

        Args:
            monitor: Monitor index (1 = primary monitor, 0 = all monitors combined in MSS).
            region: Optional (x, y, width, height) bounding box to crop.
            output_path: Optional file path to save the screenshot.
        """
        timestamp = time.time()

        if self._mock_image:
            img = self._mock_image.copy()
            if region:
                rx, ry, rw, rh = region
                img = img.crop((rx, ry, rx + rw, ry + rh))
            return self._build_result(img, monitor, timestamp, output_path)

        # 1. Attempt MSS capture if backend != "pil"
        if self.backend in ("auto", "mss"):
            try:
                import mss
                with mss.mss() as sct:
                    monitors = sct.monitors
                    selected_monitor = monitors[monitor] if 0 <= monitor < len(monitors) else monitors[1]

                    if region:
                        rx, ry, rw, rh = region
                        box = {
                            "top": selected_monitor["top"] + ry,
                            "left": selected_monitor["left"] + rx,
                            "width": rw,
                            "height": rh,
                        }
                    else:
                        box = selected_monitor

                    sct_img = sct.grab(box)
                    # Convert to PIL Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    return self._build_result(img, monitor, timestamp, output_path)
            except Exception as e:
                logger.warning(f"MSS screen capture failed: {e}. Falling back to Pillow ImageGrab.")

        # 2. Fallback to Pillow ImageGrab
        try:
            from PIL import ImageGrab
            if region:
                rx, ry, rw, rh = region
                bbox = (rx, ry, rx + rw, ry + rh)
                img = ImageGrab.grab(bbox=bbox, all_screens=True)
            else:
                img = ImageGrab.grab(all_screens=(monitor == 0))
            return self._build_result(img, monitor, timestamp, output_path)
        except Exception as e:
            logger.error(f"Pillow ImageGrab capture failed: {e}")
            raise ScreenCaptureError(f"Unable to capture screen: {e}") from e

    def _build_result(
        self,
        img: Image.Image,
        monitor: int,
        timestamp: float,
        output_path: Optional[str],
    ) -> ScreenshotResult:
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        saved_path = None
        if output_path:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "wb") as f:
                f.write(image_bytes)
            saved_path = str(p)

        return ScreenshotResult(
            image=img,
            image_bytes=image_bytes,
            width=img.width,
            height=img.height,
            monitor=monitor,
            timestamp=timestamp,
            file_path=saved_path,
        )
