"""Computer vision screen analyzer using OpenCV for template matching and UI detection."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

from neron.utils.logger import get_logger

logger = get_logger("vision.analyzer")


@dataclass
class BoundingBox:
    """Represents a rectangular region on the screen."""
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> Tuple[int, int]:
        """Calculates center coordinate (x, y)."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        """Area of the bounding box."""
        return self.width * self.height

    def as_tuple(self) -> Tuple[int, int, int, int]:
        """Return (x, y, width, height)."""
        return (self.x, self.y, self.width, self.height)

    def to_dict(self) -> Dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
        }


@dataclass
class DetectedElement:
    """A detected UI element, visual icon, or template match."""
    label: str
    bbox: BoundingBox
    confidence: float
    element_type: str = "unknown"

    @property
    def center(self) -> Tuple[int, int]:
        return self.bbox.center

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "bbox": self.bbox.to_dict(),
            "confidence": round(self.confidence, 4),
            "element_type": self.element_type,
            "center": self.center,
        }


class ScreenAnalyzer:
    """
    OpenCV-based visual element detection and screen reasoning.

    Performs template matching, UI contour detection, and visual structure extraction.
    """

    def _to_cv2(self, img_input: Union[np.ndarray, Image.Image, bytes, str, Path]) -> np.ndarray:
        """Normalize varied image inputs into a BGR OpenCV numpy array."""
        if isinstance(img_input, np.ndarray):
            return img_input

        if isinstance(img_input, Image.Image):
            # PIL Image RGB -> BGR
            rgb = np.array(img_input)
            if len(rgb.shape) == 2:
                return cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)
            elif rgb.shape[2] == 4:
                return cv2.cvtColor(rgb, cv2.COLOR_RGBA2BGR)
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if isinstance(img_input, bytes):
            nparr = np.frombuffer(img_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode image bytes with OpenCV.")
            return img

        if isinstance(img_input, (str, Path)):
            path_str = str(img_input)
            if not Path(path_str).exists():
                raise FileNotFoundError(f"Image file does not exist: {path_str}")
            img = cv2.imread(path_str, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError(f"OpenCV failed to read image from path: {path_str}")
            return img

        raise TypeError(f"Unsupported image input type: {type(img_input)}")

    def match_template(
        self,
        image_input: Union[np.ndarray, Image.Image, bytes, str, Path],
        template_input: Union[np.ndarray, Image.Image, bytes, str, Path],
        threshold: float = 0.8,
        label: str = "template_match",
        max_results: int = 10,
    ) -> List[DetectedElement]:
        """
        Locate template occurrences in the target image using normalized cross-correlation.

        Applies Non-Maximum Suppression (NMS) to eliminate overlapping duplicate boxes.
        """
        img = self._to_cv2(image_input)
        tmpl = self._to_cv2(template_input)

        img_h, img_w = img.shape[:2]
        tmpl_h, tmpl_w = tmpl.shape[:2]

        if tmpl_h > img_h or tmpl_w > img_w:
            logger.warning("Template dimensions exceed image dimensions.")
            return []

        # Convert to grayscale for robust template matching
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)

        # If template has very low variance (flat uniform color), use TM_SQDIFF
        if float(np.std(tmpl_gray)) < 5.0:
            diff = cv2.matchTemplate(img_gray, tmpl_gray, cv2.TM_SQDIFF)
            max_diff = float(255.0 ** 2 * tmpl_w * tmpl_h)
            res = 1.0 - (diff / max_diff) if max_diff > 0 else np.zeros_like(diff, dtype=float)
        else:
            res = cv2.matchTemplate(img_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
            res = np.nan_to_num(res, nan=-1.0)

        loc = np.where(res >= threshold)


        boxes: List[Tuple[int, int, int, int, float]] = []
        for pt_y, pt_x in zip(loc[0], loc[1]):
            score = float(res[pt_y, pt_x])
            boxes.append((int(pt_x), int(pt_y), tmpl_w, tmpl_h, score))

        if not boxes:
            return []

        # Sort by confidence descending
        boxes.sort(key=lambda b: b[4], reverse=True)

        # Apply Non-Maximum Suppression (NMS)
        picked: List[Tuple[int, int, int, int, float]] = []
        for x, y, w, h, score in boxes:
            overlap = False
            for px, py, pw, ph, _ in picked:
                # Calculate Intersection over Area
                xx1 = max(x, px)
                yy1 = max(y, py)
                xx2 = min(x + w, px + pw)
                yy2 = min(y + h, py + ph)
                inter_w = max(0, xx2 - xx1)
                inter_h = max(0, yy2 - yy1)
                inter_area = inter_w * inter_h
                min_area = min(w * h, pw * ph)
                if min_area > 0 and inter_area / min_area > 0.4:
                    overlap = True
                    break
            if not overlap:
                picked.append((x, y, w, h, score))
                if len(picked) >= max_results:
                    break

        results = [
            DetectedElement(
                label=label,
                bbox=BoundingBox(x=x, y=y, width=w, height=h),
                confidence=score,
                element_type="template",
            )
            for x, y, w, h, score in picked
        ]
        return results

    def detect_ui_elements(
        self,
        image_input: Union[np.ndarray, Image.Image, bytes, str, Path],
        min_width: int = 24,
        min_height: int = 16,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> List[DetectedElement]:
        """
        Detect interactive UI elements (buttons, inputs, cards) via edge and contour analysis.
        """
        img = self._to_cv2(image_input)
        h, w = img.shape[:2]

        max_w = max_width or int(w * 0.9)
        max_h = max_height or int(h * 0.9)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 50, 150)

        # Morphological closing to connect fragmented button outlines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        elements: List[DetectedElement] = []
        for cnt in contours:
            cx, cy, cw, ch = cv2.boundingRect(cnt)

            if cw < min_width or ch < min_height:
                continue
            if cw > max_w or ch > max_h:
                continue

            # Classify element type by aspect ratio and dimensions
            aspect_ratio = cw / float(ch)
            if 1.2 <= aspect_ratio <= 7.0 and 20 <= ch <= 90:
                elem_type = "button"
            elif aspect_ratio > 4.0 and 20 <= ch <= 60:
                elem_type = "input_field"
            elif aspect_ratio >= 0.8 and cw > 150 and ch > 100:
                elem_type = "panel"
            else:
                elem_type = "container"

            # Compute contour solidity/fill confidence
            contour_area = cv2.contourArea(cnt)
            bbox_area = cw * ch
            solidity = contour_area / bbox_area if bbox_area > 0 else 0.5
            confidence = min(1.0, max(0.4, float(solidity)))

            elements.append(
                DetectedElement(
                    label=f"{elem_type}_{cx}_{cy}",
                    bbox=BoundingBox(x=cx, y=cy, width=cw, height=ch),
                    confidence=confidence,
                    element_type=elem_type,
                )
            )

        # Sort from top-to-bottom, left-to-right
        elements.sort(key=lambda e: (e.bbox.y // 20, e.bbox.x))
        return elements

    def detect_color_regions(
        self,
        image_input: Union[np.ndarray, Image.Image, bytes, str, Path],
        lower_hsv: Tuple[int, int, int],
        upper_hsv: Tuple[int, int, int],
        label: str = "color_region",
        min_area: int = 100,
    ) -> List[DetectedElement]:
        """Detect contiguous regions matching an HSV color range."""
        img = self._to_cv2(image_input)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: List[DetectedElement] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            results.append(
                DetectedElement(
                    label=label,
                    bbox=BoundingBox(x=x, y=y, width=w, height=h),
                    confidence=min(1.0, float(area / (w * h))),
                    element_type="color_region",
                )
            )
        return results

    def crop_element(
        self,
        image_input: Union[np.ndarray, Image.Image, bytes, str, Path],
        bbox: BoundingBox,
    ) -> Image.Image:
        """Crop and return the sub-image region as a PIL Image."""
        img = self._to_cv2(image_input)
        h, w = img.shape[:2]

        x1 = max(0, bbox.x)
        y1 = max(0, bbox.y)
        x2 = min(w, bbox.x + bbox.width)
        y2 = min(h, bbox.y + bbox.height)

        crop_bgr = img[y1:y2, x1:x2]
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(crop_rgb)
