"""元数据生成脚本"""
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.config import config
from astronverse.baseline.config.config import load_config
from astronverse.md5.md5 import Md5


def get_version():
    """从 pyproject.toml 获取版本号"""
    pyproject_data = load_config("pyproject.toml")
    return pyproject_data["project"]["version"]


if __name__ == "__main__":
    config.set_config_file("config.yaml")
    atomicMg.register(Md5, version=get_version())
    atomicMg.meta()
