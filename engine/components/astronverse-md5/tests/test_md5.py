"""MD5组件测试"""
import os
import tempfile

import pytest
from astronverse.actionlib import BizException
from astronverse.md5 import Md5


class TestMd5:
    """MD5组件测试类"""
    
    def test_calculate_md5_simple(self):
        """测试计算简单文件的MD5"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello, World!")
            temp_path = f.name
        
        try:
            # 计算MD5
            result = Md5.calculate_file_md5(temp_path)
            
            # 验证结果（"Hello, World!" 的MD5值）
            expected = "65a8e27d8879283831b664bd8b7f0ad4"
            assert result == expected, f"Expected {expected}, got {result}"
        finally:
            # 清理临时文件
            os.unlink(temp_path)
    
    def test_calculate_md5_empty_file(self):
        """测试计算空文件的MD5"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_path = f.name
        
        try:
            result = Md5.calculate_file_md5(temp_path)
            
            # 空文件的MD5值
            expected = "d41d8cd98f00b204e9800998ecf8427e"
            assert result == expected
        finally:
            os.unlink(temp_path)
    
    def test_calculate_md5_large_file(self):
        """测试计算大文件的MD5"""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            # 写入1MB数据
            data = b'A' * (1024 * 1024)
            f.write(data)
            temp_path = f.name
        
        try:
            result = Md5.calculate_file_md5(temp_path, timeout=60)
            
            # 验证结果是32位十六进制字符串
            assert len(result) == 32
            assert all(c in '0123456789abcdef' for c in result)
        finally:
            os.unlink(temp_path)
    
    def test_file_not_found(self):
        """测试文件不存在的情况"""
        with pytest.raises(BizException) as exc_info:
            Md5.calculate_file_md5("non_existent_file.txt")
        
        assert "文件不存在" in str(exc_info.value)
    
    def test_invalid_path_empty(self):
        """测试空路径"""
        with pytest.raises(BizException) as exc_info:
            Md5.calculate_file_md5("")
        
        assert "无效的文件路径" in str(exc_info.value)
    
    def test_path_is_directory(self):
        """测试路径是目录而非文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(BizException) as exc_info:
                Md5.calculate_file_md5(temp_dir)
            
            assert "不是一个文件" in str(exc_info.value)
    
    def test_default_timeout(self):
        """测试默认超时参数"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test")
            temp_path = f.name
        
        try:
            # 不传timeout参数，使用默认值
            result = Md5.calculate_file_md5(temp_path)
            assert len(result) == 32
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
