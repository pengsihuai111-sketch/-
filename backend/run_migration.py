"""
执行数据库索引迁移脚本
"""
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.core.config import DatabaseConfig

def execute_migration():
    """执行索引迁移"""
    # 构建数据库连接URL
    db_url = f"mysql+pymysql://{DatabaseConfig.USER}:{DatabaseConfig.PASSWORD}@{DatabaseConfig.HOST}:{DatabaseConfig.PORT}/{DatabaseConfig.DATABASE}"

    print(f"连接数据库: {DatabaseConfig.HOST}:{DatabaseConfig.PORT}/{DatabaseConfig.DATABASE}")

    # 创建引擎
    engine = create_engine(db_url, echo=True)

    # 读取迁移SQL文件
    migration_file = Path(__file__).parent / "migrations" / "add_performance_indexes.sql"

    if not migration_file.exists():
        print(f"错误: 迁移文件不存在 {migration_file}")
        return False

    print(f"\n读取迁移文件: {migration_file}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # 分割SQL语句（按行处理，过滤注释）
    lines = sql_content.split('\n')
    sql_statements = []
    current_statement = []

    for line in lines:
        line = line.strip()
        # 跳过空行和注释行
        if not line or line.startswith('--'):
            continue

        current_statement.append(line)

        # 如果行以分号结尾，表示一条完整的SQL语句
        if line.endswith(';'):
            stmt = ' '.join(current_statement).strip()
            if stmt:
                sql_statements.append(stmt)
            current_statement = []

    print(f"\n找到 {len(sql_statements)} 条SQL语句\n")

    # 执行迁移
    success_count = 0
    error_count = 0

    with engine.connect() as conn:
        for i, sql in enumerate(sql_statements, 1):
            try:
                # 提取索引名称用于显示
                if 'CREATE INDEX' in sql:
                    index_name = sql.split('CREATE INDEX IF NOT EXISTS')[1].split('ON')[0].strip()
                    print(f"[{i}/{len(sql_statements)}] 创建索引: {index_name}")

                    # 检查索引是否已存在
                    table_name = sql.split('ON')[1].split('(')[0].strip()
                    check_sql = text(f"""
                        SELECT COUNT(*) as cnt
                        FROM information_schema.statistics
                        WHERE table_schema = DATABASE()
                        AND table_name = '{table_name}'
                        AND index_name = '{index_name}'
                    """)
                    result = conn.execute(check_sql)
                    exists = result.fetchone()[0] > 0

                    if exists:
                        print(f"  [SKIP] Index already exists")
                        success_count += 1
                        continue

                    # 移除IF NOT EXISTS语法
                    sql = sql.replace('IF NOT EXISTS ', '')

                conn.execute(text(sql))
                conn.commit()
                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"  [ERROR] {str(e)}")

    print(f"\n{'='*60}")
    print(f"迁移完成!")
    print(f"  成功: {success_count} 条")
    print(f"  失败: {error_count} 条")
    print(f"{'='*60}\n")

    return error_count == 0


def verify_indexes():
    """验证索引是否创建成功"""
    db_url = f"mysql+pymysql://{DatabaseConfig.USER}:{DatabaseConfig.PASSWORD}@{DatabaseConfig.HOST}:{DatabaseConfig.PORT}/{DatabaseConfig.DATABASE}"
    engine = create_engine(db_url)

    print("\n验证索引创建情况...\n")

    tables = [
        'user_wrong_questions',
        'questions',
        'user_knowledge_mastery',
        'user_practice_history',
        'practice_sheets',
        'sheet_questions',
        'wrong_question_recognition_tasks'
    ]

    with engine.connect() as conn:
        for table in tables:
            result = conn.execute(text(f"SHOW INDEX FROM {table}"))
            indexes = result.fetchall()

            # 过滤出非主键索引
            custom_indexes = [idx for idx in indexes if idx[2] != 'PRIMARY']

            print(f"[TABLE] {table}: {len(custom_indexes)} indexes")
            for idx in custom_indexes:
                print(f"   - {idx[2]} ({idx[4]})")
            print()


if __name__ == "__main__":
    print("="*60)
    print("数据库索引迁移工具")
    print("="*60)

    try:
        # 执行迁移
        success = execute_migration()

        if success:
            # 验证索引
            verify_indexes()
            print("[SUCCESS] All indexes created successfully!")
        else:
            print("[WARNING] Some indexes failed, please check error messages")

    except Exception as e:
        print(f"\n[FAILED] Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
