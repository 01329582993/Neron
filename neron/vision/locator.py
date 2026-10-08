"""Semantic and spatial element locator for desktop GUI interactions."""

import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

from neron.utils.logger import get_logger
from neron.vision.analyzer import BoundingBox, DetectedElement, ScreenAnalyzer

logger = get_logger("vision.locator")


class ElementNotFoundError(Exception):
    """Raised when an element cannot be visually located on screen."""
    pass


class ElementLocator:
    """
    Resolves natural language spatial descriptions and image templates
    to clickable screen coordinates.
    """

    def __init__(self, analyzer: Optional[ScreenAnalyzer] = None):
        self.analyzer = analyzer or ScreenAnalyzer()

    def locate_template(
        self,
        image_input: Any,
        template_input: Any,
        threshold: float = 0.8,
        label: str = "target_template",
    ) -> DetectedElement:
        """Locate the best matching template on the screen."""
        matches = self.analyzer.match_template(
            image_input=image_input,
            template_input=template_input,
            threshold=threshold,
            label=label,
            max_results=1,
        )
        if not matches:
            raise ElementNotFoundError(
                f"Template matching failed with confidence threshold >= {threshold}."
            )
        return matches[0]

    def get_spatial_region_box(
        self,
        screen_width: int,
        screen_height: int,
        region_name: str,
    ) -> BoundingBox:
        """
        Calculate bounding box for named spatial regions on screen.
        """
        w, h = screen_width, screen_height
        reg = region_name.lower().replace("-", "_").replace(" ", "_")

        if "top_left" in reg:
            return BoundingBox(0, 0, w // 3, h // 3)
        elif "top_right" in reg:
            return BoundingBox(2 * w // 3, 0, w // 3, h // 3)
        elif "top" in reg:
            return BoundingBox(w // 3, 0, w // 3, h // 3)
        elif "bottom_left" in reg:
            return BoundingBox(0, 2 * h // 3, w // 3, h // 3)
        elif "bottom_right" in reg:
            return BoundingBox(2 * w // 3, 2 * h // 3, w // 3, h // 3)
        elif "bottom" in reg:
            return BoundingBox(w // 3, 2 * h // 3, w // 3, h // 3)
        elif "left" in reg:
            return BoundingBox(0, h // 3, w // 3, h // 3)
        elif "right" in reg:
            return BoundingBox(2 * w // 3, h // 3, w // 3, h // 3)
        elif "center" in reg or "middle" in reg:
            return BoundingBox(w // 4, h // 4, w // 2, h // 2)

        # Default fallback to center screen
        return BoundingBox(w // 4, h // 4, w // 2, h // 2)

    def locate_by_description(
        self,
        image_input: Any,
        description: str,
        template_input: Optional[Any] = None,
        threshold: float = 0.8,
    ) -> DetectedElement:
        """
        Locate an element using a combination of image templates,
        spatial keywords, and UI contour detection.
        """
        # 1. Direct template matching if template provided
        if template_input is not None:
            return self.locate_template(
                image_input=image_input,
                template_input=template_input,
                threshold=threshold,
                label=description,
            )

        clean = description.lower().strip()
        img_cv = self.analyzer._to_cv2(image_input)
        h, w = img_cv.shape[:2]

        # 2. Check for explicit spatial keywords
        spatial_keywords = [
            "top left", "top right", "top center", "top",
            "bottom left", "bottom right", "bottom center", "bottom",
            "center", "middle", "left", "right"
        ]
        matched_region = None
        for kw in spatial_keywords:
            if kw in clean:
                matched_region = kw
                break

        # 3. Detect UI contours
        detected_elements = self.analyzer.detect_ui_elements(img_cv)

        # Filter by element type hint if mentioned
        target_type = None
        if "button" in clean:
            target_type = "button"
        elif "input" in clean or "field" in clean or "text box" in clean:
            target_type = "input_field"
        elif "panel" in clean or "card" in clean:
            target_type = "panel"

        filtered_candidates = [
            elem for elem in detected_elements
            if target_type is None or elem.element_type == target_type
        ] or detected_elements

        # 4. If a spatial region was found, match candidates inside that region
        if matched_region:
            region_box = self.get_spatial_region_box(w, h, matched_region)
            rx, ry, rw, rh = region_box.as_tuple()

            # Find candidates whose center falls inside region_box
            in_region = [
                elem for elem in filtered_candidates
                if rx <= elem.center[0] <= rx + rw and ry <= elem.center[1] <= ry + rh
            ]
            if in_region:
                # Return the highest confidence element in that region
                in_region.sort(key=lambda e: e.confidence, reverse=True)
                return in_region[0]

            # If no specific UI element detected inside region, return the spatial region center itself
            return DetectedElement(
                label=f"region_{matched_region}",
                bbox=region_box,
                confidence=0.75,
                element_type="spatial_region",
            )

        # 5. If candidates exist, return the most prominent one
        if filtered_candidates:
            filtered_candidates.sort(key=lambda e: e.confidence, reverse=True)
            return filtered_candidates[0]

        # 6. Fallback to center screen
        center_box = self.get_spatial_region_box(w, h, "center")
        return DetectedElement(
            label="center_fallback",
            bbox=center_box,
            confidence=0.5,
            element_type="fallback",
        )
