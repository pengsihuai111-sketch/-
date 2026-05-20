"""
数据库索引优化脚本
添加关键字段的索引以提升查询性能
"""

# 索引优化建议
INDEXES = [
    # UserWrongQuestion表索引
    {
        "table": "user_wrong_questions",
        "name": "idx_user_wrong_user_id",
        "columns": ["user_id"],
        "reason": "用户错题查询频繁"
    },
    {
        "table": "user_wrong_questions",
        "name": "idx_user_wrong_question_id",
        "columns": ["question_id"],
        "reason": "题目关联查询"
    },
    {
        "table": "user_wrong_questions",
        "name": "idx_user_wrong_created_date",
        "columns": ["created_date"],
        "reason": "按日期筛选错题"
    },
    {
        "table": "user_wrong_questions",
        "name": "idx_user_wrong_mastered",
        "columns": ["mastered"],
        "reason": "筛选未掌握的错题"
    },
    {
        "table": "user_wrong_questions",
        "name": "idx_user_wrong_user_question",
        "columns": ["user_id", "question_id"],
        "reason": "复合索引：用户+题目去重查询"
    },

    # Question表索引
    {
        "table": "questions",
        "name": "idx_question_knowledge_point",
        "columns": ["knowledge_point"],
        "reason": "按知识点筛选题目"
    },
    {
        "table": "questions",
        "name": "idx_question_difficulty",
        "columns": ["difficulty"],
        "reason": "按难度筛选题目"
    },
    {
        "table": "questions",
        "name": "idx_question_type",
        "columns": ["question_type"],
        "reason": "按题型筛选题目"
    },
    {
        "table": "questions",
        "name": "idx_question_kp_difficulty",
        "columns": ["knowledge_point", "difficulty"],
        "reason": "复合索引：知识点+难度组合查询"
    },

    # UserKnowledgeMastery表索引
    {
        "table": "user_knowledge_mastery",
        "name": "idx_mastery_user_id",
        "columns": ["user_id"],
        "reason": "用户掌握度查询"
    },
    {
        "table": "user_knowledge_mastery",
        "name": "idx_mastery_user_kp",
        "columns": ["user_id", "knowledge_point"],
        "reason": "复合索引：用户+知识点唯一查询"
    },
    {
        "table": "user_knowledge_mastery",
        "name": "idx_mastery_rate",
        "columns": ["mastery_rate"],
        "reason": "按掌握率排序查询薄弱点"
    },

    # UserPracticeHistory表索引
    {
        "table": "user_practice_history",
        "name": "idx_practice_user_id",
        "columns": ["user_id"],
        "reason": "用户练习历史查询"
    },
    {
        "table": "user_practice_history",
        "name": "idx_practice_question_id",
        "columns": ["question_id"],
        "reason": "题目练习历史查询"
    },
    {
        "table": "user_practice_history",
        "name": "idx_practice_date",
        "columns": ["practice_date"],
        "reason": "按日期查询练习记录"
    },
    {
        "table": "user_practice_history",
        "name": "idx_practice_user_date",
        "columns": ["user_id", "practice_date"],
        "reason": "复合索引：用户+日期去重查询"
    },

    # PracticeSheet表索引
    {
        "table": "practice_sheets",
        "name": "idx_sheet_user_id",
        "columns": ["user_id"],
        "reason": "用户练习单查询"
    },
    {
        "table": "practice_sheets",
        "name": "idx_sheet_type",
        "columns": ["sheet_type"],
        "reason": "按类型筛选练习单"
    },
    {
        "table": "practice_sheets",
        "name": "idx_sheet_completed",
        "columns": ["completed"],
        "reason": "筛选已完成/未完成练习单"
    },
    {
        "table": "practice_sheets",
        "name": "idx_sheet_generated_date",
        "columns": ["generated_date"],
        "reason": "按生成日期排序"
    },

    # SheetQuestion表索引
    {
        "table": "sheet_questions",
        "name": "idx_sheet_question_sheet_id",
        "columns": ["sheet_id"],
        "reason": "查询练习单的所有题目"
    },
    {
        "table": "sheet_questions",
        "name": "idx_sheet_question_order",
        "columns": ["sheet_id", "question_order"],
        "reason": "复合索引：练习单+顺序排序"
    },

    # WrongQuestionRecognitionTask表索引
    {
        "table": "wrong_question_recognition_tasks",
        "name": "idx_recognition_user_id",
        "columns": ["user_id"],
        "reason": "用户识别任务查询"
    },
    {
        "table": "wrong_question_recognition_tasks",
        "name": "idx_recognition_status",
        "columns": ["status"],
        "reason": "按状态筛选识别任务"
    },
    {
        "table": "wrong_question_recognition_tasks",
        "name": "idx_recognition_created_at",
        "columns": ["created_at"],
        "reason": "按创建时间排序"
    },
]


def generate_sql():
    """生成创建索引的SQL语句"""
    sql_statements = []

    for idx in INDEXES:
        table = idx["table"]
        name = idx["name"]
        columns = ", ".join(idx["columns"])

        sql = f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns});"
        sql_statements.append(sql)

    return sql_statements


def generate_migration_file():
    """生成数据库迁移文件"""
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"migrations/{timestamp}_add_performance_indexes.sql"

    sql_statements = generate_sql()

    content = f"""-- 性能优化：添加数据库索引
-- 生成时间: {datetime.now().isoformat()}
-- 说明: 为高频查询字段添加索引，提升查询性能

"""

    for idx in INDEXES:
        content += f"\n-- {idx['reason']}\n"
        table = idx["table"]
        name = idx["name"]
        columns = ", ".join(idx["columns"])
        content += f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns});\n"

    return filename, content


if __name__ == "__main__":
    print("=== 数据库索引优化方案 ===\n")

    for idx in INDEXES:
        print(f"表: {idx['table']}")
        print(f"  索引名: {idx['name']}")
        print(f"  字段: {', '.join(idx['columns'])}")
        print(f"  原因: {idx['reason']}")
        print()

    print(f"\n总计: {len(INDEXES)} 个索引\n")

    print("=== SQL语句 ===\n")
    for sql in generate_sql():
        print(sql)

    print("\n=== 迁移文件 ===\n")
    filename, content = generate_migration_file()
    print(f"文件名: {filename}")
    print(f"\n内容:\n{content}")
