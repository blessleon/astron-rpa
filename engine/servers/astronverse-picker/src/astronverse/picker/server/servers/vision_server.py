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

from astronverse.picker import VisionAction, VisionHlFeedback
from astronverse.picker.logger import logger
from astronverse.picker.utils.vision_adapter import AnchorMatch, ImageDetector, PickCore, RectHandler


class VisionServer:
    """视觉拾取服务 - 独立线程状态机"""

    def __init__(self, service_context):
        self.svc = service_context
        self._hl_feedback_queue: queue.Queue = queue.Queue()
        self._active_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._session_seq = 0
        self._current_session_id: str | None = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def _queue_size(self) -> str:
        try:
            return str(self._hl_feedback_queue.qsize())
        except Exception:
            return "unknown"

    @staticmethod
    def _feedback_type(data: dict) -> str:
        if not isinstance(data, dict):
            return type(data).__name__
        return str(data.get("feedback_type"))

    @staticmethod
    def _box_summary(box) -> str:
        if not isinstance(box, dict):
            return str(box)
        return (
            f"Left={box.get('Left')},Top={box.get('Top')},"
            f"Right={box.get('Right')},Bottom={box.get('Bottom')}"
        )

    def on_hl_feedback(self, data: dict) -> None:
        """由 WsServer 在 hl 消息到达时调用（异步上下文，线程安全）"""
        logger.info(
            f"VisionServer on_hl_feedback session={self._current_session_id} "
            f"type={self._feedback_type(data)} queue_before={self._queue_size()} payload={data}"
        )
        self._hl_feedback_queue.put(data)
        logger.info(
            f"VisionServer on_hl_feedback queued session={self._current_session_id} "
            f"type={self._feedback_type(data)} queue_after={self._queue_size()}"
        )

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
        # logger.info(
        #     f"VisionServer _start_session enter action={action.value} "
        #     f"active_alive={bool(self._active_thread and self._active_thread.is_alive())} "
        #     f"queue={self._queue_size()} "
        #     f"sign_keys={list(getattr(sign, 'map', sign).keys()) if hasattr(sign, 'map') else 'unknown'}"
        # )
        with self._lock:
            # logger.info(f"VisionServer _start_session lock_acquired action={action.value}")
            if self._active_thread and self._active_thread.is_alive():
                logger.warning(
                    f"VisionServer _start_session skipped action={action.value} "
                    f"reason=active_thread_running thread={self._active_thread.name}"
                )
                return
            # 清空旧 feedback
            cleared = 0
            while not self._hl_feedback_queue.empty():
                try:
                    self._hl_feedback_queue.get_nowait()
                    cleared += 1
                except queue.Empty:
                    break
            if cleared:
                logger.info(f"VisionServer _start_session cleared_feedback action={action.value} cleared={cleared}")

            data = sign[action.value]
            if data is None:
                # 防御：并发窗口或异常请求可能导致 payload 为空，避免启动空线程并给调用方明确结果。
                logger.warning(
                    f"VisionServer _start_session skipped action={action.value} "
                    f"reason=empty_payload sign_has_key={action.value in sign}"
                )
                if action.value in sign:
                    del sign[action.value]
                    sign[f"{action.value}_RES"] = self._error("invalid_payload")
                return
            self._session_seq += 1
            session_id = f"{action.value}-{self._session_seq}"
            self._current_session_id = session_id
            self._active_thread = threading.Thread(
                target=self._run_session,
                args=(action, data, sign, session_id),
                daemon=True,
                name=f"vision-{session_id}",
            )
            logger.info(
                f"VisionServer _start_session thread_start action={action.value} "
                f"session={session_id} thread={self._active_thread.name} "
                f"data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
            )
            self._active_thread.start()

    def _run_session(self, action: VisionAction, data: dict, sign: dict, session_id: str) -> None:
        """状态机主入口（在独立线程中运行）"""
        result_key = f"{action.value}_RES"
        result = None
        logger.info(
            f"VisionServer _run_session start session={session_id} action={action.value} "
            f"thread={threading.current_thread().name} queue={self._queue_size()}"
        )
        try:
            if action == VisionAction.START:
                result = self._run_start()
            elif action == VisionAction.VALIDATE:
                result = self._run_validate(data)
            elif action == VisionAction.DESIGNATE:
                result = self._run_designate(data)
        except Exception as e:
            logger.error(
                f"VisionServer _run_session exception session={session_id} action={action.value} "
                f"err={e} {traceback.format_exc()}"
            )
            result = self._error("internal_error")
        finally:
            logger.info(
                f"VisionServer _run_session finish session={session_id} action={action.value} result={result}"
            )
            del sign[action.value]
            sign[result_key] = result
            if self._current_session_id == session_id:
                self._current_session_id = None

    @staticmethod
    def _success(data: str | None = None) -> dict:
        return {"status": "success", "data": data}

    @staticmethod
    def _error(code: str) -> dict:
        return {"status": "error", "code": code}

    @staticmethod
    def _cancel(code: str = "cancel") -> dict:
        return {"status": "cancel", "code": code}

    @staticmethod
    def _has_signal(event_core, signal: str) -> bool:
        if signal == "esc":
            return event_core.is_cancel()
        if signal == "alt":
            return event_core.is_alt_pressed()
        if signal == "ctrl":
            return event_core.is_ctrl_pressed()
        if signal == "shift":
            return event_core.is_shift_pressed()
        return False

    # ------------------------------------------------------------------
    # START 状态机
    # ------------------------------------------------------------------

    def _run_start(self) -> dict:
        hl = self.svc.ws_server.hl
        event_core = self.svc.event_core
        logger.info(f"VisionServer _run_start begin session={self._current_session_id}")
        hl.start_sync("vision")
        logger.info(f"VisionServer _run_start hl.start_sync done session={self._current_session_id}")
        event_core.start()
        logger.info(f"VisionServer _run_start event_core.start done session={self._current_session_id}")

        # 需求1：全程鼠标追踪
        mouse_stop = threading.Event()

        def mouse_track_worker():
            last_pos = None
            while not mouse_stop.is_set():
                cur_x, cur_y = pyautogui.position()
                if (cur_x, cur_y) != last_pos:
                    last_pos = (cur_x, cur_y)
                    hl.mouse_move_sync(cur_x, cur_y)
                time.sleep(0.05)

        threading.Thread(target=mouse_track_worker, daemon=True).start()

        try:
            start_time = time.time()
            timeout = 60 * 3
            current_mode = None
            last_signal_log = 0.0

            while True:
                if time.time() - start_time > timeout:
                    logger.warning(
                        f"VisionServer _run_start timeout session={self._current_session_id} "
                        f"elapsed={time.time() - start_time:.3f}"
                    )
                    hl.hide_sync()
                    return self._error("timeout")

                if event_core.is_cancel():
                    logger.info(f"VisionServer _run_start cancel_detected session={self._current_session_id}")
                    hl.hide_sync()
                    return self._cancel()

                now = time.time()
                if now - last_signal_log > 1:
                    logger.info(
                        f"VisionServer _run_start heartbeat session={self._current_session_id} "
                        f"mode={current_mode} ctrl={event_core.is_ctrl_pressed()} "
                        f"alt={event_core.is_alt_pressed()} shift={event_core.is_shift_pressed()} "
                        f"cancel={event_core.is_cancel()} queue={self._queue_size()}"
                    )
                    last_signal_log = now

                if current_mode is None and self._has_signal(event_core, "shift"):
                    logger.info(f"VisionServer _run_start shift_enter session={self._current_session_id}")
                    hl.cv_initialize_sync("shift")
                    current_mode = "shift"
                    continue

                if current_mode == "shift" and not self._has_signal(event_core, "shift"):
                    logger.info(f"VisionServer _run_start shift_release session={self._current_session_id}")
                    current_mode = None

                if current_mode is None and self._has_signal(event_core, "alt"):
                    current_mode = "alt"
                    logger.info(
                        f"VisionServer _run_start alt_enter session={self._current_session_id} queue={self._queue_size()}"
                    )
                    hl.cv_shortcutkey_sync("alt")
                    logger.info(f"VisionServer _run_start alt_shortcut_sent session={self._current_session_id}")
                    screenshot_data = self._wait_feedback(VisionHlFeedback.SCREENSHOT, timeout_sec=10)
                    if screenshot_data is None:
                        logger.warning(
                            f"VisionServer _run_start alt_wait_screenshot_timeout session={self._current_session_id}"
                        )
                        current_mode = None
                        continue
                    desktop_image = self._decode_screenshot(screenshot_data)
                    if desktop_image is None:
                        logger.warning(
                            f"VisionServer _run_start alt_decode_screenshot_failed session={self._current_session_id}"
                        )
                        current_mode = None
                        continue
                    screen_w, screen_h = desktop_image.size
                    logger.info(
                        f"VisionServer _run_start alt_screenshot_ready session={self._current_session_id} "
                        f"size={screen_w}x{screen_h}"
                    )
                    bboxes, partial_rect = self._detect_alt(desktop_image)
                    logger.info(
                        f"VisionServer _run_start alt_detect_done session={self._current_session_id} "
                        f"bbox_count={len(bboxes) if bboxes else 0} partial_rect={partial_rect}"
                    )
                    result = self._mouse_track_loop(hl, bboxes, screen_w, screen_h)
                    logger.info(
                        f"VisionServer _run_start alt_track_result session={self._current_session_id} result={result}"
                    )
                    current_mode = None
                    if result == "timeout":
                        hl.hide_sync()
                        return self._error("timeout")
                    if result == "cancel":
                        hl.hide_sync()
                        return self._cancel()
                    if result == "shift":
                        hl.cv_initialize_sync("shift")
                        continue
                    if result is not None:
                        pick_result = self._check_target(result, desktop_image, bboxes, partial_rect)
                        if pick_result:
                            hl.hide_sync()
                            return self._success(pick_result)
                        continue

                if current_mode is None and self._has_signal(event_core, "ctrl"):
                    logger.info(
                        f"VisionServer _run_start ctrl_enter session={self._current_session_id} queue={self._queue_size()}"
                    )
                    current_mode = "ctrl"
                    hl.cv_shortcutkey_sync("ctrl")
                    logger.info(f"VisionServer _run_start ctrl_shortcut_sent session={self._current_session_id}")
                    confirm_result = self._wait_ctrl_confirm(timeout_sec=timeout)
                    logger.info(
                        f"VisionServer _run_start ctrl_confirm_result session={self._current_session_id} "
                        f"result={confirm_result}"
                    )
                    current_mode = None
                    if confirm_result == "timeout":
                        hl.hide_sync()
                        return self._error("timeout")
                    if confirm_result == "cancel":
                        hl.hide_sync()
                        return self._cancel()
                    box = confirm_result[0]
                    target_rect_ltrb = (box["Left"], box["Top"], box["Right"], box["Bottom"])
                    l, t, r, b = box["Left"], box["Top"], box["Right"], box["Bottom"]
                    logger.info(
                        f"VisionServer _run_start ctrl_box session={self._current_session_id} "
                        f"box={self._box_summary(box)} width={r - l} height={b - t}"
                    )
                    screenshot_started = time.time()
                    desktop_image = pyautogui.screenshot()
                    logger.info(
                        f"VisionServer _run_start ctrl_capture_done session={self._current_session_id} "
                        f"elapsed={time.time() - screenshot_started:.3f} "
                        f"size={getattr(desktop_image, 'width', None)}x{getattr(desktop_image, 'height', None)}"
                    )
                    logger.info(f"VisionServer _run_start ctrl_check_target_begin session={self._current_session_id}")
                    check_target_started = time.time()
                    # 与原 vision-picker 行为对齐：
                    # ctrl 模式确认后也需要做目标唯一性校验，不唯一时自动补锚点。
                    pick_result = self._check_target(
                        target_rect_ltrb=target_rect_ltrb,
                        desktop_image=desktop_image,
                        bboxes=None,
                        partial_rect=(0, 0, desktop_image.width, desktop_image.height),
                    )
                    logger.info(
                        f"VisionServer _run_start ctrl_check_target_done session={self._current_session_id} "
                        f"elapsed={time.time() - check_target_started:.3f} has_result={bool(pick_result)}"
                    )
                    hl.hide_sync()
                    logger.info(f"VisionServer _run_start ctrl_hide_done session={self._current_session_id}")
                    if pick_result:
                        logger.info(f"VisionServer _run_start ctrl_success session={self._current_session_id}")
                        return self._success(pick_result)
                    logger.warning(
                        f"VisionServer _run_start ctrl_target_not_found session={self._current_session_id}"
                    )
                    return self._error("target_not_found")

                time.sleep(0.05)
        finally:
            logger.info(f"VisionServer _run_start finally session={self._current_session_id}")
            mouse_stop.set()
            event_core.close()

    def _mouse_track_loop(self, hl, bboxes, screen_w, screen_h):
        """
        鼠标追踪循环：实时发送鼠标位置和命中 rect 给 hl
        返回：
            - tuple (left, top, right, bottom)：用户确认的目标 rect
            - "cancel"：ESC
            - "shift"：Shift 重置
            - None：stop 信号
        """
        from astronverse.picker import Rect
        event_core = self.svc.event_core

        last_mouse_pos = None
        draw_rect = None
        start_time = time.time()
        timeout = 60 * 3

        while True:
            if time.time() - start_time > timeout:
                logger.warning(f"VisionServer _mouse_track_loop timeout session={self._current_session_id}")
                return "timeout"

            if event_core.is_cancel():
                logger.info(f"VisionServer _mouse_track_loop cancel session={self._current_session_id}")
                return "cancel"

            if event_core.is_shift_pressed():
                logger.info(f"VisionServer _mouse_track_loop shift session={self._current_session_id}")
                return "shift"

            # 监听点击：命中候选框时，主动把命中框推送给 hl（对齐 designate 的点击命中行为）
            left_clicked = event_core.is_left_click()
            if left_clicked:
                event_core.reset_left_click_flag()
            if left_clicked and bboxes:
                cx, cy = pyautogui.position()
                hit_box = self._get_minbox(cx, cy, bboxes)
                logger.info(
                    f"VisionServer _mouse_track_loop click session={self._current_session_id} "
                    f"mouse=({cx},{cy}) hit={hit_box}"
                )
                if hit_box is not None:
                    bx, by, bw, bh = hit_box
                    draw_rect = hit_box
                    hl.draw_sync(Rect(bx, by, bx + bw, by + bh), "", "vision_pick")

            # 检查 hl feedback
            try:
                feedback = self._hl_feedback_queue.get_nowait()
                fb_type = feedback.get("feedback_type")
                if fb_type == VisionHlFeedback.CONFIRM.value:
                    # hl 回传了确认的 rect
                    boxes = feedback.get("data", {}).get("Boxes", [])
                    logger.info(
                        f"VisionServer _mouse_track_loop confirm session={self._current_session_id} boxes={boxes}"
                    )
                    if boxes:
                        b = boxes[0]
                        return (b["Left"], b["Top"], b["Right"], b["Bottom"])
                    return draw_rect
                elif fb_type == VisionHlFeedback.CONTINUE.value:
                    logger.info(f"VisionServer _mouse_track_loop continue session={self._current_session_id}")
                    continue
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
                    logger.info(
                        f"VisionServer _mouse_track_loop rect_change session={self._current_session_id} "
                        f"mouse=({cur_x},{cur_y}) rect={draw_rect}"
                    )
                    if draw_rect:
                        bx, by, bw, bh = draw_rect
                        r = Rect(bx, by, bx + bw, by + bh)
                        hl.draw_sync(r, "", "vision_pick")
                    else:
                        hl.mouse_move_sync(cur_x, cur_y)
                else:
                    hl.mouse_move_sync(cur_x, cur_y)

            time.sleep(0.05)

    def _designate_track_loop(self, hl, bboxes, target_rect=None):
        """
        designate 专用鼠标追踪循环：统一发送 designate_pick 消息
        - ESC 键：主动 hide 并取消拾取
        - 鼠标移动时发送 mouse_move 事件 + anchor_rect（若命中）
        - 鼠标左键点击时，若命中候选锚点 rect，发送 click_confirm 事件
        - 收到 hl CONFIRM 后直接从 data 中提取锚点 rect 返回
        返回：
            - tuple (left, top, right, bottom)：hl confirm 回传的锚点 rect
            - "cancel"：ESC / STOP
            - "shift"：CONTINUE
            - None：CONFIRM 数据异常
        """
        from astronverse.picker import Rect
        event_core = self.svc.event_core

        last_mouse_pos = None
        last_anchor_rect = None
        start_time = time.time()
        timeout = 60 * 3

        try:
            while True:
                if time.time() - start_time > timeout:
                    logger.warning(
                        f"VisionServer _designate_track_loop timeout session={self._current_session_id}"
                    )
                    hl.hide_sync()
                    return "timeout"

                # ── 检查 ESC ─────────────────────────────────────────────
                if event_core.is_cancel():
                    logger.info(f"VisionServer _designate_track_loop cancel session={self._current_session_id}")
                    hl.hide_sync()
                    return "cancel"

                # ── 检查点击：命中候选锚点则发送 click_confirm ────────────
                left_clicked = event_core.is_left_click()
                if left_clicked:
                    event_core.reset_left_click_flag()
                if left_clicked and bboxes:
                    cx, cy = pyautogui.position()
                    hit_box = self._get_minbox(cx, cy, bboxes)
                    logger.info(
                        f"VisionServer _designate_track_loop click session={self._current_session_id} "
                        f"mouse=({cx},{cy}) hit={hit_box}"
                    )
                    if hit_box is not None:
                        bx, by, bw, bh = hit_box
                        anchor_rect_obj = Rect(bx, by, bx + bw, by + bh)
                        hl.designate_pick_sync(
                            target_rect=target_rect,
                            anchor_rect=anchor_rect_obj,
                            event="click_confirm",
                        )

                # ── 检查 hl feedback ──────────────────────────────────────
                try:
                    feedback = self._hl_feedback_queue.get_nowait()
                    fb_type = feedback.get("feedback_type")
                    if fb_type == VisionHlFeedback.CONFIRM.value:
                        boxes = feedback.get("data", {}).get("Boxes", [])
                        logger.info(
                            f"VisionServer _designate_track_loop confirm session={self._current_session_id} boxes={boxes}"
                        )
                        data = boxes[0] if isinstance(boxes, list) and boxes else boxes
                        try:
                            return (
                                data["Left"],
                                data["Top"],
                                data["Right"],
                                data["Bottom"],
                            )
                        except KeyError:
                            logger.error(f"VisionServer: CONFIRM data 缺少 rect 字段: {data}")
                            return None
                    elif fb_type == VisionHlFeedback.CONTINUE.value:
                        logger.info(
                            f"VisionServer _designate_track_loop continue session={self._current_session_id}"
                        )
                        continue
                except queue.Empty:
                    pass

                # ── 鼠标移动追踪 ──────────────────────────────────────────
                cur_x, cur_y = pyautogui.position()
                if (cur_x, cur_y) != last_mouse_pos:
                    last_mouse_pos = (cur_x, cur_y)
                    anchor_rect = self._get_minbox(cur_x, cur_y, bboxes) if bboxes is not None else None

                    if anchor_rect != last_anchor_rect:
                        last_anchor_rect = anchor_rect
                        logger.info(
                            f"VisionServer _designate_track_loop rect_change session={self._current_session_id} "
                            f"mouse=({cur_x},{cur_y}) rect={anchor_rect}"
                        )
                        if anchor_rect is not None:
                            bx, by, bw, bh = anchor_rect
                            anchor_rect_obj = Rect(bx, by, bx + bw, by + bh)
                            hl.designate_pick_sync(
                                target_rect=target_rect,
                                anchor_rect=anchor_rect_obj,
                                event="mouse_move",
                            )
                        else:
                            hl.designate_pick_sync(
                                target_rect=target_rect, anchor_rect=None, event="mouse_move"
                            )

                time.sleep(0.05)
        finally:
            event_core.reset_left_click_flag()

    # ------------------------------------------------------------------
    # VALIDATE 状态机
    # ------------------------------------------------------------------

    def _run_validate(self, data: dict) -> dict:
        """验证视觉元素是否仍然存在于屏幕上"""
        import json
        try:
            logger.info(f"VisionServer _run_validate begin session={self._current_session_id}")
            if not isinstance(data, dict):
                logger.warning(
                    f"VisionServer _run_validate invalid_data session={self._current_session_id} "
                    f"type={type(data).__name__} value={data}"
                )
                return self._error("validate_failed")
            # data 是原始请求消息，cv 数据在 data["data"] 字段中（JSON 字符串）
            cv_data = data.get("data")
            if cv_data is None:
                logger.warning(
                    f"VisionServer _run_validate empty_cv_data session={self._current_session_id} "
                    f"keys={list(data.keys())}"
                )
                return self._error("validate_failed")
            logger.info(
                f"VisionServer _run_validate raw_input session={self._current_session_id} "
                f"input_type={type(cv_data).__name__} input_preview={str(cv_data)[:500]}"
            )
            if isinstance(cv_data, str):
                cv_data = json.loads(cv_data)
            if not isinstance(cv_data, dict):
                logger.warning(
                    f"VisionServer _run_validate parsed_invalid session={self._current_session_id} "
                    f"type={type(cv_data).__name__}"
                )
                return self._error("validate_failed")
            logger.info(
                f"VisionServer _run_validate parsed_input session={self._current_session_id} "
                f"keys={list(cv_data.keys()) if isinstance(cv_data, dict) else type(cv_data).__name__} "
                f"type={cv_data.get('type') if isinstance(cv_data, dict) else None} "
                f"pos={cv_data.get('pos') if isinstance(cv_data, dict) else None} "
                f"sr={cv_data.get('sr') if isinstance(cv_data, dict) else None} "
                f"has_self_img={bool(cv_data.get('img', {}).get('self')) if isinstance(cv_data, dict) else None} "
                f"has_parent_img={bool(cv_data.get('img', {}).get('parent')) if isinstance(cv_data, dict) else None}"
            )
            match_box = PickCore.match_imgs(cv_data)
            logger.info(
                f"VisionServer _run_validate match_result session={self._current_session_id} "
                f"match_box={match_box}"
            )
            if match_box:
                # 对齐常规拾取校验：命中后向 hl 发送 validate 高亮并停留 3 秒。
                from astronverse.picker import Rect

                x, y, w, h = match_box
                rect = Rect(x, y, x + w, y + h)
                hl = self.svc.ws_server.hl
                hl.start_sync("validate")
                hl.draw_sync(rect, "", "validate")
                time.sleep(3)
                return self._success("校验成功")
            return self._error("validate_not_found")
        except Exception as e:
            logger.error(
                f"VisionServer _run_validate failed session={self._current_session_id} err={e} "
                f"{traceback.format_exc()}"
            )
            return self._error("validate_failed")

    # ------------------------------------------------------------------
    # DESIGNATE 状态机
    # ------------------------------------------------------------------

    def _run_designate(self, data: dict) -> dict:
        """
        DESIGNATE 状态机（重拾锚点）：
        1. match_imgs 校验目标是否还在
        2. 通知 hl 画出 target 高亮并进入 designate 模式
        3. 请求 hl 截图 → 走锚点选取流程 → check_anchor → 返回结果
        """
        import json
        hl = self.svc.ws_server.hl
        event_core = self.svc.event_core
        logger.info(f"VisionServer _run_designate begin session={self._current_session_id}")
        event_core.start()
        logger.info(f"VisionServer _run_designate event_core.start done session={self._current_session_id}")

        try:
            # data 是原始请求消息，cv 数据在 data["data"] 字段中（JSON 字符串）
            cv_data = data.get("data")
            if isinstance(cv_data, str):
                cv_data = json.loads(cv_data)
            logger.info(
                f"VisionServer _run_designate parsed_data session={self._current_session_id} "
                f"has_data={bool(cv_data)} keys={list(cv_data.keys()) if isinstance(cv_data, dict) else type(cv_data).__name__}"
            )

            # Step 1: 校验目标是否还在
            match_box = PickCore.match_imgs(cv_data)
            logger.info(
                f"VisionServer _run_designate match_result session={self._current_session_id} "
                f"match_box={match_box}"
            )
            if not match_box:
                return self._error("designate_target_not_found")

            # Step 2: 通知 hl 进入 designate 模式并发送目标 rect
            from astronverse.picker import Rect
            target_rect = None
            if match_box and len(match_box) == 4:
                mb = match_box
                target_rect = Rect(mb[0], mb[1], mb[0] + mb[2], mb[1] + mb[3])

            hl.cv_start_sync("designate")
            logger.info(
                f"VisionServer _run_designate cv_start_sent session={self._current_session_id} "
                f"target_rect={target_rect}"
            )

            # Step 3: 等待截图
            screenshot_data = self._wait_feedback(VisionHlFeedback.SCREENSHOT, timeout_sec=10)
            if screenshot_data is None:
                return self._error("timeout")
            logger.info(
                f"VisionServer _run_designate screenshot_feedback session={self._current_session_id} "
                f"keys={list(screenshot_data.keys()) if isinstance(screenshot_data, dict) else type(screenshot_data).__name__}"
            )

            desktop_image = self._decode_screenshot(screenshot_data)
            if desktop_image is None:
                return self._error("designate_anchor_not_found")
            logger.info(
                f"VisionServer _run_designate screenshot_decoded session={self._current_session_id} "
                f"size={desktop_image.width}x{desktop_image.height}"
            )

            # Step 4: 分割界面元素（ALT 模式）
            bboxes, partial_rect = self._detect_alt(desktop_image)
            logger.info(
                f"VisionServer _run_designate detect_done session={self._current_session_id} "
                f"bbox_count={len(bboxes) if bboxes else 0} partial_rect={partial_rect}"
            )

            # Step 5: 发送统一 designate_pick 消息（target_ready 事件）
            hl.designate_pick_sync(target_rect=target_rect, anchor_rect=None, event="target_ready")

            # Step 6: 鼠标追踪，等待用户选取锚点
            result = self._designate_track_loop(hl, bboxes, target_rect)
            logger.info(
                f"VisionServer _run_designate track_result session={self._current_session_id} result={result}"
            )
            if result == "timeout":
                hl.hide_sync()
                return self._error("timeout")
            if result == "cancel":
                hl.hide_sync()
                return self._cancel()
            if result is None:
                hl.hide_sync()
                return self._error("designate_anchor_not_found")

            # result 是 hl CONFIRM 回传的锚点 rect (left, top, right, bottom)，来源可信，直接传入校验
            anchor_rect_ltrb = result
            pick_result = self._check_anchor(anchor_rect_ltrb, desktop_image)
            logger.info(
                f"VisionServer _run_designate check_anchor session={self._current_session_id} "
                f"anchor_rect={anchor_rect_ltrb} has_result={bool(pick_result)}"
            )
            hl.hide_sync()
            if pick_result:
                return self._success(pick_result)
            return self._error("designate_anchor_not_found")
        finally:
            logger.info(f"VisionServer _run_designate finally session={self._current_session_id}")
            event_core.close()

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
            _, _, win_rect = RectHandler.get_foreground_window_rect()
            x = max(win_rect[0], 0)
            y = max(win_rect[1], 0)
            w = min(win_rect[2] - win_rect[0], screen_w)
            h = min(win_rect[3] - win_rect[1], screen_h)
        except Exception:
            x, y, w, h = 0, 0, screen_w, screen_h
        logger.info(
            f"VisionServer _detect_alt session={self._current_session_id} "
            f"screen=({screen_w},{screen_h}) partial_rect=({x},{y},{w},{h})"
        )

        partial_rect = (x, y, w, h)
        partial_screenshot = desktop_image.crop((x, y, x + w, y + h))

        detector = ImageDetector(partial_screenshot)
        _, selected_boxes = detector.detect_objects("#00FF00", 1)

        # 坐标转换为全屏坐标
        bboxes = [
            (box[0] + x, box[1] + y, box[2], box[3])
            for box in selected_boxes
        ]
        bboxes = sorted(bboxes, key=lambda b: b[2] * b[3])
        logger.info(
            f"VisionServer _detect_alt selected session={self._current_session_id} bbox_count={len(bboxes)}"
        )
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
    def _wait_ctrl_confirm(self, timeout_sec: float = 60 * 3):
        """
        ctrl 模式下等待 hl 回传 CONFIRM，
        期间监听 ESC 可随时取消
        返回：Boxes dict | "cancel"
        """
        deadline = time.time() + timeout_sec
        event_core = self.svc.event_core
        logger.info(
            f"VisionServer _wait_ctrl_confirm begin session={self._current_session_id} "
            f"timeout={timeout_sec} queue={self._queue_size()}"
        )
        while time.time() < deadline:
            if event_core.is_cancel():
                logger.info(f"VisionServer _wait_ctrl_confirm cancel session={self._current_session_id}")
                return "cancel"
            # 检查 hl feedback
            try:
                feedback = self._hl_feedback_queue.get(timeout=0.05)
                fb_type = feedback.get("feedback_type")
                logger.info(
                    f"VisionServer _wait_ctrl_confirm dequeued session={self._current_session_id} "
                    f"fb_type={fb_type} queue_after_get={self._queue_size()} payload={feedback}"
                )
                if fb_type == VisionHlFeedback.CONFIRM.value:
                    boxes = feedback.get("data", {}).get("Boxes", [])
                    logger.info(
                        f"VisionServer _wait_ctrl_confirm confirm session={self._current_session_id} boxes={boxes}"
                    )
                    if boxes:
                        logger.info(
                            f"VisionServer _wait_ctrl_confirm return session={self._current_session_id} boxes={boxes}"
                        )
                        return boxes  # 直接返回 Boxes 列表
                    logger.warning(
                        f"VisionServer _wait_ctrl_confirm empty_boxes session={self._current_session_id}"
                    )
                    return "cancel"
                # 非预期类型放回
                self._hl_feedback_queue.put(feedback)
                logger.info(
                    f"VisionServer _wait_ctrl_confirm requeue session={self._current_session_id} "
                    f"fb_type={fb_type} queue_after_put={self._queue_size()}"
                )
            except queue.Empty:
                pass

        logger.warning(
            f"VisionServer _wait_ctrl_confirm timeout session={self._current_session_id} queue={self._queue_size()}"
        )
        return "timeout"

    def _wait_feedback(self, expected_type: VisionHlFeedback, timeout_sec: float = 10) -> dict | None:
        """阻塞等待指定类型的 hl feedback，超时返回 None"""
        deadline = time.time() + timeout_sec
        logger.info(
            f"VisionServer _wait_feedback begin session={self._current_session_id} "
            f"expected={expected_type.value} timeout={timeout_sec} queue={self._queue_size()}"
        )
        while time.time() < deadline:
            try:
                feedback = self._hl_feedback_queue.get(timeout=0.1)
                logger.info(
                    f"VisionServer _wait_feedback dequeued session={self._current_session_id} "
                    f"expected={expected_type.value} actual={feedback.get('feedback_type')} "
                    f"queue_after_get={self._queue_size()}"
                )
                if feedback.get("feedback_type") == expected_type.value:
                    logger.info(
                        f"VisionServer _wait_feedback matched session={self._current_session_id} "
                        f"expected={expected_type.value}"
                    )
                    return feedback.get("data", {})
                # 非预期类型放回队列
                self._hl_feedback_queue.put(feedback)
                logger.info(
                    f"VisionServer _wait_feedback requeue session={self._current_session_id} "
                    f"expected={expected_type.value} actual={feedback.get('feedback_type')} "
                    f"queue_after_put={self._queue_size()}"
                )
            except queue.Empty:
                pass
        logger.warning(
            f"VisionServer _wait_feedback timeout session={self._current_session_id} "
            f"expected={expected_type.value} queue={self._queue_size()}"
        )
        return None

    @staticmethod
    def _decode_screenshot(screenshot_data: dict):
        """从 hl feedback data 中解码截图为 PIL Image"""
        import base64
        import io
        import re
        from PIL import Image

        b64 = screenshot_data.get("image") if isinstance(screenshot_data, dict) else None
        if not b64:
            logger.warning("VisionServer: 截图数据为空")
            return None
        try:
            if "," in b64 and "base64" in b64[:64]:
                b64 = b64.split(",", 1)[1]
            b64 = re.sub(r"\s+", "", b64)
            missing_padding = len(b64) % 4
            if missing_padding:
                b64 += "=" * (4 - missing_padding)
            img_bytes = base64.b64decode(b64)
            image = Image.open(io.BytesIO(img_bytes))
            logger.info(
                f"VisionServer _decode_screenshot success bytes={len(img_bytes)} "
                f"size={getattr(image, 'width', None)}x{getattr(image, 'height', None)} "
                f"mode={getattr(image, 'mode', None)}"
            )
            return image
        except Exception as e:
            logger.error(
                f"VisionServer: 截图解码失败: {e} "
                f"raw_prefix={str(screenshot_data)[:200]}"
            )
            return None
