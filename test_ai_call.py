import sys
import asyncio
sys.path.insert(0, 'backend')

from app.utils.deepseek import call_text_llm

async def test():
    try:
        result = await call_text_llm(
            messages=[{"role": "user", "content": "1+1=?"}],
            system_prompt="你是数学助手",
            max_tokens=50
        )
        print("AI调用成功:", result[:100])
    except Exception as e:
        print("AI调用失败:", str(e))
        import traceback
        traceback.print_exc()

asyncio.run(test())
