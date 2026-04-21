import base64
import io

import pyautogui
from PIL import Image

from astronverse.vision.core import CvCore
from astronverse.vision.cv_match import AnchorMatch
from astronverse.vision.cv_picker import ImageDetector


class RectHandler:
    @staticmethod
    def get_foreground_window_rect():
        width, height = pyautogui.size()
        return None, "Unknown", (0, 0, width, height)


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

