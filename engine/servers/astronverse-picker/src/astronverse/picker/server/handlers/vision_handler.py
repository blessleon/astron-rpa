import json

from astronverse.picker import VisionAction


class VisionHandler:
    """
    视觉拾取 WebSocket 消息处理器

    使用原 vision-picker 消息格式：
    - 请求：{pick_sign: "START/VALIDATE/DESIGNATE", pick_type: "ELEMENT", data: "..."}
    - 响应：{err_msg: "", data: "", key: "success/error/cancel"}

    遵循 send_sign 阻塞等待模式：
    前端发送 START/VALIDATE/DESIGNATE 后阻塞等待，
    VisionServer 完成状态机后通过 SyncMap 写入结果，
    handler 收到结果后回包给前端。
    """

    def __init__(self, svc):
        self.svc = svc
        self.ws_server = None
        self._ws = None  # 当前请求的 ws 连接，dispatch 时注入

    async def dispatch(self, ws_server, ws, data: dict):
        """处理消息，统一捕获异常并回复错误 - 使用原 vision-picker 格式"""
        self.ws_server = ws_server
        self._ws = ws

        # 直接使用原格式字段 pick_sign
        pick_sign = data.get("pick_sign")

        try:
            if pick_sign == "START":
                await self._handle_start(data)
            elif pick_sign == "VALIDATE":
                await self._handle_validate(data)
            elif pick_sign == "DESIGNATE":
                await self._handle_designate(data)
            else:
                await self._send_response("error", error="未知的 pick_sign")
        except Exception as e:
            import traceback
            from astronverse.picker.logger import logger
            logger.error("VisionHandler 异常: %s\n%s", e, traceback.format_exc())
            await self._send_response("error", error=str(e))

    async def _handle_start(self, request_data: dict):
        """开始视觉拾取：阻塞等待 VisionServer 完成状态机"""
        try:
            result = await self.svc.send_sign(VisionAction.START.value, request_data)
            if result == "cancel":
                await self._send_response("cancel", error="")
            elif result:
                await self._send_response("success", data=result)
            else:
                await self._send_response("error", error="视觉拾取失败")
        finally:
            await self.ws_server.hl.hide()

    async def _handle_validate(self, request_data: dict):
        """验证视觉元素：阻塞等待 VisionServer 完成验证"""
        try:
            result = await self.svc.send_sign(VisionAction.VALIDATE.value, request_data)
            if result == "cancel":
                await self._send_response("cancel", error="")
            elif result:
                await self._send_response("success", data=result)
            else:
                await self._send_response("error", error="视觉验证失败")
        finally:
            await self.ws_server.hl.hide()

    async def _handle_designate(self, request_data: dict):
        """指定视觉元素（重拾锚点）：阻塞等待 VisionServer 完成"""
        try:
            result = await self.svc.send_sign(VisionAction.DESIGNATE.value, request_data)
            if result == "cancel":
                await self._send_response("cancel", error="")
            elif result:
                await self._send_response("success", data=result)
            else:
                await self._send_response("error", error="视觉指定失败")
        finally:
            await self.ws_server.hl.hide()

    async def _send_response(self, key: str, data=None, error: str = ""):
        """返回原 vision-picker 格式响应"""
        if data is None:
            data = ""
        if key == "success":
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False)
            elif not isinstance(data, str):
                data = str(data)

        response = {
            "err_msg": error if error else "",
            "data": data,
            "key": key  # "success", "error", "cancel"
        }
        await self._ws.send(json.dumps(response, ensure_ascii=False))
