"""实时监控识别请求"""
import asyncio
import httpx
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def monitor():
    print("开始监控后端服务...")
    print("请在前端上传图片进行识别")
    print("="*80)

    # 检查服务状态
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://localhost:8000/api/health")
            print(f"✓ 后端服务运行正常: {resp.json()}")
        except Exception as e:
            print(f"✗ 后端服务连接失败: {e}")
            return

    print("\n等待识别请求...")
    print("(按 Ctrl+C 停止监控)")

    # 持续检查
    while True:
        await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print("\n监控已停止")
