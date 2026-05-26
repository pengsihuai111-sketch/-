import json
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
import random
import os
import uuid

from ..database import get_db
from ..models import (
    Question, PracticeSheet, SheetQuestion, UserPracticeHistory,
    UserWrongQuestion, UserKnowledgeMastery, PracticeType, SheetType,
)
from ..schemas import GenerateSheetRequest, PracticeSheetOut, QuestionOut, SubmitSheetRequest, SubmitResultOut, QuestionResultOut, GenerateWeekResponse, DaySheetOut, MarkSheetRequest, MarkItem, GenerateWrongPeriodRequest, SmartRedoRequest, SelectedWrongPracticeRequest
from ..utils.auth import get_current_user_id
from ..config import UPLOAD_DIR, IMAGE_DIR

router = APIRouter(prefix="/api/practice", tags=["练习单"])


def _default_practice_sheet_name(sheet_type: str, suffix: str = "") -> str:
    today = date.today().isoformat()
    if sheet_type == "wrong_redo":
        return f"错题原题练习单_{today}{suffix}"
    return f"{sheet_type}_练习单_{today}{suffix}"


@router.post("/generate")
def generate_sheet(
    req: GenerateSheetRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """生成练习单"""
    selected = []
    sections = None

    # 手动选题模式
    if req.question_ids:
        selected = (
            db.query(Question)
            .filter(Question.question_id.in_(req.question_ids))
            .all()
        )
        if not selected:
            raise HTTPException(status_code=400, detail="未找到指定的题目")
        # 保持传入的顺序
        id_order = {qid: i for i, qid in enumerate(req.question_ids)}
        selected.sort(key=lambda q: id_order.get(q.question_id, 999))
        # 按题型分组排序
        selected, sections = _group_questions_by_type(selected)
    elif req.knowledge_group_counts:
        # 分组选题模式：按知识类别/知识点分组，每组选指定数量
        selected = []
        used_ids = set()

        # 获取今天的去重列表
        recent_ids = set(
            r[0]
            for r in db.query(UserPracticeHistory.question_id)
            .filter(
                UserPracticeHistory.user_id == user_id,
                UserPracticeHistory.practice_date >= date.today(),
            )
            .all()
        )

        for group in req.knowledge_group_counts:
            if group.count <= 0:
                continue
            query = db.query(Question)
            query = query.filter(Question.knowledge_point.in_(group.knowledge_points))
            if req.difficulties:
                query = query.filter(Question.difficulty.in_(req.difficulties))
            if recent_ids:
                query = query.filter(Question.question_id.notin_(recent_ids))

            candidates = [q for q in query.all() if q.question_id not in used_ids]
            if not candidates:
                continue

            n = min(group.count, len(candidates))
            picked = random.sample(candidates, n)
            for q in picked:
                used_ids.add(q.question_id)
            selected.extend(picked)

        if not selected:
            raise HTTPException(status_code=400, detail="没有符合条件的题目")

        # 按题型分组排序
        selected, sections = _group_questions_by_type(selected)
    else:
        query = db.query(Question)

        # 筛选知识点
        if req.knowledge_points:
            query = query.filter(Question.knowledge_point.in_(req.knowledge_points))

        # 筛选难度
        if req.difficulties:
            query = query.filter(Question.difficulty.in_(req.difficulties))

        # 获取今天已出过的题，避免重复
        recent_ids = [
            r[0]
            for r in db.query(UserPracticeHistory.question_id)
            .filter(
                UserPracticeHistory.user_id == user_id,
                UserPracticeHistory.practice_date >= date.today(),
            )
            .all()
        ]

        if recent_ids:
            query = query.filter(Question.question_id.notin_(recent_ids))

        candidates = query.all()
        if not candidates:
            raise HTTPException(status_code=400, detail="没有符合条件的题目")

        # 随机选题
        selected = random.sample(candidates, min(req.total_questions, len(candidates)))

        # 按题型分组排序
        selected, sections = _group_questions_by_type(selected)

    # 创建练习单
    time_estimate = _estimate_time(selected)
    sheet_name = req.sheet_name or _default_practice_sheet_name(req.sheet_type)
    sheet = PracticeSheet(
        user_id=user_id,
        sheet_name=sheet_name,
        sheet_type=SheetType(req.sheet_type),
        total_questions=len(selected),
        estimated_time=time_estimate,
    )
    if sections:
        sheet.sections_json = json.dumps(sections, ensure_ascii=False)
    db.add(sheet)
    db.flush()

    # 创建题目关联
    for i, q in enumerate(selected):
        sq = SheetQuestion(
            sheet_id=sheet.sheet_id,
            question_id=q.question_id,
            question_order=i + 1,
        )
        db.add(sq)

        # 记录出题历史
        ph = UserPracticeHistory(
            user_id=user_id,
            question_id=q.question_id,
            practice_date=date.today(),
            practice_type=PracticeType(req.sheet_type),
            sheet_id=sheet.sheet_id,
        )
        db.add(ph)

    db.commit()

    resp = PracticeSheetOut(
        sheet_id=sheet.sheet_id,
        sheet_name=sheet.sheet_name,
        sheet_type=sheet.sheet_type,
        total_questions=sheet.total_questions,
        estimated_time=sheet.estimated_time,
        generated_date=sheet.generated_date,
        questions=[QuestionOut.model_validate(q) for q in selected],
    )
    data = resp.model_dump()
    if sections:
        data["_sections"] = sections
    return data


@router.get("/sheets")
def list_sheets(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    sheets = (
        db.query(PracticeSheet)
        .filter(PracticeSheet.user_id == user_id)
        .order_by(PracticeSheet.generated_date.desc())
        .limit(50)
        .all()
    )
    return {"sheets": sheets}


def _get_wrong_question_info(user_id, question_ids, db):
    """获取指定题目的错题信息（错误次数、上次错误时间等）"""
    if not question_ids:
        return {}

    records = db.query(UserWrongQuestion).filter(
        UserWrongQuestion.user_id == user_id,
        UserWrongQuestion.question_id.in_(question_ids),
    ).all()

    info = {}
    for r in records:
        wrong_count = (r.redo_count or 0) + 1
        last_wrong_date = r.last_redo_date or r.created_date
        info[r.question_id] = {
            "wrong_count": wrong_count,
            "last_wrong_date": last_wrong_date.isoformat() if last_wrong_date else None,
            "mastered": r.mastered,
            "error_type": r.error_type,
        }
    return info


@router.get("/sheets/{sheet_id}")
def get_sheet(
    sheet_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    sheet = (
        db.query(PracticeSheet)
        .filter(
            PracticeSheet.sheet_id == sheet_id,
            PracticeSheet.user_id == user_id,
        )
        .first()
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="练习单不存在")

    sqs = (
        db.query(SheetQuestion)
        .filter(SheetQuestion.sheet_id == sheet_id)
        .order_by(SheetQuestion.question_order)
        .all()
    )

    questions = []
    for sq in sqs:
        q = db.query(Question).filter(Question.question_id == sq.question_id).first()
        if q:
            questions.append(QuestionOut.model_validate(q))

    question_ids = [q.question_id for q in questions]
    wrong_info = _get_wrong_question_info(user_id, question_ids, db)

    resp = PracticeSheetOut(
        sheet_id=sheet.sheet_id,
        sheet_name=sheet.sheet_name,
        sheet_type=sheet.sheet_type,
        total_questions=sheet.total_questions,
        estimated_time=sheet.estimated_time,
        generated_date=sheet.generated_date,
        completed=sheet.completed,
        completed_date=sheet.completed_date,
        score=float(sheet.score) if sheet.score else None,
        questions=questions,
    )
    data = resp.model_dump()
    data["_wrong_question_info"] = wrong_info
    if sheet.sections_json:
        data["_sections"] = json.loads(sheet.sections_json)
    return data


@router.delete("/sheets/{sheet_id}")
def delete_sheet(
    sheet_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """删除练习单"""
    sheet = db.query(PracticeSheet).filter(
        PracticeSheet.sheet_id == sheet_id,
        PracticeSheet.user_id == user_id,
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="练习单不存在")

    # Delete related records
    db.query(SheetQuestion).filter(SheetQuestion.sheet_id == sheet_id).delete()
    db.query(UserPracticeHistory).filter(
        UserPracticeHistory.sheet_id == sheet_id,
        UserPracticeHistory.user_id == user_id,
    ).delete()
    db.delete(sheet)
    db.commit()
    return {"message": "练习单已删除"}


@router.get("/sheets/{sheet_id}/download")
def download_sheet(
    sheet_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """下载练习单为文本文件"""
    sheet = db.query(PracticeSheet).filter(
        PracticeSheet.sheet_id == sheet_id,
        PracticeSheet.user_id == user_id,
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="练习单不存在")

    sqs = db.query(SheetQuestion).filter(
        SheetQuestion.sheet_id == sheet_id
    ).order_by(SheetQuestion.question_order).all()

    questions = []
    for sq in sqs:
        q = db.query(Question).filter(Question.question_id == sq.question_id).first()
        if q:
            questions.append(q)

    # Generate text content
    lines = [
        "=" * 50,
        f"  练习单：{sheet.sheet_name}",
        f"  生成日期：{sheet.generated_date.strftime('%Y-%m-%d') if sheet.generated_date else ''}",
        f"  题目数量：{len(questions)} 题",
        f"  预计用时：{sheet.estimated_time or ''} 分钟",
        "=" * 50,
        "",
    ]

    for i, q in enumerate(questions, 1):
        lines.append(f"第 {i} 题（{q.knowledge_point} / {q.difficulty or '未知难度'}）")
        lines.append("-" * 40)
        lines.append(q.question_text or "")
        if q.has_image:
            lines.append("[本题包含图片，请查看电子版]")
        lines.append("")
        lines.append("答案：______________")
        lines.append("")
        lines.append("")

    lines.append("=" * 50)
    lines.append("  参考答案")
    lines.append("=" * 50)
    lines.append("")

    for i, q in enumerate(questions, 1):
        lines.append(f"第 {i} 题：{q.answer or '待补充'}")
        if q.solution:
            lines.append(f"      解析：{q.solution}")
        lines.append("")

    content = "\n".join(lines)

    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="sheet_{sheet_id}.txt"',
        },
    )


def _estimate_time(questions) -> int:
    """估算练习用时（分钟）"""
    time_map = {"基础": 2, "中等": 3, "挑战": 5}
    type_map = {"fill_blank": 2, "choice": 2, "problem_solving": 8, "calculation": 3}
    total = 0
    for q in questions:
        t = type_map.get(q.question_type, 3)
        d = time_map.get(q.difficulty, 3)
        total += max(t, d)
    return min(total, 35)


TYPE_ORDER = {'calculation': 0, 'fill_blank': 1, 'choice': 2, 'problem_solving': 3, 'other': 4}
TYPE_LABELS = {'calculation': '计算题', 'fill_blank': '填空题', 'choice': '选择题', 'problem_solving': '应用题', 'other': '其他'}


def _group_questions_by_type(questions):
    """将题目按题型分组排序，返回 (sorted_questions, sections)

    sections = [
      {"label": "一、计算题", "start": 0, "count": 5},
      {"label": "二、填空题", "start": 5, "count": 3},
      ...
    ]
    """
    if not questions:
        return [], []

    groups = {}
    for q in questions:
        t = q.question_type or 'other'
        if t not in groups:
            groups[t] = []
        groups[t].append(q)

    # 按指定顺序排序
    sorted_types = sorted(groups.keys(), key=lambda t: TYPE_ORDER.get(t, 99))
    sorted_qs = []
    sections = []
    numerals = ['一', '二', '三', '四', '五', '六', '七']
    idx = 0
    for t in sorted_types:
        group = groups[t]
        label = TYPE_LABELS.get(t, t)
        sections.append({
            "label": f"{numerals[idx] if idx < len(numerals) else idx + 1}、{label}",
            "start": len(sorted_qs),
            "count": len(group),
        })
        idx += 1
        sorted_qs.extend(group)

    return sorted_qs, sections


# ========== 一周4天练习单生成（学期模式） ==========

GEO_KPS = ['几何面积', '圆柱与圆锥', '立体几何']


def _select_day_questions(db, day_kps, used_ids):
    """为一天选题：7-10题，含填空3-4+选择2-3+解决问题2-3（至少1道几何）"""
    candidates = db.query(Question).filter(
        Question.knowledge_point.in_(day_kps)
    ).all()
    candidates = [q for q in candidates if q.question_id not in used_ids]

    # 当天KPs不够时，放宽到所有题目
    if len(candidates) < 7:
        fallback = db.query(Question).all()
        candidates = [q for q in fallback if q.question_id not in used_ids]

    if not candidates:
        return []

    # 按题型分组
    fill_blank = [q for q in candidates if q.question_type == 'fill_blank']
    choice = [q for q in candidates if q.question_type == 'choice']
    problem_solving = [q for q in candidates if q.question_type == 'problem_solving']
    selected = []
    selected_ids = set()

    def _pick(pool, n, exclude=None):
        pool = [q for q in pool if q.question_id not in (exclude or set())]
        if not pool or n <= 0:
            return []
        n = min(n, len(pool))
        return random.sample(pool, n)

    # 1. 解决问题 - 至少1道几何
    ps_geo = [q for q in problem_solving if q.knowledge_point in GEO_KPS]
    ps_other = [q for q in problem_solving if q.knowledge_point not in GEO_KPS]
    n_ps = random.choice([2, 3])

    picked = _pick(ps_geo, 1)
    selected.extend(picked)
    selected_ids.update(q.question_id for q in picked)

    remaining = n_ps - len(picked)
    if remaining > 0:
        picked = _pick(ps_other, remaining, selected_ids)
        selected.extend(picked)
        selected_ids.update(q.question_id for q in picked)

    # 仍不够解决问题时从全部pool补
    missing_ps = 2 - len([q for q in selected if q.question_type == 'problem_solving'])
    if missing_ps > 0:
        picked = _pick(problem_solving, missing_ps, selected_ids)
        selected.extend(picked)
        selected_ids.update(q.question_id for q in picked)

    # 2. 填空题 3-4道
    n_fb = min(random.choice([3, 4]), len(fill_blank))
    picked = _pick(fill_blank, n_fb, selected_ids)
    selected.extend(picked)
    selected_ids.update(q.question_id for q in picked)

    # 3. 选择题 2-3道
    n_ch = min(random.choice([2, 3]), len(choice))
    picked = _pick(choice, n_ch, selected_ids)
    selected.extend(picked)
    selected_ids.update(q.question_id for q in picked)

    # 补到至少7题
    remaining_all = [q for q in candidates if q.question_id not in selected_ids]
    while len(selected) < 7 and remaining_all:
        q = remaining_all.pop(random.randrange(len(remaining_all)))
        selected.append(q)
        selected_ids.add(q.question_id)

    # 上限10题
    if len(selected) > 10:
        selected = selected[:10]

    random.shuffle(selected)
    return selected


@router.post("/generate-week")
def generate_week_sheets(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """生成一周4天练习单（学期模式：周一到周四）"""
    # 1. 获取掌握度数据
    mastery_list = db.query(UserKnowledgeMastery).filter(
        UserKnowledgeMastery.user_id == user_id
    ).all()

    # 2. 知识点分类
    weak_kps = []    # 完全不懂 < 40%
    medium_kps = []  # 懂一部分 40-70%
    mastered_kps = []  # 已掌握 >= 70%

    recorded_kps = set()
    for m in mastery_list:
        rate = float(m.mastery_rate or 0)
        kp = m.knowledge_point
        recorded_kps.add(kp)
        if rate < 40 or m.is_weak_point:
            weak_kps.append(kp)
        elif rate < 70:
            medium_kps.append(kp)
        else:
            mastered_kps.append(kp)

    # 补充有题目但无掌握度记录的知识点
    all_db_kps = [r[0] for r in db.query(Question.knowledge_point).distinct().all()]
    for kp in all_db_kps:
        if kp not in recorded_kps:
            medium_kps.append(kp)

    # 3. 最近3天去重
    recent_cutoff = date.today() - timedelta(days=3)
    recent_ids = set(
        r[0] for r in db.query(UserPracticeHistory.question_id).filter(
            UserPracticeHistory.user_id == user_id,
            UserPracticeHistory.practice_date >= recent_cutoff,
        ).all()
    )
    used_globally = set(recent_ids)

    # 4. 4天规划
    def _pick_kps(pool, count):
        if not pool:
            return []
        return random.sample(pool, min(count, len(pool)))

    day_plans = [
        ("周一", weak_kps + _pick_kps(medium_kps, max(2, 3 - len(weak_kps)))),
        ("周二", medium_kps + _pick_kps(weak_kps, 1) + _pick_kps(mastered_kps, 1)),
        ("周三", weak_kps + medium_kps + _pick_kps(mastered_kps, 1)),
        ("周四", mastered_kps + _pick_kps(medium_kps, 2) + _pick_kps(weak_kps, 1)),
    ]

    # 确保每天都有知识点
    for i, (label, kps) in enumerate(day_plans):
        if not kps:
            day_plans[i] = (label, all_db_kps)

    # 计算当前周信息
    today = date.today()
    # 本周一
    week_start = today - timedelta(days=today.weekday())
    week_number = week_start.isocalendar()[1]

    results = []
    for day_label, kps in day_plans:
        questions = _select_day_questions(db, kps, used_globally)
        if not questions:
            continue

        for q in questions:
            used_globally.add(q.question_id)

        sheet_name = f"{week_start.isoformat()} 第{week_number}周 {day_label}练习单"
        time_est = _estimate_time(questions)

        sheet = PracticeSheet(
            user_id=user_id,
            sheet_name=sheet_name,
            sheet_type=SheetType.daily,
            total_questions=len(questions),
            estimated_time=time_est,
        )
        db.add(sheet)
        db.flush()

        for i, q in enumerate(questions):
            sq = SheetQuestion(
                sheet_id=sheet.sheet_id,
                question_id=q.question_id,
                question_order=i + 1,
            )
            db.add(sq)
            ph = UserPracticeHistory(
                user_id=user_id,
                question_id=q.question_id,
                practice_date=date.today(),
                practice_type=PracticeType.daily,
                sheet_id=sheet.sheet_id,
            )
            db.add(ph)

        results.append(DaySheetOut(
            day_label=day_label,
            sheet=PracticeSheetOut(
                sheet_id=sheet.sheet_id,
                sheet_name=sheet.sheet_name,
                sheet_type=sheet.sheet_type,
                total_questions=sheet.total_questions,
                estimated_time=sheet.estimated_time,
                generated_date=sheet.generated_date,
                questions=[QuestionOut.model_validate(q) for q in questions],
            ),
        ))

    if not results:
        raise HTTPException(status_code=400, detail="没有符合条件的题目生成练习单")

    db.commit()

    week_end = week_start + timedelta(days=3)
    return GenerateWeekResponse(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        total_questions=sum(r.sheet.total_questions for r in results),
        total_time=sum(r.sheet.estimated_time or 0 for r in results),
        sheets=results,
    )


# ========== 错题重练生成（2计算 + 3原题重做 + 2举一反三） ==========

def _pick_random(pool, n, exclude=None):
    """从pool随机选n个，排除exclude中的ID"""
    pool = [q for q in pool if q.question_id not in (exclude or set())]
    if not pool or n <= 0:
        return []
    n = min(n, len(pool))
    return random.sample(pool, n)


@router.post("/generate-redo")
def generate_redo_sheet(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """生成错题重练练习单：2道计算题 + 3道原题重做 + 2道举一反三"""
    # 1. 获取未掌握的错题
    wrong_records = (
        db.query(UserWrongQuestion)
        .filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.mastered == False,
        )
        .order_by(UserWrongQuestion.created_date.desc())
        .all()
    )
    if not wrong_records:
        raise HTTPException(status_code=400, detail="暂无待巩固的错题")

    wrong_questions = []
    for rec in wrong_records:
        q = db.query(Question).filter(Question.question_id == rec.question_id).first()
        if q:
            wrong_questions.append(q)

    if not wrong_questions:
        raise HTTPException(status_code=400, detail="暂无待巩固的错题")

    used_ids = set()

    # 2. 计算题：选2道计算题
    calc_candidates = (
        db.query(Question)
        .filter(Question.question_type == 'calculation')
        .all()
    )
    calc_selected = _pick_random(calc_candidates, 2)
    for q in calc_selected:
        used_ids.add(q.question_id)

    # 3. 错题重做：选3道错题
    redo_selected = _pick_random(wrong_questions, 3, used_ids)
    for q in redo_selected:
        used_ids.add(q.question_id)

    # 如果错题不够3道，从已有的尽量选
    if len(redo_selected) < 3:
        more = _pick_random(wrong_questions, 3 - len(redo_selected), used_ids)
        redo_selected.extend(more)
        for q in more:
            used_ids.add(q.question_id)

    # 4. 举一反三：从错题的知识点中选同知识点其他题
    redo_kps = list(set(q.knowledge_point for q in redo_selected if q.knowledge_point))
    variant_candidates = []
    if redo_kps:
        variant_candidates = (
            db.query(Question)
            .filter(
                Question.knowledge_point.in_(redo_kps),
                Question.question_id.notin_(used_ids),
            )
            .all()
        )
    variant_selected = _pick_random(variant_candidates, 2)

    # 如果举一反三不够，从同类别补充
    if len(variant_selected) < 2:
        redo_cats = list(set(
            q.knowledge_category for q in redo_selected
            if q.knowledge_category
        ))
        if redo_cats:
            more_variants = (
                db.query(Question)
                .filter(
                    Question.knowledge_category.in_(redo_cats),
                    Question.question_id.notin_(used_ids),
                )
                .all()
            )
            more = _pick_random(more_variants, 2 - len(variant_selected))
            variant_selected.extend(more)
            for q in more:
                used_ids.add(q.question_id)

    # 5. 合并：计算题在前，错题重做中间，举一反三最后
    all_selected = calc_selected + redo_selected + variant_selected
    if not all_selected:
        raise HTTPException(status_code=400, detail="没有符合条件的题目")

    time_est = _estimate_time(all_selected)
    sheet_name = _default_practice_sheet_name("wrong_redo")

    sheet = PracticeSheet(
        user_id=user_id,
        sheet_name=sheet_name,
        sheet_type=SheetType.wrong_redo,
        total_questions=len(all_selected),
        estimated_time=time_est,
    )
    db.add(sheet)
    db.flush()

    for i, q in enumerate(all_selected):
        sq = SheetQuestion(
            sheet_id=sheet.sheet_id,
            question_id=q.question_id,
            question_order=i + 1,
        )
        db.add(sq)
        ph = UserPracticeHistory(
            user_id=user_id,
            question_id=q.question_id,
            practice_date=date.today(),
            practice_type=PracticeType.wrong_redo,
            sheet_id=sheet.sheet_id,
        )
        db.add(ph)

    db.commit()

    sheet_out = PracticeSheetOut(
        sheet_id=sheet.sheet_id,
        sheet_name=sheet.sheet_name,
        sheet_type=sheet.sheet_type,
        total_questions=sheet.total_questions,
        estimated_time=sheet.estimated_time,
        generated_date=sheet.generated_date,
        questions=[QuestionOut.model_validate(q) for q in all_selected],
    )
    resp = sheet_out.model_dump()
    sections_data = [
        {"label": "一、计算题", "start": 0, "count": len(calc_selected)},
        {"label": "二、错题重做", "start": len(calc_selected), "count": len(redo_selected)},
        {"label": "三、举一反三", "start": len(calc_selected) + len(redo_selected), "count": len(variant_selected)},
    ]
    resp["_sections"] = sections_data
    # 持久化分区信息
    sheet.sections_json = json.dumps(sections_data, ensure_ascii=False)
    db.commit()
    return resp


# ========== 智慧推荐错题功能 ==========


def _calculate_redo_score(record, question, mastery):
    """计算错题推荐分（规则评分模型）"""
    # 错误次数分
    wrong_count = (record.redo_count or 0) + 1
    wrong_count_score = min(wrong_count * 15, 100)

    # 掌握度分
    if mastery:
        mastery_score = 100 - float(mastery.mastery_rate or 0)
    else:
        mastery_score = 50

    # 遗忘风险分
    forgetting_score = mastery.forgetting_risk_score or 0 if mastery else 30

    # 最近错误分
    if record.created_date:
        cd = record.created_date
        if hasattr(cd, 'date'):
            cd = cd.date()
        days_since = (date.today() - cd).days
        recent_wrong_score = max(0, 100 - days_since * 3)
    else:
        recent_wrong_score = 30

    # 重做失败分
    redo_fail_score = (record.redo_count or 0) * 15

    # 难度分
    diff_map = {"基础": 40, "中等": 70, "挑战": 90}
    difficulty_score = diff_map.get(question.difficulty, 50)

    # 已掌握惩罚
    mastered_penalty = 80 if record.mastered else 0

    # 最近练习惩罚
    recent_penalty = 0
    if record.last_redo_date:
        lrd = record.last_redo_date
        if hasattr(lrd, 'date'):
            lrd = lrd.date()
        days_since_redo = (date.today() - lrd).days
        if days_since_redo <= 3:
            recent_penalty = 60
        elif days_since_redo <= 7:
            recent_penalty = 30

    score = (
        wrong_count_score * 0.25
        + mastery_score * 0.25
        + forgetting_score * 0.20
        + recent_wrong_score * 0.15
        + redo_fail_score * 0.10
        + difficulty_score * 0.05
        - mastered_penalty
        - recent_penalty
    )
    return max(round(score, 1), 0)


def _recommend_similar_questions(db, user_id, source_questions, count, exclude_ids=None):
    """根据错题知识点画像，从普通题库推荐举一反三题"""
    if not source_questions or count <= 0:
        return []

    kp_counts = {}
    cat_counts = {}
    for q in source_questions:
        if q.knowledge_point:
            kp_counts[q.knowledge_point] = kp_counts.get(q.knowledge_point, 0) + 1
        if q.knowledge_category:
            cat_counts[q.knowledge_category] = cat_counts.get(q.knowledge_category, 0) + 1

    top_kps = [kp for kp, _ in sorted(kp_counts.items(), key=lambda x: -x[1])]
    top_cats = [ct for ct, _ in sorted(cat_counts.items(), key=lambda x: -x[1])]

    blocked_qids = set(exclude_ids or [])
    blocked_qids.update(q.question_id for q in source_questions if q.question_id)

    candidates = []
    if top_kps:
        candidates = db.query(Question).filter(
            Question.knowledge_point.in_(top_kps),
            Question.question_id.notin_(blocked_qids),
        ).all()

    if len(candidates) < count and top_cats:
        existing = {q.question_id for q in candidates}
        more = db.query(Question).filter(
            Question.knowledge_category.in_(top_cats),
            Question.question_id.notin_(blocked_qids | existing),
        ).all()
        candidates.extend(more)

    if len(candidates) < count:
        existing = {q.question_id for q in candidates}
        more = db.query(Question).filter(
            Question.question_id.notin_(blocked_qids | existing),
        ).limit(count * 3).all()
        candidates.extend(more)

    scored = []
    for q in candidates:
        s = 0
        if q.knowledge_point in top_kps:
            s += 40
        if q.knowledge_category in top_cats:
            s += 20
        if q.difficulty:
            s += 10
        if q.is_high_freq:
            s += 10
        if q.is_classic:
            s += 10
        if q.is_key_point:
            s += 5
        scored.append((q, s))

    seen = set()
    unique = []
    for q, s in sorted(scored, key=lambda x: -x[1]):
        if q.question_id not in seen:
            seen.add(q.question_id)
            unique.append(q)
    return unique[:count]


def _supplement_questions(db, used_qids, needed, source_questions, difficulty, question_types):
    """从题库补充题目，优先选同知识点、同难度、同题型"""
    kps = list(set(q.knowledge_point for q in source_questions if q.knowledge_point))
    sup_query = db.query(Question)
    filters = []
    if kps:
        filters.append(Question.knowledge_point.in_(kps))
    if difficulty:
        filters.append(Question.difficulty.in_(difficulty))
    if question_types:
        filters.append(Question.question_type.in_(question_types))
    if filters:
        sup_query = sup_query.filter(*filters)
    sup_query = sup_query.filter(Question.question_id.notin_(used_qids))
    pool = sup_query.all()
    random.shuffle(pool)
    return pool[:needed]


@router.post("/generate-wrong-period")
def generate_wrong_period_sheet(
    req: GenerateWrongPeriodRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """按时间段生成错题练习单

    type_counts 模式：{ "calculation": 4, "fill_blank": 3, "problem_solving": 3 }
      每卷各题型固定数量，错题不够从题库补充。
    questions_per_sheet 模式：每卷固定总题数，错题不够从题库补充。
    都不设：所有错题均匀分配到各卷。
    """
    # 1. 获取时间段内的错题
    wq_query = db.query(UserWrongQuestion).filter(
        UserWrongQuestion.user_id == user_id,
        UserWrongQuestion.created_date >= req.start_date,
        UserWrongQuestion.created_date <= req.end_date,
    )
    if req.only_unmastered:
        wq_query = wq_query.filter(UserWrongQuestion.mastered == False)

    records = wq_query.order_by(UserWrongQuestion.created_date.desc()).all()

    wrong_questions = []
    seen_qids = set()
    for r in records:
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        if q and q.question_id not in seen_qids:
            if req.difficulty and q.difficulty not in req.difficulty:
                continue
            if req.question_types and q.question_type not in req.question_types:
                continue
            wrong_questions.append(q)
            seen_qids.add(q.question_id)

    n_sheets = max(1, req.sheet_count)

    if req.type_counts:
        # ===== 按题型分别定数模式 =====
        chunks = [[] for _ in range(n_sheets)]
        sheet_type_counts = [{} for _ in range(n_sheets)]
        used_qids = set(q.question_id for q in wrong_questions)
        all_supplement = []

        for qtype, cps in req.type_counts.items():
            if cps <= 0:
                continue
            needed = cps * n_sheets

            # 该题型的错题
            pool = [q for q in wrong_questions if q.question_type == qtype]

            # 不够则补充
            if len(pool) < needed:
                shortfall = needed - len(pool)
                sup = _supplement_questions(
                    db, used_qids, shortfall,
                    wrong_questions, req.difficulty, [qtype],
                )
                pool.extend(sup)
                all_supplement.extend(sup)
                for q in sup:
                    used_qids.add(q.question_id)

            random.shuffle(pool)
            for i, q in enumerate(pool):
                si = i % n_sheets
                if sheet_type_counts[si].get(qtype, 0) < cps:
                    chunks[si].append(q)
                    sheet_type_counts[si][qtype] = sheet_type_counts[si].get(qtype, 0) + 1

        supplement_count = len(all_supplement)

        if not any(chunks):
            raise HTTPException(status_code=400, detail="没有符合条件的题目")

    elif req.questions_per_sheet is not None and req.questions_per_sheet > 0:
        # ===== 每卷固定总题数模式 =====
        qps = req.questions_per_sheet
        total_needed = n_sheets * qps

        if len(wrong_questions) < total_needed:
            shortfall = total_needed - len(wrong_questions)
            supplement = _supplement_questions(
                db, seen_qids, shortfall,
                wrong_questions, req.difficulty, req.question_types,
            )
        else:
            supplement = []

        supplement_count = len(supplement)

        if not wrong_questions and not supplement:
            raise HTTPException(status_code=400, detail="没有符合条件的题目")

        all_questions = wrong_questions + supplement
        all_questions, _ = _group_questions_by_type(all_questions)
        chunks = [[] for _ in range(n_sheets)]
        for i, q in enumerate(all_questions):
            if len(chunks[i % n_sheets]) < qps:
                chunks[i % n_sheets].append(q)
    else:
        # ===== 经典模式：全部错题均匀分配 =====
        if not wrong_questions:
            raise HTTPException(status_code=400, detail="该时间段内暂无错题，请调整时间范围")

        supplement_count = 0
        all_questions, _ = _group_questions_by_type(wrong_questions)
        chunks = [[] for _ in range(n_sheets)]
        for i, q in enumerate(all_questions):
            chunks[i % n_sheets].append(q)

    # 3. 创建各卷
    created_sheets = []
    sheet_total = 0
    for ci, chunk in enumerate(chunks):
        if not chunk:
            continue
        chunk_qs, chunk_sections = _group_questions_by_type(chunk)
        time_est = _estimate_time(chunk_qs)
        suffix = f" 第{ci+1}卷" if n_sheets > 1 else ""
        sheet_name = f"{req.name}{suffix}" if req.name else _default_practice_sheet_name("wrong_redo", suffix)
        sheet = PracticeSheet(
            user_id=user_id,
            sheet_name=sheet_name,
            sheet_type=SheetType.wrong_redo,
            total_questions=len(chunk_qs),
            estimated_time=time_est,
        )
        if chunk_sections:
            sheet.sections_json = json.dumps(chunk_sections, ensure_ascii=False)
        db.add(sheet)
        db.flush()

        for i, q in enumerate(chunk_qs):
            sq = SheetQuestion(
                sheet_id=sheet.sheet_id,
                question_id=q.question_id,
                question_order=i + 1,
            )
            db.add(sq)
            ph = UserPracticeHistory(
                user_id=user_id,
                question_id=q.question_id,
                practice_date=date.today(),
                practice_type=PracticeType.wrong_redo,
                sheet_id=sheet.sheet_id,
            )
            db.add(ph)

        sheet_data = PracticeSheetOut(
            sheet_id=sheet.sheet_id,
            sheet_name=sheet.sheet_name,
            sheet_type=sheet.sheet_type,
            total_questions=sheet.total_questions,
            estimated_time=sheet.estimated_time,
            generated_date=sheet.generated_date,
            questions=[QuestionOut.model_validate(q) for q in chunk_qs],
        )
        resp = sheet_data.model_dump()
        if chunk_sections:
            resp["_sections"] = chunk_sections
        created_sheets.append(resp)
        sheet_total += len(chunk_qs)

    if not created_sheets:
        raise HTTPException(status_code=400, detail="没有符合条件的题目")

    db.commit()

    return {
        "sheets": created_sheets,
        "total_count": sheet_total,
        "sheet_count": len(created_sheets),
        "supplement_count": supplement_count,
    }


@router.post("/generate-smart-redo")
def generate_smart_redo_sheet(
    req: SmartRedoRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """智慧推荐错题重练：自定义数量 + 智能推荐"""
    wq_query = db.query(UserWrongQuestion).filter(
        UserWrongQuestion.user_id == user_id,
    )
    if req.only_unmastered:
        wq_query = wq_query.filter(UserWrongQuestion.mastered == False)
    if req.start_date:
        wq_query = wq_query.filter(UserWrongQuestion.created_date >= req.start_date)
    if req.end_date:
        wq_query = wq_query.filter(UserWrongQuestion.created_date <= req.end_date)

    all_records = wq_query.order_by(UserWrongQuestion.created_date.desc()).all()
    if not all_records:
        raise HTTPException(status_code=400, detail="暂无符合条件的错题")

    wrong_pool = []
    seen = set()
    for r in all_records:
        if r.question_id in seen:
            continue
        seen.add(r.question_id)
        q = db.query(Question).filter(Question.question_id == r.question_id).first()
        if q and (not req.question_types or q.question_type in req.question_types):
            mastery = db.query(UserKnowledgeMastery).filter(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point == q.knowledge_point,
            ).first()
            wrong_pool.append((r, q, mastery))

    if not wrong_pool:
        raise HTTPException(status_code=400, detail="暂无符合条件的错题")

    # 计算推荐分
    scored_pool = []
    for r, q, m in wrong_pool:
        score = _calculate_redo_score(r, q, m)
        scored_pool.append((score, r, q, m))

    # 策略排序
    if req.strategy == "latest":
        scored_pool.sort(key=lambda x: x[1].created_date or date.min, reverse=True)
    elif req.strategy == "weak_knowledge":
        scored_pool.sort(key=lambda x: float(x[3].mastery_rate or 100) if x[3] else 100)
    elif req.strategy == "forgetting_risk":
        scored_pool.sort(key=lambda x: -(x[3].forgetting_risk_score or 0) if x[3] else 0)
    else:
        scored_pool.sort(key=lambda x: -x[0])

    # 选择计算类错题
    calc_pool = [(s, r, q, m) for s, r, q, m in scored_pool if q.question_type == 'calculation']
    calc_selected = []
    for s, r, q, m in calc_pool:
        if len(calc_selected) >= req.calculation_count:
            break
        calc_selected.append(q)

    used_ids = {q.question_id for q in calc_selected}

    # 计算题不足时补充
    calc_shortfall = req.calculation_count - len(calc_selected)
    calc_supplement = []
    if calc_shortfall > 0:
        # 从错题的知识点中找同知识点计算题补充
        pool_kps = list(set(q.knowledge_point for _, _, q, _ in scored_pool if q.knowledge_point))
        if pool_kps:
            supplement = db.query(Question).filter(
                Question.question_type == 'calculation',
                Question.knowledge_point.in_(pool_kps),
                Question.question_id.notin_(used_ids),
            ).limit(calc_shortfall).all()
            calc_supplement.extend(supplement)
            used_ids.update(q.question_id for q in supplement)

    # 选择原错题（排除已选）
    wrong_selected = []
    for s, r, q, m in scored_pool:
        if q.question_id in used_ids:
            continue
        if len(wrong_selected) >= req.wrong_question_count:
            break
        wrong_selected.append(q)
        used_ids.add(q.question_id)

    # 推荐举一反三
    all_source = calc_selected + calc_supplement + wrong_selected
    similar_selected = _recommend_similar_questions(
        db, user_id, all_source, req.similar_question_count, exclude_ids=used_ids,
    )

    # 合并
    final_questions = calc_selected + calc_supplement + wrong_selected + similar_selected
    if not final_questions:
        raise HTTPException(status_code=400, detail="没有符合条件的题目")

    time_est = _estimate_time(final_questions)
    sheet_name = req.name or _default_practice_sheet_name("wrong_redo")

    sheet = PracticeSheet(
        user_id=user_id,
        sheet_name=sheet_name,
        sheet_type=SheetType.wrong_redo,
        total_questions=len(final_questions),
        estimated_time=time_est,
    )
    db.add(sheet)
    db.flush()

    for i, q in enumerate(final_questions):
        sq = SheetQuestion(
            sheet_id=sheet.sheet_id,
            question_id=q.question_id,
            question_order=i + 1,
        )
        db.add(sq)
        ph = UserPracticeHistory(
            user_id=user_id,
            question_id=q.question_id,
            practice_date=date.today(),
            practice_type=PracticeType.wrong_redo,
            sheet_id=sheet.sheet_id,
        )
        db.add(ph)

    # 分区信息
    off1 = len(calc_selected)
    off2 = off1 + len(calc_supplement)
    off3 = off2 + len(wrong_selected)
    sections_data = []
    idx = 1
    numerals = ['一', '二', '三', '四', '五', '六']
    if calc_selected:
        sections_data.append({"label": f"{numerals[idx-1]}、计算巩固", "start": 0, "count": len(calc_selected)})
        idx += 1
    if calc_supplement:
        sections_data.append({"label": f"{numerals[idx-1]}、补充计算题", "start": off1, "count": len(calc_supplement)})
        idx += 1
    if wrong_selected:
        sections_data.append({"label": f"{numerals[idx-1]}、原错题重练", "start": off2, "count": len(wrong_selected)})
        idx += 1
    if similar_selected:
        sections_data.append({"label": f"{numerals[idx-1]}、举一反三", "start": off3, "count": len(similar_selected)})
    sheet.sections_json = json.dumps(sections_data, ensure_ascii=False)
    db.commit()

    resp = PracticeSheetOut(
        sheet_id=sheet.sheet_id,
        sheet_name=sheet.sheet_name,
        sheet_type=sheet.sheet_type,
        total_questions=sheet.total_questions,
        estimated_time=sheet.estimated_time,
        generated_date=sheet.generated_date,
        questions=[QuestionOut.model_validate(q) for q in final_questions],
    )
    data = resp.model_dump()
    data["_sections"] = sections_data
    return data


@router.post("/generate-selected-wrongs")
def generate_selected_wrong_sheet(
    req: SelectedWrongPracticeRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """根据用户手动勾选的错题生成原题/举一反三/混合练习单。"""
    mode = req.mode if req.mode in {"original", "similar", "mixed"} else "mixed"
    records = (
        db.query(UserWrongQuestion)
        .filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.record_id.in_(req.record_ids),
        )
        .all()
    )
    if not records:
        raise HTTPException(status_code=400, detail="请先选择要练习的错题")

    record_order = {record_id: index for index, record_id in enumerate(req.record_ids)}
    records.sort(key=lambda item: record_order.get(item.record_id, 9999))
    record_question_pairs = []
    for record in records:
        question = db.query(Question).filter(Question.question_id == record.question_id).first()
        if question:
            record_question_pairs.append((record, question))

    if not record_question_pairs:
        raise HTTPException(status_code=400, detail="所选错题没有对应题目")

    original_questions = [question for _, question in record_question_pairs]
    selected = []
    sections_data = []
    source_map = []
    used_ids = set()
    if mode in {"original", "mixed"}:
        selected.extend(original_questions)
        used_ids.update(q.question_id for q in original_questions)
        source_map.extend([
            {
                "question_id": question.question_id,
                "source": "wrong_original",
                "source_wrong_question_id": question.question_id,
                "source_record_id": record.record_id,
            }
            for record, question in record_question_pairs
        ])
        sections_data.append({"label": "一、错题原题重练", "start": 0, "count": len(original_questions)})

    similar_questions = []
    if mode in {"similar", "mixed"} and req.similar_per_wrong > 0:
        for record, source_question in record_question_pairs:
            recommendations = _recommend_similar_questions(
                db,
                user_id,
                [source_question],
                req.similar_per_wrong,
                exclude_ids=used_ids,
            )
            for recommendation in recommendations:
                similar_questions.append(recommendation)
                used_ids.add(recommendation.question_id)
                source_map.append({
                    "question_id": recommendation.question_id,
                    "source": "similar_existing",
                    "source_wrong_question_id": source_question.question_id,
                    "source_record_id": record.record_id,
                })
        if similar_questions:
            sections_data.append({
                "label": "二、举一反三迁移练习" if sections_data else "一、举一反三迁移练习",
                "start": len(selected),
                "count": len(similar_questions),
            })
            selected.extend(similar_questions)

    if not selected:
        raise HTTPException(status_code=400, detail="没有可生成的练习题")

    sheet_name = req.name or _default_practice_sheet_name("wrong_redo")
    sheet = PracticeSheet(
        user_id=user_id,
        sheet_name=sheet_name,
        sheet_type=SheetType.wrong_redo,
        total_questions=len(selected),
        estimated_time=_estimate_time(selected),
    )
    if sections_data:
        sheet.sections_json = json.dumps(sections_data, ensure_ascii=False)
    db.add(sheet)
    db.flush()

    for index, question in enumerate(selected, start=1):
        db.add(SheetQuestion(
            sheet_id=sheet.sheet_id,
            question_id=question.question_id,
            question_order=index,
        ))
        db.add(UserPracticeHistory(
            user_id=user_id,
            question_id=question.question_id,
            practice_date=date.today(),
            practice_type=PracticeType.wrong_redo,
            sheet_id=sheet.sheet_id,
        ))

    db.commit()
    db.refresh(sheet)

    data = PracticeSheetOut(
        sheet_id=sheet.sheet_id,
        sheet_name=sheet.sheet_name,
        sheet_type=sheet.sheet_type,
        total_questions=sheet.total_questions,
        estimated_time=sheet.estimated_time,
        generated_date=sheet.generated_date,
        questions=[QuestionOut.model_validate(q) for q in selected],
    ).model_dump()
    data["_sections"] = sections_data
    data["_source_summary"] = {
        "original_count": len(original_questions) if mode in {"original", "mixed"} else 0,
        "similar_count": len(similar_questions),
        "selected_wrong_count": len(original_questions),
    }
    data["_source_map"] = source_map
    return data


# ========== 标记练习单为已完成（手工批改模式） ==========


@router.post("/sheets/{sheet_id}/complete")
def mark_sheet_complete(
    sheet_id: int,
    req: MarkSheetRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """手工对错标记后提交，标记练习单为已完成，更新掌握度"""
    sheet = db.query(PracticeSheet).filter(
        PracticeSheet.sheet_id == sheet_id,
        PracticeSheet.user_id == user_id,
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="练习单不存在")
    if sheet.completed:
        raise HTTPException(status_code=400, detail="该练习单已标记为已完成")

    # 获取题目的 SQL 映射
    sqs = db.query(SheetQuestion).filter(
        SheetQuestion.sheet_id == sheet_id
    ).order_by(SheetQuestion.question_order).all()
    sq_map = {sq.question_id: sq for sq in sqs}

    mark_map = {m.question_id: m for m in req.marks}
    missing_question_ids = [sq.question_id for sq in sqs if sq.question_id not in mark_map]
    if missing_question_ids:
        raise HTTPException(
            status_code=400,
            detail=f"还有 {len(missing_question_ids)} 道题未标记，请全部标记后再提交",
        )

    correct_count = 0
    wrong_ids = []

    for sq in sqs:
        q = db.query(Question).filter(Question.question_id == sq.question_id).first()
        if not q:
            continue

        mark = mark_map[q.question_id]
        is_correct = mark.is_correct

        if is_correct:
            correct_count += 1
        else:
            wrong_ids.append(q.question_id)

        # 记录到 sheet_question
        sq.is_correct = is_correct

        # 记录练习历史
        ph = db.query(UserPracticeHistory).filter(
            UserPracticeHistory.user_id == user_id,
            UserPracticeHistory.question_id == q.question_id,
            UserPracticeHistory.sheet_id == sheet_id,
        ).first()
        if ph:
            ph.is_correct = is_correct

        # 更新知识点掌握度
        _update_mastery_kp(user_id, q.knowledge_point, is_correct, db)

    # 把错题自动加入错题本
    from ..models import UserWrongQuestion, ErrorType
    for qid in wrong_ids:
        existing = db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.question_id == qid,
        ).first()
        mark = mark_map.get(qid)
        error_type = mark.error_type if mark else None
        if not existing:
            wq = UserWrongQuestion(
                user_id=user_id,
                question_id=qid,
                exam_name=sheet.sheet_name,
                exam_date=date.today(),
                is_correct=False,
                mastered=False,
                error_type=error_type,
            )
            db.add(wq)

    # 更新练习单状态
    total = len(sqs)
    score = round(correct_count / total * 100, 1) if total > 0 else 0
    sheet.completed = True
    sheet.completed_date = datetime.now()
    sheet.score = score

    db.commit()

    return {
        "sheet_id": sheet_id,
        "total": total,
        "correct_count": correct_count,
        "wrong_count": total - correct_count,
        "score": score,
        "wrong_question_ids": wrong_ids,
    }


# ========== 提交批改 ==========

def _normalize_answer(text: str) -> str:
    """标准化答案用于比较：去空格/标点/大小写"""
    import re
    text = re.sub(r'[\s,，。、；;：:""''（）()【】\[\]{}]', '', str(text or ''))
    return text.lower().strip()


@router.post("/sheets/{sheet_id}/submit")
def submit_sheet(
    sheet_id: int,
    req: SubmitSheetRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """提交练习单答案并自动批改"""
    sheet = db.query(PracticeSheet).filter(
        PracticeSheet.sheet_id == sheet_id,
        PracticeSheet.user_id == user_id,
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="练习单不存在")
    if sheet.completed:
        raise HTTPException(status_code=400, detail="该练习单已提交过")

    # 获取题目映射
    sqs = db.query(SheetQuestion).filter(
        SheetQuestion.sheet_id == sheet_id
    ).order_by(SheetQuestion.question_order).all()
    sq_map = {sq.question_id: sq for sq in sqs}

    answer_map = {a.question_id: a for a in req.answers}

    results = []
    correct_count = 0
    wrong_ids = []

    for sq in sqs:
        q = db.query(Question).filter(Question.question_id == sq.question_id).first()
        if not q:
            continue

        user_ans = answer_map.get(q.question_id)
        user_text = user_ans.user_answer if user_ans else ""

        # 答案比较
        is_correct = False
        if q.answer:
            norm_user = _normalize_answer(user_text)
            norm_correct = _normalize_answer(q.answer)
            is_correct = norm_user == norm_correct

        if is_correct:
            correct_count += 1
        else:
            wrong_ids.append(q.question_id)

        # 记录到sheet_question
        sq.user_answer = user_text
        sq.is_correct = is_correct

        # 记录练习历史
        ph = db.query(UserPracticeHistory).filter(
            UserPracticeHistory.user_id == user_id,
            UserPracticeHistory.question_id == q.question_id,
            UserPracticeHistory.sheet_id == sheet_id,
        ).first()
        if ph:
            ph.is_correct = is_correct

        # 更新知识点掌握度
        _update_mastery_kp(user_id, q.knowledge_point, is_correct, db)

        results.append({
            "question_id": q.question_id,
            "question_order": sq.question_order,
            "question_text": q.question_text,
            "knowledge_point": q.knowledge_point,
            "difficulty": q.difficulty,
            "user_answer": user_text,
            "correct_answer": q.answer,
            "is_correct": is_correct,
            "solution": q.solution,
        })

    # 把错题自动加入错题本
    from ..models import UserWrongQuestion, ErrorType
    for qid in wrong_ids:
        existing = db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.question_id == qid,
        ).first()
        if not existing:
            wq = UserWrongQuestion(
                user_id=user_id,
                question_id=qid,
                exam_name=sheet.sheet_name,
                exam_date=date.today(),
                is_correct=False,
                mastered=False,
            )
            db.add(wq)

    # 更新练习单
    total = len(sqs)
    score = round(correct_count / total * 100, 1) if total > 0 else 0
    sheet.completed = True
    sheet.completed_date = datetime.now()
    sheet.score = score

    db.commit()

    return SubmitResultOut(
        sheet_id=sheet_id,
        total=total,
        correct_count=correct_count,
        wrong_count=total - correct_count,
        score=score,
        results=[QuestionResultOut(**r) for r in results],
        wrong_question_ids=wrong_ids,
    )


def _update_mastery_kp(user_id: int, knowledge_point: str, is_correct: bool, db: Session):
    """更新知识点掌握度"""
    mastery = db.query(UserKnowledgeMastery).filter(
        UserKnowledgeMastery.user_id == user_id,
        UserKnowledgeMastery.knowledge_point == knowledge_point,
    ).first()
    if not mastery:
        mastery = UserKnowledgeMastery(
            user_id=user_id,
            knowledge_point=knowledge_point,
            total_practiced=0,
            correct_count=0,
            mastery_rate=0,
            last_practiced_date=date.today(),
        )
        db.add(mastery)

    mastery.total_practiced = (mastery.total_practiced or 0) + 1
    if is_correct:
        mastery.correct_count = (mastery.correct_count or 0) + 1
    total = mastery.total_practiced or 1
    correct = mastery.correct_count or 0
    mastery.mastery_rate = round(correct / total * 100, 1)
    mastery.last_practiced_date = date.today()
    mastery.is_weak_point = (mastery.mastery_rate or 0) < 60


# ========== 上传练习单（纸质版拍照上传） ==========

@router.post("/sheets/{sheet_id}/upload")
async def upload_sheet(
    sheet_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """上传练习单图片（纸质做题后拍照上传）"""
    sheet = db.query(PracticeSheet).filter(
        PracticeSheet.sheet_id == sheet_id,
        PracticeSheet.user_id == user_id,
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="练习单不存在")

    # 确保上传目录存在
    os.makedirs(IMAGE_DIR, exist_ok=True)

    ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
    filename = f"sheet_{sheet_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(IMAGE_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "message": "上传成功",
        "filename": filename,
        "file_url": f"/uploads/images/{filename}",
        "sheet_id": sheet_id,
    }
