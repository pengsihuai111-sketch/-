-- 性能优化：添加数据库索引
-- 生成时间: 2026-05-20
-- 说明: 为高频查询字段添加索引，提升查询性能

-- ==================== UserWrongQuestion表索引 ====================

-- 用户错题查询频繁
CREATE INDEX IF NOT EXISTS idx_user_wrong_user_id ON user_wrong_questions (user_id);

-- 题目关联查询
CREATE INDEX IF NOT EXISTS idx_user_wrong_question_id ON user_wrong_questions (question_id);

-- 按日期筛选错题
CREATE INDEX IF NOT EXISTS idx_user_wrong_created_date ON user_wrong_questions (created_date);

-- 筛选未掌握的错题
CREATE INDEX IF NOT EXISTS idx_user_wrong_mastered ON user_wrong_questions (mastered);

-- 复合索引：用户+题目去重查询
CREATE INDEX IF NOT EXISTS idx_user_wrong_user_question ON user_wrong_questions (user_id, question_id);


-- ==================== Question表索引 ====================

-- 按知识点筛选题目
CREATE INDEX IF NOT EXISTS idx_question_knowledge_point ON questions (knowledge_point);

-- 按难度筛选题目
CREATE INDEX IF NOT EXISTS idx_question_difficulty ON questions (difficulty);

-- 按题型筛选题目
CREATE INDEX IF NOT EXISTS idx_question_type ON questions (question_type);

-- 复合索引：知识点+难度组合查询
CREATE INDEX IF NOT EXISTS idx_question_kp_difficulty ON questions (knowledge_point, difficulty);


-- ==================== UserKnowledgeMastery表索引 ====================

-- 用户掌握度查询
CREATE INDEX IF NOT EXISTS idx_mastery_user_id ON user_knowledge_mastery (user_id);

-- 复合索引：用户+知识点唯一查询
CREATE INDEX IF NOT EXISTS idx_mastery_user_kp ON user_knowledge_mastery (user_id, knowledge_point);

-- 按掌握率排序查询薄弱点
CREATE INDEX IF NOT EXISTS idx_mastery_rate ON user_knowledge_mastery (mastery_rate);


-- ==================== UserPracticeHistory表索引 ====================

-- 用户练习历史查询
CREATE INDEX IF NOT EXISTS idx_practice_user_id ON user_practice_history (user_id);

-- 题目练习历史查询
CREATE INDEX IF NOT EXISTS idx_practice_question_id ON user_practice_history (question_id);

-- 按日期查询练习记录
CREATE INDEX IF NOT EXISTS idx_practice_date ON user_practice_history (practice_date);

-- 复合索引：用户+日期去重查询
CREATE INDEX IF NOT EXISTS idx_practice_user_date ON user_practice_history (user_id, practice_date);


-- ==================== PracticeSheet表索引 ====================

-- 用户练习单查询
CREATE INDEX IF NOT EXISTS idx_sheet_user_id ON practice_sheets (user_id);

-- 按类型筛选练习单
CREATE INDEX IF NOT EXISTS idx_sheet_type ON practice_sheets (sheet_type);

-- 筛选已完成/未完成练习单
CREATE INDEX IF NOT EXISTS idx_sheet_completed ON practice_sheets (completed);

-- 按生成日期排序
CREATE INDEX IF NOT EXISTS idx_sheet_generated_date ON practice_sheets (generated_date);


-- ==================== SheetQuestion表索引 ====================

-- 查询练习单的所有题目
CREATE INDEX IF NOT EXISTS idx_sheet_question_sheet_id ON sheet_questions (sheet_id);

-- 复合索引：练习单+顺序排序
CREATE INDEX IF NOT EXISTS idx_sheet_question_order ON sheet_questions (sheet_id, question_order);


-- ==================== WrongQuestionRecognitionTask表索引 ====================

-- 用户识别任务查询
CREATE INDEX IF NOT EXISTS idx_recognition_user_id ON wrong_question_recognition_tasks (user_id);

-- 按状态筛选识别任务
CREATE INDEX IF NOT EXISTS idx_recognition_status ON wrong_question_recognition_tasks (status);

-- 按创建时间排序
CREATE INDEX IF NOT EXISTS idx_recognition_created_at ON wrong_question_recognition_tasks (created_at);
