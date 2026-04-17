"""
VisionServer - 视觉拾取状态机

职责：
- 接收 PickerServer 路由过来的 VISION_START / VALIDATE / DESIGNATE 信号
- 在独立线程中运行状态机，通过 HlHandler 控制 hl 进程
- 接收 hl 回传的 feedback（截图、确认、停止、继续）
- 调用 OpenCV 算法（ImageDetector / AnchorMatch / IPickCore）
- 完成后将结果写入 SyncMap，解除 VisionHandler 的阻塞等待
"""

import queue
import threading
import time
import traceback

import pyautogui
from pynput import keyboard

from astronverse.picker import VisionAction, VisionHlFeedback
from astronverse.picker.logger import logger


class VisionServer:
    """视觉拾取服务 - 独立线程状态机"""

    def __init__(self, service_context):
        self.svc = service_context
        self._hl_feedback_queue: queue.Queue = queue.Queue()
        self._active_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def on_hl_feedback(self, data: dict) -> None:
        """由 WsServer 在 hl 消息到达时调用（异步上下文，线程安全）"""
        self._hl_feedback_queue.put(data)

    def handle(self, sign: dict) -> None:
        """由 PickerServer 在主轮询线程调用"""
        if VisionAction.START.value in sign:
            self._start_session(VisionAction.START, sign)
        elif VisionAction.VALIDATE.value in sign:
            self._start_session(VisionAction.VALIDATE, sign)
        elif VisionAction.DESIGNATE.value in sign:
            self._start_session(VisionAction.DESIGNATE, sign)

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def _start_session(self, action: VisionAction, sign: dict) -> None:
        """启动独立线程运行状态机，单会话保护"""
        with self._lock:
            if self._active_thread and self._active_thread.is_alive():
                logger.warning("VisionServer: 已有活跃会话，忽略新请求")
                return
            # 清空旧 feedback
            while not self._hl_feedback_queue.empty():
                try:
                    self._hl_feedback_queue.get_nowait()
                except queue.Empty:
                    break

            data = sign[action.value]
            self._active_thread = threading.Thread(
                target=self._run_session,
                args=(action, data, sign),
                daemon=True,
            )
            self._active_thread.start()

    def _run_session(self, action: VisionAction, data: dict, sign: dict) -> None:
        """状态机主入口（在独立线程中运行）"""
        result_key = f"{action.value}_RES"
        result = None
        try:
            if action == VisionAction.START:
                result = self._run_start()
            elif action == VisionAction.VALIDATE:
                result = self._run_validate(data)
            elif action == VisionAction.DESIGNATE:
                result = self._run_designate(data)
        except Exception as e:
            logger.error("VisionServer 会话异常: %s\n%s", e, traceback.format_exc())
            result = str(e)
        finally:
            del sign[action.value]
            sign[result_key] = result

    # ------------------------------------------------------------------
    # START 状态机
    # ------------------------------------------------------------------

    def _run_start(self) -> str | None:
        """
        START 状态机：
        1. 通知 hl 进入 vision_wait 模式
        2. 监听键盘（Alt / Ctrl / ESC / Shift）
        3. Alt → 请求 hl 截图 → 接收截图 → 分割 → 鼠标追踪 → 等待确认
        4. Ctrl → 请求 hl 截图 → 接收截图 → 鼠标追踪（无分割）→ 等待确认
        5. 确认 → check_target → 返回结果
        6. ESC / 超时 → 返回 "cancel"
        """
        hl = self.svc.ws_server.hl

        # 通知 hl 进入等待模式
        hl.cv_start_sync("vision_wait")

        # 键盘状态
        current_keys: set = set()
        key_event: dict = {"mode": None}  # "alt" | "ctrl" | "esc" | "shift"
        key_lock = threading.Lock()

        def on_press(key):
            current_keys.add(key)
            with key_lock:
                if key == keyboard.Key.esc:
                    key_event["mode"] = "esc"
                elif (
                    key in (keyboard.Key.alt_l, keyboard.Key.alt_gr)
                    and len(current_keys) == 1
                ):
                    key_event["mode"] = "alt"
                elif (
                    key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)
                    and len(current_keys) == 1
                ):
                    key_event["mode"] = "ctrl"
                elif (
                    key in (keyboard.Key.shift_l, keyboard.Key.shift_r)
                    and len(current_keys) == 1
                ):
                    key_event["mode"] = "shift"

        def on_release(key):
            current_keys.discard(key)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        try:
            start_time = time.time()
            timeout = 60 * 3  # 3 分钟超时

            while True:
                if time.time() - start_time > timeout:
                    hl.cv_initialize_sync("ESC")
                    return "cancel"

                with key_lock:
                    mode = key_event.get("mode")
                    key_event["mode"] = None

                if mode == "esc":
                    hl.cv_initialize_sync("ESC")
                    return "cancel"

                if mode == "shift":
                    hl.cv_initialize_sync("SHIFT")
                    # 重置，继续等待
                    continue

                if mode in ("alt", "ctrl"):
                    # 请求截图（hl 会自动维护截图状态，无需手动 hide）
                    hl.request_screenshot_sync()

                    # 等待 hl 回传截图
                    screenshot_data = self._wait_feedback(
                        VisionHlFeedback.SCREENSHOT, timeout_sec=10
                    )
                    if screenshot_data is None:
                        logger.warning("VisionServer: 截图超时，重新等待")
                        hl.cv_start_sync("vision_wait")
                        continue

                    # 解码截图
                    desktop_image = self._decode_screenshot(screenshot_data)
                    if desktop_image is None:
                        hl.cv_start_sync("vision_wait")
                        continue

                    screen_w, screen_h = desktop_image.size

                    if mode == "alt":
                        # ALT 模式：分割界面元素
                        hl.cv_start_sync("alt")
                        bboxes, partial_rect = self._detect_alt(desktop_image)
                    else:
                        # CTRL 模式：全屏，无分割
                        hl.cv_start_sync("ctrl")
                        bboxes = None
                        partial_rect = (0, 0, screen_w, screen_h)

                    # 鼠标追踪循环
                    result = self._mouse_track_loop(
                        hl, desktop_image, bboxes, screen_w, screen_h
                    )

                    if result == "cancel":
                        hl.cv_initialize_sync("ESC")
                        return "cancel"
                    if result == "shift":
                        hl.cv_initialize_sync("SHIFT")
                        # hl.cv_start_sync("vision_wait")
                        continue
                    if result is not None:
                        # 有目标 rect，进行 check_target
                        pick_result = self._check_target(result, desktop_image, bboxes, partial_rect)
                        if pick_result:
                            hl.cv_initialize_sync("ESC")
                            return pick_result
                        else:
                            # 目标获取失败，重新等待
                            # hl.cv_start_sync("vision_wait")
                            continue

                time.sleep(0.05)
        finally:
            listener.stop()

    def _mouse_track_loop(self, hl, desktop_image, bboxes, screen_w, screen_h):
        """
        鼠标追踪循环：实时发送鼠标位置和命中 rect 给 hl
        返回：
          - tuple (left, top, right, bottom)：用户确认的目标 rect
          - "cancel"：ESC
          - "shift"：Shift 重置
          - None：stop 信号
        """
        from astronverse.picker import Rect

        last_mouse_pos = None
        draw_rect = None
        last_draw_rect = None
        start_time = time.time()
        timeout = 60 * 3

        while True:
            if time.time() - start_time > timeout:
                return "cancel"

            # 检查 hl feedback
            try:
                feedback = self._hl_feedback_queue.get_nowait()
                fb_type = feedback.get("feedback_type")
                if fb_type == VisionHlFeedback.CONFIRM.value:
                    # hl 回传了确认的 rect
                    boxes = feedback.get("data", {}).get("Boxes", [])
                    if boxes:
                        b = boxes[0]
                        return (b["Left"], b["Top"], b["Right"], b["Bottom"])
                    return draw_rect
                elif fb_type == VisionHlFeedback.STOP.value:
                    return "cancel"
                elif fb_type == VisionHlFeedback.CONTINUE.value:
                    return "shift"
            except queue.Empty:
                pass

            # 鼠标位置追踪
            cur_x, cur_y = pyautogui.position()
            if (cur_x, cur_y) != last_mouse_pos:
                last_mouse_pos = (cur_x, cur_y)

                if bboxes is not None:
                    new_rect = self._get_minbox(cur_x, cur_y, bboxes)
                else:
                    new_rect = None

                if new_rect != draw_rect:
                    draw_rect = new_rect
                    if draw_rect:
                        bx, by, bw, bh = draw_rect
                        r = Rect(bx, by, bx + bw, by + bh)
                        hl.draw_sync(r, "", "vision_pick")
                    else:
                        hl.mouse_move_sync(cur_x, cur_y)
                else:
                    hl.mouse_move_sync(cur_x, cur_y)

            time.sleep(0.05)

    # ------------------------------------------------------------------
    # VALIDATE 状态机
    # ------------------------------------------------------------------

    def _run_validate(self, data: dict) -> str | None:
        """验证视觉元素是否仍然存在于屏幕上"""
        import json
        from astronverse.vision_picker.core.core import IPickCore

        try:
            # data 是原始请求消息，cv 数据在 data["data"] 字段中（JSON 字符串）
            cv_data = data.get("data")
            if isinstance(cv_data, str):
                cv_data = json.loads(cv_data)
            match_box = IPickCore.match_imgs(cv_data, remote_addr="")
            if match_box:
                return "valid"
            return "invalid"
        except Exception as e:
            logger.error("VisionServer validate 失败: %s", e)
            return None

    # ------------------------------------------------------------------
    # DESIGNATE 状态机
    # ------------------------------------------------------------------

    def _run_designate(self, data: dict) -> str | None:
        """
        DESIGNATE 状态机（重拾锚点）：
        1. match_imgs 校验目标是否还在
        2. 通知 hl 画出 target 高亮并进入 designate 模式
        3. 请求 hl 截图 → 走锚点选取流程 → check_anchor → 返回结果
        """
        import json
        from astronverse.vision_picker.core.core import IPickCore

        hl = self.svc.ws_server.hl

        # data 是原始请求消息，cv 数据在 data["data"] 字段中（JSON 字符串）
        cv_data = data.get("data")
        if isinstance(cv_data, str):
            cv_data = json.loads(cv_data)

        # Step 1: 校验目标是否还在
        match_box = IPickCore.match_imgs(cv_data, remote_addr="")
        if not match_box:
            return None

        # Step 2: 通知 hl 进入 designate 模式并画出目标高亮
        from astronverse.picker import Rect
        target_rect_data = cv_data.get("pos", {})
        target_x = target_rect_data.get("self_x", 0)
        target_y = target_rect_data.get("self_y", 0)
        # match_box 格式: (left, top, right, bottom) 或 (x, y, w, h)
        if match_box and len(match_box) == 4:
            mb = match_box
            r = Rect(mb[0], mb[1], mb[0] + mb[2], mb[1] + mb[3])
            hl.draw_sync(r, "", "designate_target")
        hl.cv_start_sync("designate")

        # Step 3: 请求截图（hl 自动维护截图状态，无需 hide）
        hl.request_screenshot_sync()
        screenshot_data = self._wait_feedback(VisionHlFeedback.SCREENSHOT, timeout_sec=10)
        if screenshot_data is None:
            return None

        desktop_image = self._decode_screenshot(screenshot_data)
        if desktop_image is None:
            return None

        # 分割界面元素（ALT 模式）
        bboxes, partial_rect = self._detect_alt(desktop_image)
        hl.cv_start_sync("alt")

        # 鼠标追踪，等待用户选取锚点
        result = self._mouse_track_loop(hl, desktop_image, bboxes, *desktop_image.size)
        if result in ("cancel", "shift", None):
            hl.cv_initialize_sync("ESC")
            return "cancel"

        # check_anchor
        anchor_rect = result  # (left, top, right, bottom)
        pick_result = self._check_anchor(anchor_rect, desktop_image)
        hl.cv_initialize_sync("ESC")
        return pick_result

    # ------------------------------------------------------------------
    # 算法辅助方法
    # ------------------------------------------------------------------

    def _detect_alt(self, desktop_image):
        """ALT 模式：获取前景窗口区域并分割界面元素"""
        import sys
        import platform as _platform

        screen_w, screen_h = desktop_image.size

        # 获取前景窗口
        try:
            if sys.platform == "win32":
                from astronverse.vision_picker.core.core_win import RectHandler
            elif _platform.system() == "Linux":
                from astronverse.vision_picker.core.core_unix import RectHandler
            else:
                from astronverse.vision_picker.core.core_mac import RectHandler

            _, _, win_rect = RectHandler.get_foreground_window_rect()
            x = max(win_rect[0], 0)
            y = max(win_rect[1], 0)
            w = min(win_rect[2] - win_rect[0], screen_w)
            h = min(win_rect[3] - win_rect[1], screen_h)
        except Exception:
            x, y, w, h = 0, 0, screen_w, screen_h

        partial_rect = (x, y, w, h)
        partial_screenshot = desktop_image.crop((x, y, x + w, y + h))

        from astronverse.vision_picker.core.cv_picker import ImageDetector
        detector = ImageDetector(partial_screenshot)
        _, selected_boxes = detector.detect_objects("#00FF00", 1)

        # 坐标转换为全屏坐标
        bboxes = [
            (box[0] + x, box[1] + y, box[2], box[3])
            for box in selected_boxes
        ]
        bboxes = sorted(bboxes, key=lambda b: b[2] * b[3])
        return bboxes, partial_rect

    @staticmethod
    def _get_minbox(x_pos, y_pos, bboxes):
        """找到包含鼠标位置的最小 bbox"""
        min_bbox = None
        min_area = float("inf")
        if not x_pos or not y_pos:
            return min_bbox
        for bbox in bboxes:
            bx, by, bw, bh = bbox
            if bx <= x_pos < bx + bw and by <= y_pos < by + bh:
                area = bw * bh
                if area < min_area:
                    min_area = area
                    min_bbox = bbox
                    break
        return min_bbox

    def _check_target(self, target_rect_ltrb, desktop_image, bboxes, partial_rect):
        """
        校验目标元素唯一性，自动补充锚点
        target_rect_ltrb: (left, top, right, bottom)
        """
        import sys
        import platform as _platform

        if sys.platform == "win32":
            from astronverse.vision_picker.core.core_win import PickCore
        elif _platform.system() == "Linux":
            from astronverse.vision_picker.core.core_unix import PickCore
        else:
            from astronverse.vision_picker.core.core_mac import PickCore

        from astronverse.vision_picker.core.cv_match import AnchorMatch
        from astronverse.vision_picker.core.cv_picker import ImageDetector

        left, top, right, bottom = target_rect_ltrb
        target_img = desktop_image.crop((left, top, right, bottom))
        target_rect_xywh = (left, top, right - left, bottom - top)

        if not AnchorMatch.check_if_multiple_elements(desktop_image, target_img, match_similarity=0.95):
            # 元素不唯一，自动选取锚点
            if not bboxes:
                partial_screenshot = desktop_image.crop((
                    partial_rect[0], partial_rect[1],
                    partial_rect[0] + partial_rect[2],
                    partial_rect[1] + partial_rect[3],
                ))
                detector = ImageDetector(partial_screenshot)
                _, selected_boxes = detector.detect_objects("#00FF00", 1)
                bboxes = sorted(selected_boxes, key=lambda b: b[2] * b[3])

            for box in bboxes[::-1]:
                anchor_img = desktop_image.crop((box[0], box[1], box[0] + box[2], box[1] + box[3]))
                if AnchorMatch.check_if_multiple_elements(desktop_image, anchor_img, match_similarity=0.95):
                    return PickCore.json_res(target_img, target_rect_xywh, anchor_img, box, desktop_image)
            return None
        else:
            return PickCore.json_res(target_img, target_rect_xywh, None, None, desktop_image)

    def _check_anchor(self, anchor_rect_ltrb, desktop_image):
        """校验锚点元素唯一性"""
        import sys
        import platform as _platform

        if sys.platform == "win32":
            from astronverse.vision_picker.core.core_win import PickCore
        elif _platform.system() == "Linux":
            from astronverse.vision_picker.core.core_unix import PickCore
        else:
            from astronverse.vision_picker.core.core_mac import PickCore

        from astronverse.vision_picker.core.cv_match import AnchorMatch

        left, top, right, bottom = anchor_rect_ltrb
        anchor_img = desktop_image.crop((left, top, right, bottom))
        anchor_rect_xywh = (left, top, right - left, bottom - top)

        if not AnchorMatch.check_if_multiple_elements(desktop_image, anchor_img, match_similarity=0.95):
            logger.warning("VisionServer: 锚点不唯一，请重新选取")
            return None
        return PickCore.json_res(None, None, anchor_img, anchor_rect_xywh, desktop_image)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _wait_feedback(self, expected_type: VisionHlFeedback, timeout_sec: float = 10) -> dict | None:
        """阻塞等待指定类型的 hl feedback，超时返回 None"""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                feedback = self._hl_feedback_queue.get(timeout=0.1)
                if feedback.get("feedback_type") == expected_type.value:
                    return feedback.get("data", {})
                # 非预期类型放回队列
                self._hl_feedback_queue.put(feedback)
            except queue.Empty:
                pass
        return None

    @staticmethod
    def _decode_screenshot(screenshot_data: dict):
        """从 hl feedback data 中解码截图为 PIL Image"""
        import base64
        import io
        from PIL import Image

        b64 = screenshot_data.get("image") if isinstance(screenshot_data, dict) else None
        if not b64:
            logger.warning("VisionServer: 截图数据为空")
            return None
        try:
            img_bytes = base64.b64decode(b64)
            return Image.open(io.BytesIO(img_bytes))
        except Exception as e:
            logger.error("VisionServer: 截图解码失败: %s", e)
            return None
