from typing import Any, Dict

from sqlalchemy.orm import Session


def get_system_help_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    topic = str(args.get("topic") or "")
    if "上传" in topic or "错题" in topic:
        reply = "你可以进入“错题管理”，点击图片上传或文件上传，上传后等待识别结果，确认题目、答案和解析后加入错题本。"
    elif "练习" in topic or "组卷" in topic:
        reply = "你可以进入“练习单”，选择知识点或错题生成方式；也可以直接在这里告诉我想练什么，我会先生成预览给你确认。"
    elif "学情" in topic or "诊断" in topic:
        reply = "你可以进入“学情诊断”查看掌握率、薄弱点和遗忘风险；也可以问我“我最近哪里最薄弱”。"
    else:
        reply = "我可以帮你生成练习单、查看错题、分析薄弱点、讲解题目，也可以说明系统功能怎么使用。"
    return {
        "reply": reply,
        "actions": [{"type": "system_help", "data": {"topic": topic, "content": reply}}],
        "suggestions": ["生成练习单", "查看薄弱点", "查看最近错题"],
    }

