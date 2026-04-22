import base64
import contextlib
import io
import json
import os
import subprocess
import sys
import threading
import time
import tempfile

import cv2
import pyautogui
import numpy as np
from PIL import Image

from astronverse.vision.core import CvCore
from astronverse.vision.cv_match import AnchorMatch
from astronverse.vision.cv_picker import ImageDetector as VisionImageDetector
from astronverse.picker.logger import logger


class RectHandler:
    @staticmethod
    def get_foreground_window_rect():
        width, height = pyautogui.size()
        return None, "Unknown", (0, 0, width, height)


class ImageDetector(VisionImageDetector):
    _SUBPROCESS_CODE = r"""
import json
import sys
import time

import cv2
import numpy as np


def compute_canny_edge(grey):
    return cv2.Canny(grey, 100, 150)


def compute_sobel_gradient(blurred):
    grad_x = cv2.Sobel(blurred, ddepth=cv2.CV_32F, dx=1, dy=0)
    grad_y = cv2.Sobel(blurred, ddepth=cv2.CV_32F, dx=0, dy=1)
    gradient = cv2.subtract(grad_x, grad_y)
    return cv2.convertScaleAbs(gradient)


def apply_threshold_and_blur(gradient):
    _, thresh = cv2.threshold(gradient, 75, 255, cv2.THRESH_BINARY)
    return thresh


def apply_morphology(thresh):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.dilate(thresh, kernel, iterations=3)


def fill_hole(masker):
    _, mask = cv2.threshold(masker, 30, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        if cv2.contourArea(contour) < 200:
            x, y, w, h = cv2.boundingRect(contour)
            mask[y : y + h, x : x + w] = 255
    return mask


def preprocess_stage(gradient):
    thresh = apply_threshold_and_blur(gradient)
    closed = apply_morphology(thresh)
    contours = fill_hole(closed)
    contours, _ = cv2.findContours(contours, cv2.RETR_TREE, cv2.CHAIN_APPROX_TC89_KCOS)
    return contours


def apply_nms(boxes, iou_threshold=0.3):
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


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: python -c <code> <image_path>"}))
        sys.exit(1)

    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(json.dumps({"ok": False, "error": f"failed to read image: {sys.argv[1]}"}))
        sys.exit(1)

    started = time.perf_counter()
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray_img, (3, 3), 0)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(blurred, -1, kernel)
    canny_gradient = compute_canny_edge(sharpened)
    sobel_gradient = compute_sobel_gradient(sharpened)

    _, fore_g = cv2.threshold(canny_gradient, 127, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    fore_g = cv2.dilate(fore_g, kernel, iterations=2)
    _, fore_markers = cv2.connectedComponents(fore_g)
    fore_markers = fore_markers.astype(np.uint8)
    fore_contours, _ = cv2.findContours(fore_markers.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    sobel_contours = preprocess_stage(sobel_gradient)

    img_area = img.shape[0] * img.shape[1]
    fore_boxes = [
        (x, y, w, h)
        for x, y, w, h in (cv2.boundingRect(contour) for contour in fore_contours)
        if (w * h) > 50 and (h / w) < 10 and (w * h) / img_area < 0.2
    ]
    sobel_boxes = [
        (x, y, w, h)
        for x, y, w, h in (cv2.boundingRect(contour) for contour in sobel_contours)
        if (w * h) > 50 and (h / w) < 10 and (w * h) / img_area < 0.2
    ]
    boxes = apply_nms([list(box) for box in (fore_boxes + sobel_boxes)])
    print(json.dumps({
        "ok": True,
        "boxes": boxes,
        "elapsed": time.perf_counter() - started,
        "fore_contours": len(fore_contours),
        "sobel_contours": len(sobel_contours),
        "fore_boxes": len(fore_boxes),
        "sobel_boxes": len(sobel_boxes),
    }))


if __name__ == "__main__":
    main()
"""

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

    def _detect_objects_via_subprocess(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            temp_path = tmp_file.name
        try:
            cv2.imwrite(temp_path, self.original_img)
            started = time.perf_counter()
            completed = subprocess.run(
                [sys.executable, "-c", self._SUBPROCESS_CODE, temp_path],
                capture_output=True,
                text=True,
                check=False,
            )
            worker_wall = time.perf_counter() - started
            if completed.returncode != 0:
                raise RuntimeError(
                    f"worker exited with code {completed.returncode}, stderr={completed.stderr.strip()}"
                )
            payload = json.loads(completed.stdout.strip())
            if not payload.get("ok"):
                raise RuntimeError(f"worker failed: {payload}")
            logger.info(
                "VisionAdapter detect_objects subprocess "
                f"worker_wall={worker_wall:.3f}s worker_elapsed={payload.get('elapsed')} "
                f"fore_contours={payload.get('fore_contours')} sobel_contours={payload.get('sobel_contours')} "
                f"fore_boxes={payload.get('fore_boxes')} sobel_boxes={payload.get('sobel_boxes')} "
                f"selected={len(payload.get('boxes', []))}"
            )
            return self.original_img, payload["boxes"]
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def detect_objects(self, dash_color, line_width, draw_boxes: bool = False):
        """
        默认使用快速路径：仅计算候选框，不做虚线绘制与深拷贝。
        若需要兼容旧行为可传 draw_boxes=True。
        """
        try:
            if not draw_boxes:
                return self._detect_objects_via_subprocess()
        except Exception as e:
            logger.warning(f"VisionAdapter detect_objects subprocess failed, fallback=in_process err={e}")

        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)

        if draw_boxes:
            with contextlib.redirect_stdout(io.StringIO()):
                return super().detect_objects(dash_color, line_width)

        # 下面逻辑与基类 detect_objects 保持同等筛选流程，
        # 但跳过 output 图绘制阶段，减少全屏场景耗时。
        total_started = time.perf_counter()
        total_thread_started = time.thread_time()
        detector_meta_logged = False

        def elapsed(start_wall, start_thread):
            return time.perf_counter() - start_wall, time.thread_time() - start_thread

        stage_started = time.perf_counter()
        stage_thread_started = time.thread_time()
        blurred = cv2.GaussianBlur(self.gray_img, (3, 3), 0)
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(blurred, -1, kernel)
        preprocess_elapsed, preprocess_cpu = elapsed(stage_started, stage_thread_started)

        stage_started = time.perf_counter()
        stage_thread_started = time.thread_time()
        canny_gradient = self.compute_canny_edge(sharpened)
        sobel_gradient = self.compute_sobel_gradient(sharpened)
        gradient_elapsed, gradient_cpu = elapsed(stage_started, stage_thread_started)

        if not detector_meta_logged:
            detector_meta_logged = True
            logger.info(
                "VisionAdapter detect_objects runtime "
                f"pid={os.getpid()} thread={threading.current_thread().name} "
                f"thread_ident={threading.get_ident()} active_threads={threading.active_count()} "
                f"cv_threads={cv2.getNumThreads()} image_shape={self.original_img.shape}"
            )

        stage_started = time.perf_counter()
        stage_thread_started = time.thread_time()
        _, fore_g = cv2.threshold(canny_gradient, 127, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((3, 3), np.uint8)
        fore_g = cv2.dilate(fore_g, kernel, iterations=2)
        _, fore_markers = cv2.connectedComponents(fore_g)
        fore_markers = fore_markers.astype(np.uint8)
        fore_contours, _ = cv2.findContours(fore_markers.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        foreground_elapsed, foreground_cpu = elapsed(stage_started, stage_thread_started)

        stage_started = time.perf_counter()
        stage_thread_started = time.thread_time()
        sobel_contours = self.preprocess_stage(sobel_gradient, False)
        sobel_elapsed, sobel_cpu = elapsed(stage_started, stage_thread_started)

        # 旧版 detect_objects 虽然会计算 canny_contours/canny_boxes，
        # 但最终返回结果只使用 fore_boxes + sobel_boxes。
        # 快速路径中跳过这段纯冗余计算，保持输出等价并降低 ALT 耗时。
        canny_contours = []
        canny_elapsed = 0.0

        img_h, img_w = self.original_img.shape[0], self.original_img.shape[1]
        img_area = img_h * img_w

        stage_started = time.perf_counter()
        stage_thread_started = time.thread_time()
        fore_boxes = [
            (x, y, w, h)
            for x, y, w, h in (cv2.boundingRect(contour) for contour in fore_contours)
            if (w * h) > 50 and (h / w) < 10 and (w * h) / img_area < 0.2
        ]

        sobel_boxes = [
            (x, y, w, h)
            for x, y, w, h in (cv2.boundingRect(contour) for contour in sobel_contours)
            if (w * h) > 50 and (h / w) < 10 and (w * h) / img_area < 0.2
        ]

        box_filter_elapsed, box_filter_cpu = elapsed(stage_started, stage_thread_started)

        all_boxes = [list(box) for box in (fore_boxes + sobel_boxes)]
        stage_started = time.perf_counter()
        stage_thread_started = time.thread_time()
        selected_boxes = self.apply_nms(all_boxes)
        nms_elapsed, nms_cpu = elapsed(stage_started, stage_thread_started)
        total_elapsed, total_cpu = elapsed(total_started, total_thread_started)
        logger.info(
            "VisionAdapter detect_objects timing "
            f"total={total_elapsed:.3f}s total_cpu={total_cpu:.3f}s "
            f"preprocess={preprocess_elapsed:.3f}s/{preprocess_cpu:.3f}s "
            f"gradient={gradient_elapsed:.3f}s/{gradient_cpu:.3f}s "
            f"foreground={foreground_elapsed:.3f}s/{foreground_cpu:.3f}s "
            f"sobel={sobel_elapsed:.3f}s/{sobel_cpu:.3f}s "
            f"canny={canny_elapsed:.3f}s "
            f"box_filter={box_filter_elapsed:.3f}s/{box_filter_cpu:.3f}s "
            f"nms={nms_elapsed:.3f}s/{nms_cpu:.3f}s "
            f"fore_contours={len(fore_contours)} sobel_contours={len(sobel_contours)} "
            f"canny_contours={len(canny_contours)} fore_boxes={len(fore_boxes)} "
            f"sobel_boxes={len(sobel_boxes)} total_boxes={len(all_boxes)} "
            f"selected={len(selected_boxes)}"
        )
        return self.original_img, selected_boxes

    def detect_objects_legacy(self, dash_color, line_width):
        """调试用：强制走基类完整路径（含绘制）。"""
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
