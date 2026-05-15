-- ============================================================
-- 小升初数学题库管理系统 v4.0 数据库表结构
-- Database: question_bank_v4
-- ============================================================

-- 1. 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20),
    real_name VARCHAR(50),
    grade_level VARCHAR(20) COMMENT '年级',
    member_type ENUM('free', 'basic', 'premium') DEFAULT 'free',
    member_expire_date DATETIME,
    register_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    status ENUM('active', 'suspended') DEFAULT 'active',
    INDEX idx_username (username),
    INDEX idx_member (member_type, member_expire_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 2. 题库主表
CREATE TABLE IF NOT EXISTS questions (
    question_id INT PRIMARY KEY AUTO_INCREMENT,
    q_id VARCHAR(50) UNIQUE NOT NULL COMMENT '兼容v3 ID，如 EW_几何面积_001',
    knowledge_point VARCHAR(100) NOT NULL COMMENT '知识点',
    knowledge_category VARCHAR(50) COMMENT '分片类别：几何/方程与应用/计算/数论/逻辑/基础/其他',
    question_type ENUM('fill_blank', 'choice', 'problem_solving', 'calculation') COMMENT '题型',
    difficulty ENUM('基础', '中等', '挑战'),
    question_text TEXT NOT NULL,
    answer TEXT COMMENT '答案',
    solution TEXT COMMENT '解析',
    has_image BOOLEAN DEFAULT FALSE,
    image_path VARCHAR(255),
    image_caption VARCHAR(255),
    source_school VARCHAR(100) COMMENT '来源学校',
    source_exam VARCHAR(100) COMMENT '来源套卷',
    source_number VARCHAR(50) COMMENT '题号',
    exam_year VARCHAR(10),
    is_key_point BOOLEAN DEFAULT FALSE,
    is_difficult BOOLEAN DEFAULT FALSE,
    is_high_freq BOOLEAN DEFAULT FALSE,
    is_classic BOOLEAN DEFAULT FALSE,
    verification_status ENUM('pending', 'ai_generated', 'verified', 'needs_review') DEFAULT 'pending',
    variation_of INT COMMENT '变式题关联question_id',
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_date DATETIME ON UPDATE CURRENT_TIMESTAMP,
    global_usage_count INT DEFAULT 0,
    INDEX idx_knowledge (knowledge_point),
    INDEX idx_category (knowledge_category),
    INDEX idx_difficulty (difficulty),
    INDEX idx_qid (q_id),
    FULLTEXT idx_question_text (question_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='题库主表';

-- 3. 用户错题表
CREATE TABLE IF NOT EXISTS user_wrong_questions (
    record_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    question_id INT NOT NULL,
    exam_name VARCHAR(100) COMMENT '考试名称',
    exam_date DATE,
    is_correct BOOLEAN DEFAULT FALSE,
    error_type ENUM('概念错误', '计算错误', '审题错误', '方法错误', '其他'),
    redo_count INT DEFAULT 0,
    last_redo_date DATE,
    mastered BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id),
    INDEX idx_user_question (user_id, question_id),
    INDEX idx_user_mastered (user_id, mastered)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户错题表';

-- 4. 用户知识点掌握度表
CREATE TABLE IF NOT EXISTS user_knowledge_mastery (
    mastery_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    knowledge_point VARCHAR(100) NOT NULL,
    total_practiced INT DEFAULT 0,
    correct_count INT DEFAULT 0,
    mastery_rate DECIMAL(5,2) COMMENT '掌握率 0-100',
    last_practiced_date DATE,
    forgetting_risk_score INT DEFAULT 0 COMMENT '遗忘风险分 0-100',
    is_weak_point BOOLEAN DEFAULT FALSE,
    updated_date DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_kp (user_id, knowledge_point),
    INDEX idx_weak (user_id, is_weak_point)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识点掌握度表';

-- 5. 用户练习历史表
CREATE TABLE IF NOT EXISTS user_practice_history (
    history_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    question_id INT NOT NULL,
    practice_date DATE NOT NULL,
    is_correct BOOLEAN,
    time_spent INT COMMENT '用时(秒)',
    practice_type ENUM('daily', 'wrong_redo', 'special_topic', 'exam'),
    sheet_id INT COMMENT '关联练习单ID',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id),
    INDEX idx_user_date (user_id, practice_date),
    INDEX idx_question (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='练习历史表';

-- 6. 练习单表
CREATE TABLE IF NOT EXISTS practice_sheets (
    sheet_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    sheet_name VARCHAR(100),
    sheet_type ENUM('daily', 'wrong_redo', 'special_topic', 'custom'),
    total_questions INT,
    estimated_time INT COMMENT '预计用时(分钟)',
    generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT FALSE,
    completed_date DATETIME,
    score DECIMAL(5,2),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_type (user_id, sheet_type),
    INDEX idx_date (generated_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='练习单表';

-- 7. 练习单题目关联表
CREATE TABLE IF NOT EXISTS sheet_questions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sheet_id INT NOT NULL,
    question_id INT NOT NULL,
    question_order INT COMMENT '题目序号',
    is_correct BOOLEAN,
    user_answer TEXT,
    FOREIGN KEY (sheet_id) REFERENCES practice_sheets(sheet_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id),
    INDEX idx_sheet (sheet_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='练习单题目关联表';

-- 8. 会员订单表
CREATE TABLE IF NOT EXISTS member_orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    order_no VARCHAR(50) UNIQUE NOT NULL,
    member_type ENUM('basic', 'premium'),
    duration_months INT,
    amount DECIMAL(10,2),
    payment_method ENUM('wechat', 'alipay', 'balance'),
    payment_status ENUM('pending', 'paid', 'failed', 'refunded') DEFAULT 'pending',
    transaction_id VARCHAR(100),
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    paid_date DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_order_no (order_no),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会员订单表';

-- 9. 题目查重索引表
CREATE TABLE IF NOT EXISTS question_dedup_index (
    dedup_id INT PRIMARY KEY AUTO_INCREMENT,
    question_id INT NOT NULL,
    text_fingerprint VARCHAR(64) COMMENT 'SHA256指纹',
    source_key VARCHAR(200) COMMENT '学校_考试_题号',
    similarity_group INT COMMENT '相似题组ID',
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE KEY uk_source (source_key),
    INDEX idx_fingerprint (text_fingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='查重索引表';

-- 10. 学习记录表 (艾宾浩斯遗忘曲线)
CREATE TABLE IF NOT EXISTS user_learning_records (
    record_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    knowledge_point VARCHAR(100) NOT NULL,
    learn_date DATE NOT NULL,
    recall_score INT COMMENT '回忆分 1-5',
    next_review_date DATE COMMENT '下次复习日期',
    review_interval INT COMMENT '当前间隔天数',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_review (user_id, next_review_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='遗忘曲线学习记录';

-- 11. 错题识别任务表 (带批改痕迹识别)
CREATE TABLE IF NOT EXISTS wrong_question_recognition_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    file_url VARCHAR(500) NOT NULL COMMENT '原始文件URL',
    file_type VARCHAR(30) COMMENT 'image/pdf',
    recognition_mode VARCHAR(50) COMMENT 'normal/corrected_paper/auto',
    status VARCHAR(30) DEFAULT 'pending' COMMENT 'pending/processing/need_confirm/confirmed/failed',
    page_count INT DEFAULT 1,
    raw_result JSON NULL COMMENT 'AI分析原始结果',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_task (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='错题识别任务表';

-- 12. 错题识别题块表 (每道题一个块)
CREATE TABLE IF NOT EXISTS wrong_question_recognition_blocks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id INT NOT NULL,
    page_no INT NOT NULL DEFAULT 1,
    question_no VARCHAR(20) COMMENT '题号',
    bbox JSON NULL COMMENT '坐标 [x1,y1,x2,y2]',
    crop_image_url VARCHAR(500) COMMENT '裁剪图URL',
    clean_crop_image_url VARCHAR(500) COMMENT '清洗后裁剪图URL',
    ai_question_text TEXT COMMENT 'AI识别题干',
    ai_question_type VARCHAR(50) COMMENT '题型',
    ai_knowledge_points JSON NULL COMMENT '知识点列表',
    ai_difficulty VARCHAR(20) COMMENT '难度',
    ai_keywords JSON NULL COMMENT '关键词列表',
    ai_confidence INT COMMENT 'AI置信度 0-100',
    matched_question_id INT NULL COMMENT '匹配的题库ID',
    match_confidence INT COMMENT '匹配置信度 0-100',
    status VARCHAR(30) DEFAULT 'need_confirm' COMMENT 'need_confirm/confirmed/skipped',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES wrong_question_recognition_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (matched_question_id) REFERENCES questions(question_id),
    INDEX idx_task (task_id),
    INDEX idx_match (matched_question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='识别题块表';

-- 扩展 user_wrong_questions 表 (如未添加)
ALTER TABLE user_wrong_questions
    ADD COLUMN IF NOT EXISTS original_image_url VARCHAR(500) NULL COMMENT '原始错题图片',
    ADD COLUMN IF NOT EXISTS clean_image_url VARCHAR(500) NULL COMMENT '清洗后的识别图片',
    ADD COLUMN IF NOT EXISTS crop_image_url VARCHAR(500) NULL COMMENT '错题裁剪图片',
    ADD COLUMN IF NOT EXISTS recognition_task_id INT NULL COMMENT '识别任务ID',
    ADD COLUMN IF NOT EXISTS ai_confidence INT NULL COMMENT 'AI识别置信度 0-100';
