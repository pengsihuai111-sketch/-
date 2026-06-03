import unittest

from app.agents.constants import (
    LEARNING_DIAGNOSIS,
    PARENT_REPORT,
    PRACTICE_GENERATE,
    QUESTION_EXPLAIN,
    SEMANTIC_QUESTION_SEARCH,
    SIMILAR_QUESTION_RECOMMEND,
    SMALLTALK,
    STUDY_PLAN,
    WRONG_QUESTION_REVIEW,
)
from app.agents.response import build_response
from app.agents.router import route_message


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


if __name__ == "__main__":
    unittest.main()
