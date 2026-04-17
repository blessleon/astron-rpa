import os
import platform
import sys
from importlib.util import find_spec

from astronverse.scheduler import ComponentType
from astronverse.scheduler.utils.subprocess import SubPopen


class Picker:
    def __init__(self, svc):
        self.svc = svc
        self.highlighter = None  # 画框
        self.app_picker = None  # 拾取（已集成 cv 识别）
        # self.app_picker_core = None  # 拾取
        self.start = False

    def set_start(self, start):
        self.start = start

    def init(self):
        python_executable = self.svc.config.python_core

        # 1. 服务声明
        if sys.platform == "win32" and platform.release() != "7":
            highlighter_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "win",
                "RPAHighlighter",
                "ConsoleApp1.exe",
            )
            self.highlighter = SubPopen(name="highlighter", cmd=[highlighter_path])
            self.app_picker = SubPopen(name="picker", cmd=[python_executable, "-m", "astronverse.picker"])
        elif sys.platform == "win32" and platform.release() == "7":
            highlighter_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "win",
                "RPAHighlighter",
                "cv_match_application_4.0.py",
            )
            self.highlighter = SubPopen(
                name="rpa_highlighter",
                cmd=[
                    python_executable,
                    highlighter_path,
                    "{}".format(self.svc.rpa_hl_port),
                ],
            )
            self.app_picker = SubPopen(name="picker", cmd=[python_executable, "-m", "astronverse.picker"])
        elif sys.platform == "darwin":
            highlighter_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "mac",
                "RPAHighlighter",
                "cv_match_application_4.0.py",
            )
            if find_spec("PyQt5") is not None:
                self.highlighter = SubPopen(
                    name="rpa_highlighter",
                    cmd=[
                        python_executable,
                        highlighter_path,
                        "{}".format(self.svc.rpa_hl_port),
                    ],
                )
            self.app_picker = SubPopen(name="picker", cmd=[python_executable, "-m", "astronverse.picker"])
        else:
            highlighter_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "linux",
                "RPAHighlighter",
                "cv_match_application_4.0.py",
            )
            self.highlighter = SubPopen(
                name="rpa_highlighter",
                cmd=[
                    python_executable,
                    highlighter_path,
                    "{}".format(self.svc.rpa_hl_port),
                ],
            )
            self.app_picker = SubPopen(name="picker", cmd=[python_executable, "-m", "astronverse.picker_linux"])

        # 2. 服务配置
        # picker 已集成 cv 功能，通过 /cv_picker 路径路由访问
        if self.app_picker:
            picker_port = self.svc.get_validate_port(ComponentType.PICKER)
            self.app_picker.set_param("port", picker_port)
            self.app_picker.set_param("route_port", self.svc.rpa_route_port)
            self.app_picker.set_param("highlight_socket_port", self.svc.rpa_hl_port)

            # cv_picker 已集成到 picker 中，注册到同一端口
            self.svc.port_dict[ComponentType.CV_PICKER.name.lower()] = picker_port
