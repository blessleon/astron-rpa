import json

from astronverse.picker import VisionAction
from astronverse.picker.server import RequestMessage, ResponseMessage, ResponseKey


class VisionHandler:
    """
    视觉拾取 WebSocket 消息处理器

    遵循 send_sign 阻塞等待模式（与 NormalPickerHandler 一致）：
    前端发送 START/VALIDATE/DESIGNATE 后阻塞等待，
    VisionServer 完成状态机后通过 SyncMap 写入结果，
    handler 收到结果后回包给前端。
    """

    def __init__(self, svc):
        self.svc = svc
        self.ws_server = None
        self._ws = None  # 当前请求的 ws 连接，dispatch 时注入

    async def dispatch(self, ws_server, ws, data: dict):
        """处理消息，统一捕获异常并回复错误"""
        self.ws_server = ws_server
        self._ws = ws
        request = RequestMessage(**data)
        try:
            match request.vision_action:
                case VisionAction.START:
                    await self._handle_start(request)
                case VisionAction.VALIDATE:
                    await self._handle_validate(request)
                case VisionAction.DESIGNATE:
                    await self._handle_designate(request)
                case _:
                    await self._send_response(ResponseKey.ERROR, error="未知的 vision_action")
        except Exception as e:
            import traceback
            from astronverse.picker.logger import logger
            logger.error("VisionHandler 异常: %s\n%s", e, traceback.format_exc())
            await self._send_response(ResponseKey.ERROR, error=str(e))

    async def _handle_start(self, request: RequestMessage):
        """开始视觉拾取：阻塞等待 VisionServer 完成状态机"""
        try:
            result = await self.svc.send_sign(VisionAction.START.value, request.model_dump(mode="json"))
            if result == "cancel":
                await self._send_response(ResponseKey.CANCEL, error="")
            elif result:
                await self._send_response(ResponseKey.SUCCESS, data=result)
            else:
                await self._send_response(ResponseKey.ERROR, error="视觉拾取失败")
        finally:
            await self.ws_server.hl.hide()

    async def _handle_validate(self, request: RequestMessage):
        """验证视觉元素：阻塞等待 VisionServer 完成验证"""
        try:
            result = await self.svc.send_sign(VisionAction.VALIDATE.value, request.model_dump(mode="json"))
            if result == "cancel":
                await self._send_response(ResponseKey.CANCEL, error="")
            elif result:
                await self._send_response(ResponseKey.SUCCESS, data=result)
            else:
                await self._send_response(ResponseKey.ERROR, error="视觉验证失败")
        finally:
            await self.ws_server.hl.hide()

    async def _handle_designate(self, request: RequestMessage):
        """指定视觉元素（重拾锚点）：阻塞等待 VisionServer 完成"""
        try:
            result = await self.svc.send_sign(VisionAction.DESIGNATE.value, request.model_dump(mode="json"))
            if result == "cancel":
                await self._send_response(ResponseKey.CANCEL, error="")
            elif result:
                await self._send_response(ResponseKey.SUCCESS, data=result)
            else:
                await self._send_response(ResponseKey.ERROR, error="视觉指定失败")
        finally:
            await self.ws_server.hl.hide()

    async def _send_response(self, key: ResponseKey, data=None, error: str = ""):
        if data is None:
            data = ""
        if key == ResponseKey.SUCCESS:
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False)
            elif not isinstance(data, str):
                data = str(data)
        await self._ws.send(ResponseMessage.create_response(key, data=data, err_msg=error).model_dump_json())
