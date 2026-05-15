"""测试 IMAGE_DIR 配置"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.config import IMAGE_DIR, UPLOAD_DIR
    print(f"UPLOAD_DIR: {UPLOAD_DIR}")
    print(f"IMAGE_DIR: {IMAGE_DIR}")
    print(f"UPLOAD_DIR exists: {os.path.exists(UPLOAD_DIR)}")
    print(f"IMAGE_DIR exists: {os.path.exists(IMAGE_DIR)}")

    # 尝试创建目录
    print("\n尝试创建 IMAGE_DIR...")
    os.makedirs(IMAGE_DIR, exist_ok=True)
    print("创建成功！")

    # 尝试写入测试文件
    test_file = os.path.join(IMAGE_DIR, "test.txt")
    print(f"\n尝试写入测试文件: {test_file}")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("test")
    print("写入成功！")

    # 删除测试文件
    os.remove(test_file)
    print("测试文件已删除")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
