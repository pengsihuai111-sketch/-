"""Rule-based metadata cleanup for recognized math questions.

The vision/text model sometimes leaves knowledge fields blank or returns only
very broad categories. These helpers provide a deterministic fallback so OCR
imports remain useful even when the model is terse.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_KNOWLEDGE_CATALOG: Dict[str, List[str]] = {
    "行程": ["行程问题", "相遇问题", "追及问题", "流水行船"],
    "工程": ["工程问题"],
    "经济": ["经济问题", "利润折扣", "成本售价"],
    "浓度": ["浓度问题", "溶液混合"],
    "几何": ["几何面积", "几何周长", "圆柱圆锥", "立体几何", "图形比例"],
    "计算": ["简便运算", "分数计算", "小数计算", "百分数计算", "四则混合运算"],
    "数论": ["因数与倍数", "质数合数", "最大公因数与最小公倍数", "余数问题"],
    "方程与应用": ["方程应用", "比例应用", "分数应用题", "百分数应用题"],
    "逻辑推理": ["逻辑推理", "排列组合", "找规律"],
    "统计": ["平均数与统计", "概率统计"],
    "基础": ["单位换算", "时钟问题", "定义新运算"],
    "其他": ["综合应用"],
}


_RULES: List[Tuple[str, str, Iterable[str]]] = [
    ("行程", "流水行船", ("顺水", "逆水", "水流", "船", "静水")),
    ("行程", "相遇问题", ("相遇", "同时出发", "相向", "两地", "速度和")),
    ("行程", "追及问题", ("追上", "追及", "速度差", "领先", "落后")),
    ("行程", "行程问题", ("速度", "路程", "千米/时", "米/秒", "行驶", "骑车", "步行")),
    ("工程", "工程问题", ("工程", "工作效率", "工作量", "合作", "单独完成", "完工")),
    ("经济", "经济问题", ("利润", "成本", "售价", "定价", "折扣", "打折", "盈利", "亏损", "利率", "本金")),
    ("浓度", "浓度问题", ("浓度", "溶质", "溶液", "盐水", "糖水", "酒精", "含盐率", "混合")),
    ("几何", "圆柱圆锥", ("圆柱", "圆锥", "底面积", "侧面积", "体积", "表面积")),
    ("几何", "立体几何", ("长方体", "正方体", "棱长", "表面积", "体积")),
    ("几何", "几何面积", ("面积", "三角形", "梯形", "平行四边形", "圆", "扇形", "阴影")),
    ("几何", "几何周长", ("周长", "边长", "半径", "直径")),
    ("几何", "图形比例", ("比例尺", "图上距离", "实际距离", "放大", "缩小")),
    ("方程与应用", "比例应用", ("比例", "比值", "正比例", "反比例", "按比例", "比例尺")),
    ("方程与应用", "百分数应用题", ("百分之", "%", "百分数", "增长率", "减少率")),
    ("方程与应用", "分数应用题", ("分率", "几分之", "比", "还剩", "占")),
    ("方程与应用", "方程应用", ("设", "方程", "未知数", "解得")),
    ("数论", "最大公因数与最小公倍数", ("最大公因数", "最小公倍数", "公因数", "公倍数")),
    ("数论", "因数与倍数", ("因数", "倍数", "约数", "整除")),
    ("数论", "余数问题", ("余数", "除以", "同余")),
    ("逻辑推理", "找规律", ("规律", "数列", "第n", "第 n", "排列")),
    ("逻辑推理", "逻辑推理", ("至少", "至多", "保证", "抽屉", "推理")),
    ("统计", "平均数与统计", ("平均数", "统计图", "统计表", "中位数", "众数")),
    ("基础", "时钟问题", ("时针", "分针", "钟面", "夹角")),
    ("基础", "单位换算", ("单位", "换算", "千克", "克", "吨", "升", "毫升")),
    ("计算", "简便运算", ("简便", "脱式", "计算", "递等式")),
    ("计算", "分数计算", ("\\frac", "dfrac", "frac", "分数")),
]


def guess_question_type(question_text: str) -> str:
    text = (question_text or "").strip()
    if not text:
        return "other"
    if re.search(r"(^|\s)[A-D][.、．)]", text) or any(k in text for k in ("选择", "正确的是", "错误的是")):
        return "choice"
    if "____" in text or "（  ）" in text or "(  )" in text or "填空" in text:
        return "fill_blank"
    if any(k in text for k in ("计算", "脱式", "简便", "求下列")) and len(text) < 120:
        return "calculation"
    if any(k in text for k in ("多少", "几", "如果", "已知", "求", "问", "需要", "一共", "至少")):
        return "problem_solving"
    return "other"


def classify_knowledge(question_text: str) -> Tuple[str, str]:
    text = question_text or ""
    compact = re.sub(r"\s+", "", text)
    for category, point, keywords in _RULES:
        if any(keyword in text or keyword in compact for keyword in keywords):
            return category, point
    return "其他", "综合应用"


def normalize_question_metadata(question: Dict[str, Any]) -> Dict[str, Any]:
    text = str(question.get("question_text") or "")
    category, point = classify_knowledge(text)

    current_point = str(question.get("knowledge_point") or "").strip()
    current_category = str(question.get("knowledge_category") or "").strip()
    current_type = str(question.get("question_type") or "").strip()

    if not current_point or current_point in {"未知", "其他", "综合", "未分类"}:
        question["knowledge_point"] = point
    if not current_category or current_category in {"其他", "未分类"}:
        question["knowledge_category"] = category
    if not current_type or current_type == "other":
        question["question_type"] = guess_question_type(text)

    kps = question.get("knowledge_points")
    if not kps:
        question["knowledge_points"] = [question.get("knowledge_point") or point]
    elif isinstance(kps, str):
        question["knowledge_points"] = [item.strip() for item in re.split(r"[,，、]", kps) if item.strip()]

    return question


def normalize_questions_metadata(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for question in questions:
        normalize_question_metadata(question)
    return questions
