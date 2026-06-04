import unittest
import asyncio
from unittest.mock import patch

from app.agents.constants import (
    LEARNING_DIAGNOSIS,
    PARENT_REPORT,
    PRACTICE_GENERATE,
    QUESTION_EXPLAIN,
    SEMANTIC_QUESTION_SEARCH,
    SIMILAR_QUESTION_RECOMMEND,
    SMALLTALK,
    STUDY_PLAN,
    WRONG_QUESTION_ADD,
    WRONG_QUESTION_REVIEW,
)
from app.agents.graph import run_agent_graph
from app.agents.context import load_agent_context, resolve_context_references, wants_all_referenced_questions
from app.agents.planner import build_task_plan
from app.agents.response import build_response
from app.agents.router import route_message
from app.agents.subgraphs.diagnosis_graph import run_diagnosis_subgraph
from app.agents.subgraphs.question_graph import run_question_subgraph
from app.agents.subgraphs.search_graph import run_search_subgraph
from app.agents.tools.practice_tools import _build_prompt_with_source_questions


class AgentRouterTest(unittest.TestCase):
    def route(self, message, history=None):
        state = {"message": message, "history": history or []}
        return route_message(state)

    def test_wrong_question_review_recent_days(self):
        state = self.route("看看我最近 7 天的错题")
        self.assertEqual(state["intent"], WRONG_QUESTION_REVIEW)
        self.assertEqual(state["tool_args"]["recent_days"], 7)

    def test_question_explain_pending_question(self):
        state = self.route("给我讲解一道题，我把题目发给你")
        self.assertEqual(state["intent"], QUESTION_EXPLAIN)
        self.assertTrue(state["tool_args"]["awaiting_question"])

    def test_practice_generate(self):
        state = self.route("按错题生成一套举一反三练习单")
        self.assertEqual(state["intent"], PRACTICE_GENERATE)

    def test_similar_question_recommend(self):
        state = self.route("推荐几道同类题")
        self.assertEqual(state["intent"], SIMILAR_QUESTION_RECOMMEND)

    def test_semantic_question_search(self):
        state = self.route("搜索几何面积阴影面积题目")
        self.assertEqual(state["intent"], SEMANTIC_QUESTION_SEARCH)

    def test_learning_diagnosis(self):
        state = self.route("我最近哪里最薄弱")
        self.assertEqual(state["intent"], LEARNING_DIAGNOSIS)

    def test_study_plan(self):
        state = self.route("制定一份 7 天学习计划")
        self.assertEqual(state["intent"], STUDY_PLAN)
        self.assertEqual(state["tool_args"]["days"], 7)

    def test_parent_week_report(self):
        state = self.route("生成一份家长周报")
        self.assertEqual(state["intent"], PARENT_REPORT)
        self.assertEqual(state["tool_args"]["days"], 7)

    def test_parent_month_report(self):
        state = self.route("生成一份家长月报")
        self.assertEqual(state["intent"], PARENT_REPORT)
        self.assertEqual(state["tool_args"]["days"], 30)

    def test_name_memory_reply(self):
        state = self.route(
            "我叫什么",
            history=[
                {"role": "user", "content": "我叫李四"},
                {"role": "assistant", "content": "我记住啦，你叫李四。"},
                {"role": "user", "content": "我叫什么"},
            ],
        )
        self.assertEqual(state["intent"], SMALLTALK)
        self.assertEqual(state["tool_args"]["memory_query"], "name")
        response = build_response(state)
        self.assertEqual(response["response_source"], "memory")
        self.assertIn("李四", response["reply"])

    def test_attachment_question_followup(self):
        state = self.route(
            "讲第 1 题",
            history=[
                {
                    "role": "assistant",
                    "content": "我已经识别了这个图片，共找到 1 道题。",
                    "actions": [
                        {
                            "type": "show_attachment_questions",
                            "data": {
                                "questions": [
                                    {
                                        "question_no": "1",
                                        "question_text": "甲乙两人相向而行，求相遇时间。",
                                    }
                                ]
                            },
                        }
                    ],
                }
            ],
        )
        self.assertEqual(state["intent"], QUESTION_EXPLAIN)
        self.assertEqual(state["tool_args"]["source"], "attachment")
        self.assertIn("相遇时间", state["tool_args"]["question_text"])

    def test_attachment_every_question_followup_explains_all(self):
        state = self.route(
            "帮我生成每个题的详细解析",
            history=[
                {
                    "role": "assistant",
                    "content": "我已经识别了这个文件，共找到 2 道题。",
                    "actions": [
                        {
                            "type": "show_attachment_questions",
                            "data": {
                                "questions": [
                                    {"question_no": "1", "question_text": "综合练习（三）— 提取题目", "question_type": "other"},
                                    {"question_no": "2", "question_text": "第一题题干"},
                                    {"question_no": "3", "question_text": "第二题题干"},
                                ]
                            },
                        }
                    ],
                }
            ],
        )
        self.assertEqual(state["intent"], QUESTION_EXPLAIN)
        self.assertTrue(state["tool_args"]["explain_all"])
        self.assertEqual(len(state["tool_args"]["attachment_questions"]), 2)
        self.assertIn("第一题", state["tool_args"]["attachment_questions"][0]["question_text"])
        self.assertTrue(wants_all_referenced_questions("帮我给出每个题的详细解析"))

    def test_normalize_attachment_questions_filters_document_heading(self):
        from app.api.assistant import _normalize_questions_payload

        questions = _normalize_questions_payload([
            {"question_no": "1", "question_text": "综合练习（三）— 提取题目", "question_type": "other"},
            {"question_no": "2", "question_text": "填空题 1 甲数是乙数的 2 倍，求甲数。", "answer": "略"},
            {"question_no": "3", "question_text": "二、选择题（每题 3 分）", "question_type": "other"},
            {"question_no": "4", "question_text": "选择题 如图，下面说法错误的是（ ）。"},
        ])

        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["question_no"], "1")
        self.assertEqual(questions[0]["source_question_no"], "2")
        self.assertIn("甲数", questions[0]["question_text"])
        self.assertEqual(questions[1]["question_no"], "2")
        self.assertIn("说法错误", questions[1]["question_text"])

    def test_wrong_question_add_from_attachment(self):
        state = self.route(
            "把第 2 题加入错题本",
            history=[
                {
                    "role": "assistant",
                    "content": "我已经识别了这个图片，共找到 2 道题。",
                    "actions": [
                        {
                            "type": "show_attachment_questions",
                            "data": {
                                "questions": [
                                    {"question_no": "1", "question_text": "第一题题干"},
                                    {"question_no": "2", "question_text": "第二题题干"},
                                ]
                            },
                        }
                    ],
                }
            ],
        )
        self.assertEqual(state["intent"], WRONG_QUESTION_ADD)
        self.assertEqual(state["tool_args"]["source"], "attachment")
        self.assertIn("第二题", state["tool_args"]["question_text"])

    def test_context_resolver_targets_second_attachment_question(self):
        state = {
            "message": "讲第 2 题",
            "history": [
                {
                    "role": "assistant",
                    "actions": [
                        {
                            "type": "show_attachment_questions",
                            "data": {
                                "questions": [
                                    {"question_no": "1", "question_text": "第一题题干"},
                                    {"question_no": "2", "question_text": "第二题题干"},
                                ]
                            },
                        }
                    ],
                }
            ],
            "intent": QUESTION_EXPLAIN,
            "tool_args": {},
        }
        state = load_agent_context(state)
        state = resolve_context_references(state)
        self.assertEqual(state["resolved_target"]["ordinal"], 2)
        self.assertIn("第二题", state["tool_args"]["question_text"])

    def test_planner_routes_question_and_wrong_subgraphs(self):
        question_state = build_task_plan({"intent": QUESTION_EXPLAIN, "message": "讲第 1 题", "tool_args": {}})
        self.assertEqual(question_state["business_graph"], "question_subgraph")
        self.assertTrue(any(step["step"] == "explain_question" for step in question_state["plan_steps"]))

        wrong_state = build_task_plan({"intent": WRONG_QUESTION_ADD, "message": "把这些题加入错题本", "tool_args": {}})
        self.assertEqual(wrong_state["business_graph"], "wrong_subgraph")
        self.assertTrue(any(step["step"] == "add_questions_to_wrong_book" for step in wrong_state["plan_steps"]))

    def test_main_graph_uses_multi_node_flow(self):
        async def fail_llm_router(state):
            raise RuntimeError("skip network in unit test")

        async def skip_polish(state):
            return None

        with (
            patch("app.agents.nodes.main_nodes.route_message_with_llm", fail_llm_router),
            patch("app.agents.nodes.main_nodes.polish_reply_with_llm", skip_polish),
        ):
            state = asyncio.run(run_agent_graph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "你好",
                "history": [],
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "chat_subgraph")
        self.assertIn("load_context_node", state["node_trace"])
        self.assertIn("task_planner_node", state["node_trace"])
        self.assertIn("chat_reply_node", state["node_trace"])

    def test_question_subgraph_explains_multiple_attachment_questions(self):
        async def fake_generate_answer(question_text, question_type="", knowledge_point=""):
            return {"answer": f"答案-{question_text[:2]}", "solution": f"解析-{question_text[:2]}"}

        with patch("app.agents.subgraphs.question_graph.generate_answer", fake_generate_answer):
            state = asyncio.run(run_question_subgraph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "解析图片里的题目",
                "intent": QUESTION_EXPLAIN,
                "tool_args": {
                    "attachment_questions": [
                        {"question_no": "1", "question_text": "第一题题干"},
                        {"question_no": "2", "question_text": "第二题题干"},
                    ],
                    "explain_all": True,
                },
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "question_subgraph")
        self.assertEqual(len(state["actions"]), 2)
        self.assertEqual(state["actions"][1]["data"]["question"]["explain_order"], 2)
        self.assertEqual(state["actions"][1]["data"]["question"]["validation_status"], "ok")

    def test_question_subgraph_explains_all_fifteen_attachment_questions(self):
        async def fake_generate_answer(question_text, question_type="", knowledge_point=""):
            return {"answer": "答案", "solution": "解析"}

        questions = [
            {"question_no": str(index), "question_text": f"第 {index} 题题干"}
            for index in range(1, 16)
        ]
        with patch("app.agents.subgraphs.question_graph.generate_answer", fake_generate_answer):
            state = asyncio.run(run_question_subgraph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "帮我生成每个题的详细解析",
                "intent": QUESTION_EXPLAIN,
                "tool_args": {
                    "attachment_questions": questions,
                    "explain_all": True,
                },
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(len(state["actions"]), 15)
        self.assertEqual(state["actions"][-1]["data"]["question"]["explain_order"], 15)

    def test_practice_prompt_uses_source_question_texts(self):
        prompt = _build_prompt_with_source_questions(
            "用这些题生成举一反三",
            [{"question_text": "甲乙工程问题，合作完成需要几天？"}],
        )
        self.assertIn("参考题目如下", prompt)
        self.assertIn("工程问题", prompt)

    def test_diagnosis_subgraph_adds_meta_and_node_trace(self):
        def fake_weak_points(user_id, args, db):
            return {
                "reply": "薄弱点分析完成",
                "actions": [{"type": "show_weak_points", "data": {"weak_points": []}}],
                "suggestions": ["生成练习"],
                "data": {"weak_points": []},
            }

        with patch("app.agents.subgraphs.diagnosis_graph.get_weak_points_tool", fake_weak_points):
            state = asyncio.run(run_diagnosis_subgraph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "分析我的薄弱点",
                "intent": LEARNING_DIAGNOSIS,
                "tool_args": {},
                "context": {},
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "diagnosis_subgraph")
        self.assertIn("diagnosis_collect_node", state["node_trace"])
        self.assertIn("diagnosis_output_node", state["node_trace"])
        self.assertEqual(state["tool_result"]["data"]["diagnosis_meta"]["business_graph"], "diagnosis_subgraph")

    def test_search_subgraph_dedupes_and_reranks_results(self):
        async def fake_search(user_id, args, db):
            return {
                "reply": "找到题目",
                "actions": [],
                "suggestions": [],
                "data": {
                    "items": [
                        {"question_id": 1, "question_text": "工程题A", "score": 0.2, "source": "mysql_keyword"},
                        {"question_id": 1, "question_text": "工程题A重复", "score": 0.9, "source": "qdrant_hybrid"},
                        {"question_id": 2, "question_text": "工程题B", "score": 0.7, "source": "qdrant_hybrid"},
                    ]
                },
            }

        with patch("app.agents.subgraphs.search_graph.semantic_search_tool", fake_search):
            state = asyncio.run(run_search_subgraph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "搜索工程问题",
                "intent": SEMANTIC_QUESTION_SEARCH,
                "tool_args": {"query": "工程问题", "limit": 8},
                "context": {},
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "search_subgraph")
        self.assertEqual(len(state["search_results"]), 2)
        self.assertEqual(state["search_results"][0]["question_id"], 1)
        self.assertEqual(state["search_results"][0]["rank"], 1)
        self.assertIn("search_meta", state["tool_result"]["data"])

    def test_main_graph_routes_search_to_search_subgraph(self):
        async def fail_llm_router(state):
            raise RuntimeError("skip network in unit test")

        async def skip_polish(state):
            return None

        async def fake_search(user_id, args, db):
            return {
                "reply": "找到题目",
                "actions": [],
                "suggestions": [],
                "data": {"items": [{"question_id": 8, "question_text": "工程题", "score": 0.8, "source": "mysql_keyword"}]},
            }

        with (
            patch("app.agents.nodes.main_nodes.route_message_with_llm", fail_llm_router),
            patch("app.agents.nodes.main_nodes.polish_reply_with_llm", skip_polish),
            patch("app.agents.subgraphs.search_graph.semantic_search_tool", fake_search),
        ):
            state = asyncio.run(run_agent_graph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "搜索工程问题",
                "history": [],
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "search_subgraph")
        self.assertIn("semantic_search_node", state["node_trace"])
        self.assertEqual(state["search_results"][0]["rank"], 1)

    def test_main_graph_routes_parent_report_to_diagnosis_subgraph(self):
        async def fail_llm_router(state):
            raise RuntimeError("skip network in unit test")

        async def skip_polish(state):
            return None

        def fake_parent_report(user_id, args, db):
            return {
                "reply": "家长周报完成",
                "actions": [{"type": "show_parent_report", "data": {"days": args.get("days")}}],
                "suggestions": ["生成练习"],
                "data": {"days": args.get("days")},
            }

        with (
            patch("app.agents.nodes.main_nodes.route_message_with_llm", fail_llm_router),
            patch("app.agents.nodes.main_nodes.polish_reply_with_llm", skip_polish),
            patch("app.agents.subgraphs.diagnosis_graph.build_parent_report_tool", fake_parent_report),
        ):
            state = asyncio.run(run_agent_graph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "生成一份家长周报",
                "history": [],
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "diagnosis_subgraph")
        self.assertIn("diagnosis_analyze_node", state["node_trace"])
        self.assertEqual(state["tool_result"]["data"]["diagnosis_meta"]["scope"]["days"], 7)

    def test_main_graph_routes_attachment_questions_to_practice_subgraph(self):
        async def fail_llm_router(state):
            raise RuntimeError("skip network in unit test")

        async def skip_polish(state):
            return None

        async def fake_practice_preview(user_id, args, db):
            source_action = args.get("source_action") or {}
            questions = (source_action.get("data") or {}).get("questions") or []
            return {
                "reply": "练习单预览完成",
                "actions": [{"type": "show_practice_preview", "data": {"variants": [], "source_count": len(questions)}}],
                "suggestions": ["确认生成练习单"],
                "data": {"source_count": len(questions)},
            }

        history = [{
            "role": "assistant",
            "actions": [{
                "type": "show_attachment_questions",
                "data": {"questions": [
                    {"question_no": "1", "question_text": "第一题题干"},
                    {"question_no": "2", "question_text": "第二题题干"},
                ]},
            }],
        }]

        with (
            patch("app.agents.nodes.main_nodes.route_message_with_llm", fail_llm_router),
            patch("app.agents.nodes.main_nodes.polish_reply_with_llm", skip_polish),
            patch("app.agents.subgraphs.practice_graph.generate_practice_preview_tool", fake_practice_preview),
        ):
            state = asyncio.run(run_agent_graph({
                "user_id": 1,
                "session_id": "test-session",
                "message": "用这些题生成练习单",
                "history": history,
                "actions": [],
                "suggestions": [],
            }, db=None))

        self.assertEqual(state["business_graph"], "practice_subgraph")
        self.assertIn("practice_source_node", state["node_trace"])
        self.assertEqual(state["tool_result"]["data"]["source_count"], 2)


if __name__ == "__main__":
    unittest.main()
