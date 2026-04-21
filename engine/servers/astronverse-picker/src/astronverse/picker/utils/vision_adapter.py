import base64
import contextlib
import io

import pyautogui
import numpy as np
from PIL import Image

from astronverse.vision.core import CvCore
from astronverse.vision.cv_match import AnchorMatch
from astronverse.vision.cv_picker import ImageDetector as VisionImageDetector


class RectHandler:
    @staticmethod
    def get_foreground_window_rect():
        width, height = pyautogui.size()
        return None, "Unknown", (0, 0, width, height)


class ImageDetector(VisionImageDetector):
    def __init__(self, img=None):
        if img is None:
            super().__init__()
            return

        if isinstance(img, Image.Image):
            img = cv_pil_to_bgr(img)

        super().__init__()
        self.get_image_from_gradio(img)

    @staticmethod
    def apply_nms(boxes: list[list[int]], iou_threshold: float = 0.3) -> list[list[int]]:
        """使用 numpy + 相交预筛选优化 NMS，降低全屏场景耗时。"""
        if not boxes:
            return []

        boxes_array = np.array(boxes, dtype=np.float32)
        areas = boxes_array[:, 2] * boxes_array[:, 3]
        order = np.argsort(boxes_array[:, 2])

        keep_boxes = []
        suppressed = np.zeros(len(boxes), dtype=bool)

        for idx in range(len(order) - 1, -1, -1):
            i = order[idx]
            if suppressed[i]:
                continue

            keep_boxes.append(boxes[i])

            x1, y1, w1, h1 = boxes_array[i]
            x1_max, y1_max = x1 + w1, y1 + h1
            area1 = areas[i]

            for jdx in range(idx):
                j = order[jdx]
                if suppressed[j]:
                    continue

                x2, y2, w2, h2 = boxes_array[j]
                x2_max, y2_max = x2 + w2, y2 + h2

                if x1_max <= x2 or x2_max <= x1 or y1_max <= y2 or y2_max <= y1:
                    continue

                inter_x1 = max(x1, x2)
                inter_y1 = max(y1, y2)
                inter_x2 = min(x1_max, x2_max)
                inter_y2 = min(y1_max, y2_max)
                inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)

                if inter_area <= 0:
                    continue

                area2 = areas[j]
                union_area = area1 + area2 - inter_area
                iou = inter_area / union_area
                if iou >= iou_threshold or iou < 0.0003:
                    suppressed[j] = True

        return keep_boxes

    def detect_objects(self, dash_color, line_width):
        """
        复用基类流程，但屏蔽基类内的 print 调试输出，
        避免全屏大列表输出拖慢处理。
        """
        with contextlib.redirect_stdout(io.StringIO()):
            return super().detect_objects(dash_color, line_width)


class PickCore:
    @staticmethod
    def get_mouse_position():
        current_position = pyautogui.position()
        return current_position.x, current_position.y

    @staticmethod
    def image_to_base64(img):
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="PNG")
        img_byte_arr = img_byte_arr.getvalue()
        return base64.b64encode(img_byte_arr).decode("utf-8")

    @staticmethod
    def json_res(target_img, target_rect, anchor_img, anchor_rect, screen):
        def encode_image(image):
            return PickCore.image_to_base64(image) if image else ""

        def get_position(rect, index):
            return rect[index] if rect else ""

        if not screen:
            screen = pyautogui.screenshot(region=None)

        res = {
            "version": "1",
            "type": "cv",
            "app": "",
            "path": "",
            "img": {
                "self": encode_image(target_img),
                "parent": encode_image(anchor_img),
            },
            "pos": {
                "self_x": get_position(target_rect, 0),
                "self_y": get_position(target_rect, 1),
                "parent_x": get_position(anchor_rect, 0),
                "parent_y": get_position(anchor_rect, 1),
            },
            "sr": {"screen_w": screen.width, "screen_h": screen.height},
            "picker_type": "ELEMENT",
        }

        if not (target_img or anchor_img or target_rect or anchor_rect):
            return None

        import json

        return json.dumps(res, ensure_ascii=False)

    @staticmethod
    def base64_to_image(base64_str):
        if not base64_str:
            return None
        image_data = base64.b64decode(base64_str)
        return Image.open(io.BytesIO(image_data))

    @staticmethod
    def match_imgs(data, canny_flag=False):
        return CvCore.match_imgs({"elementData": data}, canny_flag=canny_flag)


def cv_pil_to_bgr(img: Image.Image):
    img_np = np.array(img)
    if img_np.ndim == 2:
        return img_np
    if img_np.shape[2] == 4:
        import cv2

        return cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    import cv2

    return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
