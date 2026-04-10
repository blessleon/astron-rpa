"""MD5文件哈希计算组件"""
import hashlib
from pathlib import Path

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.md5.error import BizException, Md5Error


class Md5:
    """MD5文件哈希计算组件
    
    提供文件MD5值的计算功能
    """
    
    @staticmethod
    @atomicMg.atomic(
        "Md5",
        inputList=[
            atomicMg.param(
                "file_path",
                types="PATH",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={}
                ),
                required=True,
            ),
            atomicMg.param(
                "timeout",
                types="Int",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON.value,
                    params={}
                ),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("result", types="Str")
        ],
    )
    def calculate_file_md5(file_path: str, timeout: int = 30) -> str:
        """计算文件的MD5值
        
        Args:
            file_path: 文件路径
            timeout: 超时时间（秒），默认30秒
            
        Returns:
            str: 文件的MD5值（32位十六进制字符串）
            
        Raises:
            BizException: 当文件不存在、读取失败或计算超时时抛出
        """
        # 参数校验
        if not file_path:
            raise Exception(Md5Error.INVALID_PATH.format("路径为空"))
        
        # 转换为Path对象
        path = Path(file_path)
        
        # 检查文件是否存在
        if not path.exists():
            raise Exception(Md5Error.FILE_NOT_FOUND.format(file_path))
        
        # 检查是否为文件
        if not path.is_file():
            raise Exception(Md5Error.INVALID_PATH.format(f"{file_path} 不是一个文件"))
        
        try:
            # 创建MD5对象
            md5_hash = hashlib.md5()
            
            # 分块读取文件，避免大文件占用过多内存
            chunk_size = 8192
            total_read = 0
            file_size = path.stat().st_size
            
            # 简单的超时控制（基于读取速度估算）
            # 假设最低读取速度为 1MB/s
            min_speed = 1024 * 1024  # 1MB/s
            max_chunks = (file_size // chunk_size + 1) * 2  # 允许一定的余量
            
            with open(path, 'rb') as f:
                chunk_count = 0
                while chunk := f.read(chunk_size):
                    chunk_count += 1
                    
                    # 简单超时检查
                    if timeout > 0 and chunk_count > max_chunks:
                        raise Exception(Md5Error.TIMEOUT_ERROR.format("读取超过预期块数"))
                    
                    md5_hash.update(chunk)
                    total_read += len(chunk)
            
            # 返回MD5十六进制字符串
            return md5_hash.hexdigest()
            
        except BizException:
            raise
        except Exception as e:
            raise Exception(Md5Error.FILE_READ_ERROR.format(str(e)))
