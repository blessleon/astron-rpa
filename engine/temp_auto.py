import os
import pathlib

# components 目录路径
components_dir = pathlib.Path(__file__).parent / 'components'

# 要删除的文件名列表
files_to_delete = ['meta.json', 'tree.json']

# 统计信息
deleted_count = 0
skipped_count = 0

print(f"开始扫描目录: {components_dir}")
print(f"目标文件: {', '.join(files_to_delete)}\n")

# 遍历 components 下的所有子目录
if components_dir.exists() and components_dir.is_dir():
    for subdir in components_dir.iterdir():
        if subdir.is_dir():
            print(f"检查目录: {subdir.name}")
            
            # 在每个子目录中查找并删除目标文件
            for filename in files_to_delete:
                file_path = subdir / filename
                
                if file_path.exists():
                    try:
                        file_path.unlink()
                        print(f"  ✓ 已删除: {filename}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"  ✗ 删除失败 {filename}: {e}")
                        skipped_count += 1
                else:
                    print(f"  - 未找到: {filename}")
else:
    print(f"错误: components 目录不存在: {components_dir}")

print(f"\n完成！")
print(f"成功删除: {deleted_count} 个文件")
print(f"删除失败: {skipped_count} 个文件")
