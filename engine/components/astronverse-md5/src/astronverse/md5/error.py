from astronverse.baseline.error.error import BizException
from astronverse.baseline.i18n.i18n import _

BizException = BizException


class Md5Error:
    """MD5组件错误定义"""

    FILE_NOT_FOUND = "文件不存在: {}"
    FILE_READ_ERROR = "读取文件失败: {}"
    TIMEOUT_ERROR = "计算超时: {}"
    INVALID_PATH = "无效的文件路径: {}"

from astronverse.baseline.error.error import *
from astronverse.baseline.i18n.i18n import _

BizException = BizException


class Md5Error:
    """MD5组件错误定义"""

    FILE_NOT_FOUND = "文件不存在: {}"
    FILE_READ_ERROR = "读取文件失败: {}"
    TIMEOUT_ERROR = "计算超时: {}"
    INVALID_PATH = "无效的文件路径: {}"
