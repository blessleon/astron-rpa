# astronverse-md5

MD5文件哈希计算组件，用于计算文件的MD5值。

## 功能

- 计算指定文件的MD5哈希值
- 支持大文件分块计算（避免内存溢出）
- 支持超时控制
- 返回32位十六进制MD5字符串

## 使用方法

### calculate_file_md5

计算文件的MD5值。

**参数：**
- `file_path` (str): 文件路径
- `timeout` (int, 可选): 超时时间（秒），默认30秒

**返回：**
- `str`: 文件的MD5值（32位十六进制字符串）

**示例：**
```python
from astronverse.md5 import Md5

# 计算文件MD5
md5_value = Md5.calculate_file_md5("C:/path/to/file.txt", timeout=60)
print(f"MD5: {md5_value}")
```

## 错误处理

组件在以下情况会抛出 `BizException`：
- 文件不存在
- 路径无效（如路径为空或不是文件）
- 文件读取失败
- 计算超时

## 版本

1.0.0
