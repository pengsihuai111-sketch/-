"""
v3.0 题库架构操作工具库
小升初数学题库 - 分层分片存储操作接口

在新会话中，将此文件与 math_bank_v3/ 目录一起上传，
即可执行所有题库操作（查询、筛选、入库、更新、生成练习单等）。

用法:
    from v3_toolkit import QuestionBankV3
    bank = QuestionBankV3("/path/to/math_bank_v3")
    questions = bank.get_questions_by_knowledge_point("几何面积")
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Callable
from collections import defaultdict


class QuestionBankV3:
    """v3.0 分层分片题库操作类"""

    def __init__(self, base_dir: str):
        """
        初始化题库连接
        :param base_dir: math_bank_v3/ 目录的绝对路径
        """
        self.base_dir = base_dir
        self.index_dir = os.path.join(base_dir, "index")
        self.questions_dir = os.path.join(base_dir, "questions")
        self.images_dir = os.path.join(base_dir, "images")
        self.dedup_dir = os.path.join(base_dir, "dedup")
        self.student_dir = os.path.join(base_dir, "student")
        self.wq_dir = os.path.join(base_dir, "wrong_questions")

        # 缓存
        self._master_index = None
        self._kp_index = None
        self._shard_cache = {}  # shard_name -> data
        self._dedup_index = None

    # ========== 索引加载（轻量） ==========

    def _load_master_index(self) -> Dict:
        """加载主索引（~120KB @ 200题，~500KB @ 800题）"""
        if self._master_index is None:
            path = os.path.join(self.index_dir, "master_index.json")
            with open(path, "r", encoding="utf-8") as f:
                self._master_index = json.load(f)
        return self._master_index

    def _load_kp_index(self) -> Dict:
        """加载知识点索引"""
        if self._kp_index is None:
            path = os.path.join(self.index_dir, "knowledge_point_index.json")
            with open(path, "r", encoding="utf-8") as f:
                self._kp_index = json.load(f)
        return self._kp_index

    def _load_shard(self, shard_name: str) -> Dict:
        """按需加载分片内容"""
        if shard_name not in self._shard_cache:
            path = os.path.join(self.questions_dir, f"{shard_name}.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._shard_cache[shard_name] = json.load(f)
            else:
                self._shard_cache[shard_name] = {"questions": []}
        return self._shard_cache[shard_name]

    def _load_dedup_index(self) -> Dict:
        """加载查重索引"""
        if self._dedup_index is None:
            path = os.path.join(self.dedup_dir, "dedup_index.json")
            with open(path, "r", encoding="utf-8") as f:
                self._dedup_index = json.load(f)
        return self._dedup_index

    def _save_master_index(self):
        """保存主索引"""
        path = os.path.join(self.index_dir, "master_index.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._master_index, f, ensure_ascii=False, indent=2)

    def _save_shard(self, shard_name: str):
        """保存分片"""
        if shard_name in self._shard_cache:
            path = os.path.join(self.questions_dir, f"{shard_name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._shard_cache[shard_name], f, ensure_ascii=False, indent=2)

    def _save_dedup_index(self):
        """保存查重索引"""
        if self._dedup_index:
            path = os.path.join(self.dedup_dir, "dedup_index.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._dedup_index, f, ensure_ascii=False, indent=2)

    # ========== 核心查询API ==========

    def get_question_meta(self, q_id: str) -> Optional[Dict]:
        """获取题目的元数据（从主索引，不加载分片）"""
        master = self._load_master_index()
        for q in master["questions"]:
            if q["q_id"] == q_id:
                return q
        return None

    def get_question_full(self, q_id: str) -> Optional[Dict]:
        """获取题目的完整数据（包括原文和答案）"""
        meta = self.get_question_meta(q_id)
        if not meta:
            return None
        shard = self._load_shard(meta["shard"])
        for q in shard["questions"]:
            if q["q_id"] == q_id:
                return q
        return None

    def get_questions_by_knowledge_point(self, kp: str) -> List[Dict]:
        """按知识点获取题目（只加载相关分片）"""
        master = self._load_master_index()
        result = []
        for q_meta in master["questions"]:
            if q_meta["knowledge_point"] == kp:
                full = self.get_question_full(q_meta["q_id"])
                if full:
                    result.append(full)
        return result

    def get_questions_by_shard(self, shard_name: str) -> List[Dict]:
        """按分片获取全部题目"""
        shard = self._load_shard(shard_name)
        return shard.get("questions", [])

    def filter_questions(self, **conditions) -> List[Dict]:
        """
        多条件筛选题目（只从主索引筛选，不加载分片内容）
        conditions: knowledge_point, difficulty, question_type, source_school_full,
                    has_image, is_key_point, answer_status, etc.
        """
        master = self._load_master_index()
        results = []
        for q in master["questions"]:
            match = True
            for key, value in conditions.items():
                if q.get(key) != value:
                    match = False
                    break
            if match:
                results.append(q)
        return results

    def get_image_path(self, q_id: str) -> Optional[str]:
        """获取题目图片的绝对路径"""
        meta = self.get_question_meta(q_id)
        if meta and meta.get("has_image") and meta.get("image_path"):
            img_path = os.path.join(self.images_dir, meta["image_path"])
            if os.path.exists(img_path):
                return img_path
        return None

    # ========== 练习单生成 ==========

    def generate_practice_sheet(self, q_ids: List[str]) -> Dict:
        """
        生成练习单（学生卷 + 答案卷）
        :param q_ids: 题目ID列表（通常7-10题）
        :return: {student_sheet: [...], answer_sheet: [...], meta: {...}}
        """
        student_sheet = []
        answer_sheet = []
        total_time = 0

        for i, q_id in enumerate(q_ids, 1):
            q = self.get_question_full(q_id)
            if not q:
                continue

            # 学生卷条目
            img_path = self.get_image_path(q_id)
            student_entry = {
                "day_q": f"Q{i}",
                "q_id": q_id,
                "knowledge_point": q["knowledge_point"],
                "question_type": q["question_type"],
                "difficulty": q["difficulty"],
                "question_text": q["question_text"],
                "has_image": q.get("has_image", False),
                "image_path": img_path,
                "source": f"{q.get('source_school_full', '')} {q.get('source_exam', '')} {q.get('source_number', '')}",
                "solve_area": ""
            }
            student_sheet.append(student_entry)

            # 答案卷条目
            answer_entry = {
                "day_q": f"Q{i}",
                "q_id": q_id,
                "knowledge_point": q["knowledge_point"],
                "difficulty": q["difficulty"],
                "answer": q.get("answer", "待补充"),
                "solution": q.get("solution", "待补充"),
                "source": f"{q.get('source_school_full', '')} {q.get('source_exam', '')} {q.get('source_number', '')}",
                "verification_status": q.get("verification_status", "unknown"),
                "image_path": img_path
            }
            answer_sheet.append(answer_entry)

        # 难度时间估算
        time_estimate = self._estimate_time(student_sheet)

        return {
            "meta": {
                "total_questions": len(student_sheet),
                "time_estimate_minutes": time_estimate,
                "generated_at": datetime.now().isoformat()
            },
            "student_sheet": student_sheet,
            "answer_sheet": answer_sheet
        }

    def _estimate_time(self, questions: List[Dict]) -> int:
        """估算练习用时（分钟）"""
        time_map = {"基础": 2, "中等": 3, "挑战": 5}
        type_map = {"fill_blank": 2, "choice": 2, "problem_solving": 8, "calculation": 3}
        total = 0
        for q in questions:
            t = type_map.get(q.get("question_type"), 3)
            d = time_map.get(q.get("difficulty"), 3)
            total += max(t, d)
        return min(total, 35)  # 上限35分钟

    # ========== 错题相关 ==========

    def load_wrong_questions(self) -> Dict:
        """加载错题库"""
        path = os.path.join(self.wq_dir, "wrong_question_bank.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_student_state(self) -> Dict:
        """加载学生状态"""
        path = os.path.join(self.student_dir, "冯紫桐_学习状态.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_wrong_question_sheet(self) -> Dict:
        """生成错题重做练习单（基于wrong_question_bank）"""
        wq_data = self.load_wrong_questions()
        wq_list = wq_data.get("wrong_questions", [])

        q_ids = [wq["question_id"] for wq in wq_list]
        result = self.generate_practice_sheet(q_ids)
        result["meta"]["type"] = "错题重做"
        result["meta"]["total_wrong"] = len(wq_list)

        # 附加考情分析
        result["exam_analysis"] = self._generate_exam_analysis(wq_list)
        return result

    def _generate_exam_analysis(self, wq_list: List[Dict]) -> Dict:
        """生成考情分析"""
        kp_stats = defaultdict(lambda: {"total": 0, "wrong": 0})
        for wq in wq_list:
            kp = wq.get("knowledge_point", "未知")
            kp_stats[kp]["total"] += 1
            if wq.get("is_correct") == False:
                kp_stats[kp]["wrong"] += 1

        # 计算掌握度
        mastery = {}
        for kp, stats in kp_stats.items():
            if stats["total"] > 0:
                mastery[kp] = round((stats["total"] - stats["wrong"]) / stats["total"] * 100, 1)
            else:
                mastery[kp] = 100.0

        return {
            "knowledge_point_mastery": dict(mastery),
            "weak_points": [kp for kp, rate in mastery.items() if rate < 60],
            "total_questions": sum(s["total"] for s in kp_stats.values()),
            "total_wrong": sum(s["wrong"] for s in kp_stats.values())
        }

    # ========== 新题入库 ==========

    def check_duplicate(self, question_text: str, school: str, exam: str, number: str) -> Optional[str]:
        """
        查重检查
        :return: 如果重复返回已有q_id，否则返回None
        """
        dedup = self._load_dedup_index()
        source_key = f"{school}_{exam}_{number}"
        if source_key in dedup.get("source_index", {}):
            return dedup["source_index"][source_key]
        # 文本指纹比对（简化版）
        text_prefix = question_text[:50] if question_text else ""
        for qid, fp in dedup.get("text_fingerprint", {}).items():
            if fp.get("school") == school and fp.get("set") == exam and fp.get("number") == str(number):
                return qid
        return None

    def add_question(self, question: Dict, shard_name: str) -> str:
        """
        新增题目入库
        :param question: 完整题目字典（含q_id, question_text, answer等）
        :param shard_name: 目标分片名（如"几何", "方程与应用"等）
        :return: 新题目的q_id
        """
        # 1. 加载并更新分片
        shard = self._load_shard(shard_name)
        shard["questions"].append(question)
        shard["_meta"]["total_questions"] = len(shard["questions"])
        if question.get("knowledge_point") not in shard["_meta"].get("knowledge_points", []):
            shard["_meta"].setdefault("knowledge_points", []).append(question["knowledge_point"])
        self._save_shard(shard_name)

        # 2. 更新主索引
        master = self._load_master_index()
        master_entry = {
            "q_id": question["q_id"],
            "knowledge_point": question.get("knowledge_point", ""),
            "shard": shard_name,
            "question_type": question.get("question_type", ""),
            "difficulty": question.get("difficulty", "中等"),
            "source_school_full": question.get("source_school_full", ""),
            "source_exam": question.get("source_exam", ""),
            "source_number": question.get("source_number", ""),
            "exam_year": question.get("exam_year", "2025"),
            "has_image": question.get("has_image", False),
            "image_path": question.get("image_path"),
            "is_key_point": question.get("is_key_point", False),
            "is_difficult": question.get("is_difficult", False),
            "is_high_freq": question.get("is_high_freq", False),
            "confirmed": question.get("confirmed_by_user", False),
            "answer_status": question.get("verification_status", "pending"),
            "usage_count": 0,
            "last_used": None
        }
        master["questions"].append(master_entry)
        master["_meta"]["total_questions"] = len(master["questions"])
        self._save_master_index()

        # 3. 更新查重索引
        dedup = self._load_dedup_index()
        dedup["text_fingerprint"][question["q_id"]] = {
            "q_id": question["q_id"],
            "fingerprint": f"fp_{hash(question.get('question_text', '')) % 100000000:08d}",
            "has_text": bool(question.get("question_text")),
            "knowledge_point": question.get("knowledge_point", ""),
            "school": question.get("source_school_full", ""),
            "set": question.get("source_exam", ""),
            "number": question.get("source_number", ""),
            "length": len(question.get("question_text", ""))
        }
        source_key = f"{question.get('source_school_full', '')}_{question.get('source_exam', '')}_{question.get('source_number', '')}"
        dedup["source_index"][source_key] = question["q_id"]
        self._save_dedup_index()

        return question["q_id"]

    def update_answer(self, q_id: str, answer: str, solution: str) -> bool:
        """
        更新题目的答案和解析
        :return: 是否成功
        """
        meta = self.get_question_meta(q_id)
        if not meta:
            return False

        # 更新分片
        shard = self._load_shard(meta["shard"])
        for q in shard["questions"]:
            if q["q_id"] == q_id:
                q["answer"] = answer
                q["solution"] = solution
                q["verification_status"] = "verified"
                break
        self._save_shard(meta["shard"])

        # 更新主索引
        master = self._load_master_index()
        for q in master["questions"]:
            if q["q_id"] == q_id:
                q["answer_status"] = "verified"
                break
        self._save_master_index()
        return True

    def record_usage(self, q_id: str):
        """记录题目出题历史"""
        meta = self.get_question_meta(q_id)
        if not meta:
            return
        master = self._load_master_index()
        for q in master["questions"]:
            if q["q_id"] == q_id:
                q["usage_count"] = q.get("usage_count", 0) + 1
                q["last_used"] = datetime.now().strftime("%Y-%m-%d")
                break
        self._save_master_index()

    # ========== 统计与诊断 ==========

    def get_stats(self) -> Dict:
        """获取题库统计信息"""
        master = self._load_master_index()
        stats = {
            "total_questions": len(master["questions"]),
            "by_difficulty": defaultdict(int),
            "by_question_type": defaultdict(int),
            "by_knowledge_point": defaultdict(int),
            "by_school": defaultdict(int),
            "with_image": 0,
            "verified_answers": 0,
            "pending_answers": 0
        }
        for q in master["questions"]:
            stats["by_difficulty"][q.get("difficulty", "未知")] += 1
            stats["by_question_type"][q.get("question_type", "未知")] += 1
            stats["by_knowledge_point"][q.get("knowledge_point", "未知")] += 1
            stats["by_school"][q.get("source_school_full", "未知")] += 1
            if q.get("has_image"):
                stats["with_image"] += 1
            if q.get("answer_status") == "verified":
                stats["verified_answers"] += 1
            elif q.get("answer_status") in ("needs_review", "pending"):
                stats["pending_answers"] += 1

        return {
            **stats,
            "by_difficulty": dict(stats["by_difficulty"]),
            "by_question_type": dict(stats["by_question_type"]),
            "by_knowledge_point": dict(stats["by_knowledge_point"]),
            "by_school": dict(stats["by_school"])
        }

    def get_knowledge_mastery(self) -> Dict:
        """基于错题库获取知识点掌握度"""
        try:
            state = self.load_student_state()
            return state.get("knowledge_mastery", {})
        except:
            return {}

    def get_weak_points(self) -> List[str]:
        """获取薄弱知识点（掌握度 < 60% 的知识点）"""
        mastery = self.get_knowledge_mastery()
        return [kp for kp, rate in mastery.items() if isinstance(rate, (int, float)) and rate < 60]

    def get_forgetting_risk_list(self, days_threshold: int = 7) -> List[Dict]:
        """
        获取遗忘风险列表（超过days_threshold天未练习且已掌握的知识点）
        """
        master = self._load_master_index()
        risk_list = []
        today = datetime.now()

        for q in master["questions"]:
            last_used = q.get("last_used")
            if last_used:
                days = (today - datetime.strptime(last_used, "%Y-%m-%d")).days
                if days >= days_threshold and q.get("answer_status") == "verified":
                    risk_list.append({
                        "q_id": q["q_id"],
                        "knowledge_point": q["knowledge_point"],
                        "days_since_last": days,
                        "difficulty": q["difficulty"]
                    })

        return sorted(risk_list, key=lambda x: x["days_since_last"], reverse=True)

    # ========== 去重辅助 ==========

    def get_recently_used(self, days: int = 7) -> List[str]:
        """获取最近N天出过的题目ID列表（去重用）"""
        master = self._load_master_index()
        today = datetime.now()
        recent = []
        for q in master["questions"]:
            last = q.get("last_used")
            if last:
                d = (today - datetime.strptime(last, "%Y-%m-%d")).days
                if d <= days:
                    recent.append(q["q_id"])
        return recent

    def find_similar_kp(self, kp: str, exclude_ids: List[str] = None) -> List[Dict]:
        """找同类知识点的备选题目（举一反三用）"""
        exclude_ids = exclude_ids or []
        master = self._load_master_index()
        candidates = []
        for q in master["questions"]:
            if q["knowledge_point"] == kp and q["q_id"] not in exclude_ids:
                full = self.get_question_full(q["q_id"])
                if full:
                    candidates.append(full)
        return candidates


# ========== 便捷函数 ==========

def init_bank_v3(base_dir: str) -> QuestionBankV3:
    """快捷初始化"""
    return QuestionBankV3(base_dir)


if __name__ == "__main__":
    # 简单测试
    bank = QuestionBankV3(".")
    stats = bank.get_stats()
    print(f"题库统计: {stats['total_questions']}题")
    print(f"难度分布: {stats['by_difficulty']}")
    print(f"带图题: {stats['with_image']}道")
    print(f"已验证答案: {stats['verified_answers']}道")
