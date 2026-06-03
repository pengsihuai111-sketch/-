# AI 学习助手 Agent + MySQL + 向量数据库完整实现计划书

## 0. 计划书目标

本文档用于指导在当前“小升初数学题库管理与学情诊断系统 v4.0”中完整实现一个 **AI 学习助手 Agent 模块**，并将其与现有 MySQL 业务数据库、后续向量数据库能力进行融合。

本计划书不是只实现“生成练习单”，而是实现一个完整的学习智能体。

最终目标是让学生或家长可以通过 AI 助手完成：

```text
1. 生成练习单
2. 查询薄弱点
3. 查看错题
4. 生成错题重练
5. 生成举一反三
6. 讲解题目
7. 制定学习计划
8. 查看学习总结
9. 查找题库题目
10. 操作系统功能
11. 语义搜索相似题
12. 题库查重
13. 系统文档问答
```

---

## 1. 总体定位

AI 学习助手不是普通聊天机器人，而是系统的自然语言入口。

它应该做到：

```text
用户自然语言输入
    ↓
Agent 理解用户意图
    ↓
Agent 判断应该调用哪个系统工具
    ↓
工具访问 MySQL 或向量数据库
    ↓
返回结构化结果
    ↓
Agent 生成可解释回复
    ↓
前端展示聊天回复 + 功能卡片 + 可操作按钮
```

---

## 2. 最终实现效果

### 2.1 用户可以生成练习单

用户：

```text
帮我生成一套几何面积专项练习，10 题，中等难度。
```

AI 助手：

```text
我已经为你生成了一套几何面积专项练习预览，共 10 题，预计 30 分钟完成。
你可以确认生成，也可以让我换一批题或降低难度。
```

前端展示：

```text
练习单预览卡片
- 题目列表
- 题型分布
- 难度分布
- 预计用时
- 确认生成按钮
- 换一批按钮
```

---

### 2.2 用户可以查询薄弱点

用户：

```text
我最近哪里最薄弱？
```

AI 助手：

```text
根据你的练习记录和错题情况，最近薄弱点主要集中在：
1. 几何面积
2. 分数混合运算
3. 方程应用题

建议你先做基础巩固，再做错题重练和举一反三。
```

前端展示：

```text
薄弱点卡片
- 知识点
- 掌握率
- 练习数
- 正确数
- 遗忘风险
- 一键生成专项练习
```

---

### 2.3 用户可以查看错题

用户：

```text
帮我看看最近一周的错题。
```

AI 助手：

```text
你最近一周共有 8 道错题，其中 5 道还未标记掌握。
主要集中在“几何面积”和“分数运算”。
```

前端展示：

```text
错题列表卡片
- 错题题干
- 知识点
- 错误类型
- 是否掌握
- 原题重练按钮
- 举一反三按钮
```

---

### 2.4 用户可以生成错题重练

用户：

```text
把最近 3 天的错题生成 3 天练习，每套 4 个计算题，至少 2 个举一反三。
```

AI 助手执行流程：

```text
1. 从 MySQL 查询最近 3 天错题。
2. 把错题平均分配到 3 套练习。
3. 每套补充 4 道计算题。
4. 每套通过向量数据库或规则推荐至少 2 道举一反三。
5. 返回 3 套练习单预览。
6. 用户确认后写入 MySQL。
```

---

### 2.5 用户可以讲解题目

用户：

```text
这道题为什么这样做？
```

AI 助手：

```text
这道题的关键是先找出外部图形面积，再减去原来的图形面积。
你容易错的地方可能是只算了外部面积，没有做相减。
```

前端展示：

```text
题目讲解卡片
- 题干
- 答案
- 解题思路
- 分步解析
- 易错点
- 同类题推荐
```

---

### 2.6 用户可以制定学习计划

用户：

```text
我下周考试，帮我安排 7 天复习计划。
```

AI 助手：

```text
我建议你用 7 天完成三轮复习：
第 1-2 天：基础计算和分数运算
第 3-4 天：几何面积和应用题
第 5 天：错题重练
第 6 天：综合练习
第 7 天：查漏补缺
```

前端展示：

```text
学习计划卡片
- 每日重点
- 每日任务
- 推荐练习
- 一键生成对应练习单
```

---

### 2.7 用户可以查看学习总结

用户：

```text
帮我总结一下这周学习情况。
```

AI 助手：

```text
你本周完成了 5 套练习，共 42 道题，正确率约 76%。
进步较明显的是“分数计算”，但“几何面积”仍然需要加强。
建议下周继续安排 2 套几何专项练习。
```

前端展示：

```text
学习总结卡片
- 练习套数
- 题目数量
- 正确率
- 进步知识点
- 薄弱知识点
- 下周建议
```

---

### 2.8 用户可以操作系统功能

用户：

```text
怎么上传错题？
```

AI 助手：

```text
你可以进入“错题管理”页面，点击“拍照识别”或“上传 PDF”，上传后等待系统识别，然后确认题目并加入错题本。
```

---

### 2.9 用户可以语义搜索题目

用户：

```text
找几道和长方形花坛铺路面积类似的题。
```

AI 助手：

```text
我找到了几道和“花坛铺路面积”相似的题，主要涉及外框面积减内框面积。
```

前端展示：

```text
相似题卡片
- 题目
- 相似度
- 知识点
- 难度
- 加入练习单
- 查看解析
```

---

### 2.10 用户可以做题库查重

用户上传或录入新题时：

```text
系统自动检查题库中是否已有相似题。
```

AI 助手或前端提示：

```text
题库中发现 3 道相似题，建议确认是否重复后再入库。
```

---

## 3. 技术选型

### 3.1 后端

```text
FastAPI
SQLAlchemy
MySQL
LangGraph
LangChain
Qdrant
httpx
Pydantic
```

### 3.2 前端

```text
Vue 3
Element Plus
Pinia
Vue Router
Axios
```

### 3.3 数据库分工

```text
MySQL：
保存权威业务数据。
包括用户、题库、错题、练习单、学习记录、掌握度、AI 助手会话。

Qdrant：
保存题目和文档 embedding。
用于相似题、语义查题、题库查重、RAG 文档问答。

Agent：
负责理解用户需求，调用 MySQL 工具、向量检索工具和业务工具。
```

---

## 4. 总体架构

```text
前端 AIAssistant.vue
        ↓
POST /api/assistant/chat
        ↓
FastAPI Assistant API
        ↓
LangGraph Agent Runtime
        ↓
RouterNode 意图识别
        ↓
按意图分发到不同节点
        ↓
调用工具层
        ↓
工具层访问：
    - MySQL
    - Qdrant
    - 现有练习单模块
    - 现有错题模块
    - 现有学情模块
    - 现有 AI 组卷模块
        ↓
ResponseNode 生成回复
        ↓
保存 assistant_sessions / assistant_messages
        ↓
返回 reply + actions + data
```

---

## 5. 后端新增目录结构

```text
backend/app/agents/
├── __init__.py
├── graph.py
├── state.py
├── memory.py
├── guardrails.py
├── model.py
├── constants.py
├── nodes/
│   ├── __init__.py
│   ├── router_node.py
│   ├── practice_node.py
│   ├── diagnosis_node.py
│   ├── wrong_node.py
│   ├── tutor_node.py
│   ├── study_plan_node.py
│   ├── summary_node.py
│   ├── vector_search_node.py
│   ├── system_help_node.py
│   └── response_node.py
├── tools/
│   ├── __init__.py
│   ├── practice_tools.py
│   ├── diagnosis_tools.py
│   ├── wrong_tools.py
│   ├── question_tools.py
│   ├── study_plan_tools.py
│   ├── summary_tools.py
│   ├── vector_tools.py
│   └── system_tools.py
└── prompts/
    ├── router.md
    ├── practice.md
    ├── diagnosis.md
    ├── wrong_question.md
    ├── tutor.md
    ├── study_plan.md
    ├── summary.md
    ├── vector_search.md
    └── response_writer.md
```

---

## 6. 向量数据库新增目录结构

```text
backend/app/vector/
├── __init__.py
├── config.py
├── client.py
├── embedding.py
├── indexer.py
├── search.py
├── sync.py
└── hybrid.py
```

说明：

```text
config.py      向量库配置
client.py      Qdrant 客户端
embedding.py   embedding 生成
indexer.py     题库向量索引构建
search.py      向量检索
sync.py        增量同步
hybrid.py      向量 + MySQL 混合推荐
```

---

## 7. 前端新增目录结构

```text
frontend/src/views/AIAssistant.vue

frontend/src/api/assistant.js
frontend/src/api/vectorSearch.js

frontend/src/components/assistant/
├── AssistantMessage.vue
├── PracticePreviewCard.vue
├── WeakPointCard.vue
├── WrongQuestionCard.vue
├── QuestionExplainCard.vue
├── StudyPlanCard.vue
├── StudySummaryCard.vue
├── SimilarQuestionCard.vue
└── QuickActionBar.vue
```

---

# 8. 数据库设计

## 8.1 assistant_sessions

```sql
CREATE TABLE IF NOT EXISTS assistant_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(100),
    status ENUM('active', 'archived') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_session (user_id, updated_at),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI助手会话表';
```

---

## 8.2 assistant_messages

```sql
CREATE TABLE IF NOT EXISTS assistant_messages (
    message_id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    user_id INT NOT NULL,
    role ENUM('user', 'assistant', 'tool') NOT NULL,
    content TEXT,
    intent VARCHAR(50),
    tool_name VARCHAR(100),
    tool_args JSON,
    tool_result JSON,
    actions JSON,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_time (session_id, created_at),
    INDEX idx_user_time (user_id, created_at),
    FOREIGN KEY (session_id) REFERENCES assistant_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI助手消息表';
```

---

## 8.3 vector_sync_jobs

后续用于异步同步题目向量。

```sql
CREATE TABLE IF NOT EXISTS vector_sync_jobs (
    job_id INT PRIMARY KEY AUTO_INCREMENT,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INT NOT NULL,
    action ENUM('upsert', 'delete') NOT NULL,
    status ENUM('pending', 'processing', 'success', 'failed') DEFAULT 'pending',
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='向量同步任务表';
```

---

# 9. Agent 支持的意图

```text
practice_generate          生成练习单
practice_confirm           确认生成练习单
practice_adjust            换题、补题、调整难度
learning_diagnosis         学情分析
wrong_question_review      查看错题
wrong_practice_generate    生成错题练习
question_explain           题目讲解
study_plan                 制定学习计划
study_summary              查看学习总结
semantic_question_search   语义查题
similar_question_recommend 推荐相似题
duplicate_check            题库查重
system_help                系统功能帮助
smalltalk                  普通聊天
fallback                   无法识别
```

---

# 10. Agent 工具清单

## 10.1 练习单工具

```python
generate_practice_preview_tool()
confirm_practice_sheet_tool()
replace_practice_question_tool()
supplement_practice_question_tool()
```

复用：

```text
build_ai_preview
confirm_ai_sheets
replace_ai_question
supplement_ai_question
```

---

## 10.2 学情工具

```python
get_weak_points_tool()
get_mastery_summary_tool()
get_learning_trend_tool()
```

数据来源：

```text
user_knowledge_mastery
user_practice_history
user_wrong_questions
questions
```

---

## 10.3 错题工具

```python
get_recent_wrong_questions_tool()
get_unmastered_wrong_questions_tool()
generate_wrong_practice_tool()
generate_similar_wrong_practice_tool()
```

数据来源：

```text
user_wrong_questions
questions
practice_sheets
sheet_questions
```

---

## 10.4 题目讲解工具

```python
search_questions_tool()
explain_question_tool()
get_question_detail_tool()
```

讲解规则：

```text
优先使用题库已有 answer / solution。
没有解析时再调用 LLM。
```

---

## 10.5 学习计划工具

```python
build_study_plan_tool()
build_exam_review_plan_tool()
```

---

## 10.6 学习总结工具

```python
build_weekly_summary_tool()
build_monthly_summary_tool()
```

---

## 10.7 向量检索工具

```python
semantic_search_questions_tool()
similar_questions_tool()
duplicate_check_tool()
rag_system_help_tool()
```

访问：

```text
Qdrant
MySQL
```

---

# 11. LangGraph 流程设计

```text
START
  ↓
router_node
  ↓
条件分支：
  ├── practice_node
  ├── diagnosis_node
  ├── wrong_node
  ├── tutor_node
  ├── study_plan_node
  ├── summary_node
  ├── vector_search_node
  ├── system_help_node
  └── response_node
  ↓
response_node
  ↓
END
```

---

# 12. 分阶段完整开发流程

## 第 0 阶段：基础准备

目标：

```text
完成依赖、目录、环境变量准备。
```

后端任务：

```text
1. 安装 langgraph、langchain、qdrant-client。
2. 新建 agents 目录。
3. 新建 vector 目录。
4. 新建 assistant.py API。
5. 增加环境变量。
```

前端任务：

```text
1. 新增 AIAssistant.vue 空页面。
2. 新增 assistant.js。
3. 新增 AI 学习助手菜单。
```

验收：

```text
[ ] 后端能启动。
[ ] 前端能打开 AI 学习助手页面。
[ ] 环境变量配置完整。
```

---

## 第 1 阶段：MySQL 会话与消息存储

目标：

```text
完成 AI 助手会话和消息持久化。
```

后端任务：

```text
1. 创建 assistant_sessions 表。
2. 创建 assistant_messages 表。
3. 新增 ORM 模型。
4. 新增 schema。
5. 实现 ensure_session。
6. 实现 save_user_message。
7. 实现 save_assistant_message。
8. 实现查询历史会话。
```

接口：

```text
POST /api/assistant/chat
GET /api/assistant/sessions
GET /api/assistant/sessions/{session_id}/messages
DELETE /api/assistant/sessions/{session_id}
```

验收：

```text
[ ] 可以创建会话。
[ ] 可以保存用户消息。
[ ] 可以保存助手回复。
[ ] 可以查询历史会话。
[ ] 用户只能看到自己的会话。
```

---

## 第 2 阶段：Qdrant 接入

目标：

```text
让后端可以连接向量数据库。
```

后端任务：

```text
1. 实现 vector/client.py。
2. 实现 create_collection。
3. 实现 upsert_point。
4. 实现 search_points。
5. 实现 delete_point。
```

验收：

```text
[ ] 可以连接 Qdrant。
[ ] 可以创建 math_questions collection。
[ ] 可以写入测试向量。
[ ] 可以搜索测试向量。
[ ] Qdrant 不可用时系统不崩溃。
```

---

## 第 3 阶段：题库 embedding 构建

目标：

```text
把 questions 表同步到向量数据库。
```

任务：

```text
1. 实现 build_question_embedding_text。
2. 实现 embed_text。
3. 实现 upsert_question_vector。
4. 新增 vector_build_index.py。
5. 全量同步题库。
```

embedding 内容：

```text
题干
答案
解析
知识点
知识类别
题型
难度
年级
```

验收：

```text
[ ] 题库题目成功写入 Qdrant。
[ ] 每条向量 payload 包含 question_id。
[ ] MySQL 与 Qdrant 数量基本一致。
```

---

## 第 4 阶段：向量检索服务

目标：

```text
实现相似题搜索和自然语言查题。
```

任务：

```text
1. 实现 search_similar_questions。
2. 支持 source_question_id。
3. 支持 query_text。
4. 支持 top_k。
5. 支持 exclude_ids。
6. 支持 MySQL 二次过滤。
```

验收：

```text
[ ] 根据一道题可以找相似题。
[ ] 根据自然语言可以查题。
[ ] 不会返回原题自己。
[ ] 可以过滤题型和难度。
```

---

## 第 5 阶段：举一反三接入向量检索

目标：

```text
让错题练习和 AI 组卷中的举一反三更智能。
```

任务：

```text
1. 实现 recommend_similar_questions_hybrid。
2. 优先用 Qdrant 找相似题。
3. 不足时 fallback 到同知识点 / 同类别推荐。
4. 接入 generate-selected-wrongs。
5. 接入 generate-smart-redo。
6. 接入 ai-generate-preview。
```

验收：

```text
[ ] 举一反三推荐更贴近原错题。
[ ] 向量库不可用时仍可推荐。
[ ] 不会推荐最近练过的题。
[ ] 不会重复推荐同一道题。
```

---

## 第 6 阶段：题库查重

目标：

```text
利用向量检索实现语义查重。
```

任务：

```text
1. 新增 /api/questions/vector-dup-check。
2. 手动录题时调用。
3. AI 识别录题确认前调用。
4. 展示疑似重复题。
```

验收：

```text
[ ] 相似题能被识别为疑似重复。
[ ] 查重结果能展示给用户。
[ ] 不自动删除题目，只做提醒。
```

---

## 第 7 阶段：LangGraph Agent 骨架

目标：

```text
搭建最小 Agent 工作流。
```

任务：

```text
1. 实现 AgentState。
2. 实现 router_node。
3. 实现 response_node。
4. 实现 graph.py。
5. /api/assistant/chat 调用 Agent。
```

验收：

```text
[ ] Agent 可以正常执行。
[ ] 能识别基础 intent。
[ ] 能返回 reply。
[ ] 能保存消息。
```

---

## 第 8 阶段：Agent 接入系统帮助

目标：

```text
让 AI 助手回答系统使用问题。
```

任务：

```text
1. 实现 system_tools.py。
2. 实现 system_help_node.py。
3. 支持上传错题、生成练习单、查看学情等说明。
```

验收：

```text
[ ] 用户问“怎么上传错题”能得到正确步骤。
[ ] 用户问“怎么生成练习单”能得到正确步骤。
```

---

## 第 9 阶段：Agent 接入练习单能力

目标：

```text
让 AI 助手可以生成、确认、调整练习单。
```

任务：

```text
1. 实现 practice_tools.py。
2. 实现 practice_node.py。
3. 调用 build_ai_preview。
4. 调用 confirm_ai_sheets。
5. 调用 replace_ai_question。
6. 调用 supplement_ai_question。
```

验收：

```text
[ ] 用户可以自然语言生成练习单预览。
[ ] 用户可以确认生成。
[ ] 用户可以换题。
[ ] 用户可以补题。
```

---

## 第 10 阶段：Agent 接入学情分析

目标：

```text
让 AI 助手可以分析薄弱点和掌握度。
```

任务：

```text
1. 实现 diagnosis_tools.py。
2. 实现 diagnosis_node.py。
3. 查询 user_knowledge_mastery。
4. 查询练习历史。
5. 查询错题统计。
```

验收：

```text
[ ] 用户可以查询薄弱点。
[ ] 用户可以查看掌握率。
[ ] 可以基于薄弱点生成练习。
```

---

## 第 11 阶段：Agent 接入错题助手

目标：

```text
让 AI 助手可以查看错题、生成错题练习和举一反三。
```

任务：

```text
1. 实现 wrong_tools.py。
2. 实现 wrong_node.py。
3. 查询最近错题。
4. 查询未掌握错题。
5. 调用错题练习生成工具。
6. 调用向量相似题推荐。
```

验收：

```text
[ ] 用户可以查看最近错题。
[ ] 用户可以生成错题重练。
[ ] 用户可以生成举一反三。
```

---

## 第 12 阶段：Agent 接入题目讲解

目标：

```text
让 AI 助手可以讲解题目。
```

任务：

```text
1. 实现 question_tools.py。
2. 实现 tutor_node.py。
3. 优先使用题库 answer / solution。
4. 解析不足时调用 LLM。
5. 推荐同类题时调用向量检索。
```

验收：

```text
[ ] 用户可以查看题目讲解。
[ ] 用户可以看到易错点。
[ ] 用户可以获得同类题推荐。
```

---

## 第 13 阶段：Agent 接入向量搜索

目标：

```text
让 AI 助手可以自然语言查题、找相似题、做查重。
```

任务：

```text
1. 实现 vector_tools.py。
2. 实现 vector_search_node.py。
3. 支持 semantic_question_search。
4. 支持 similar_question_recommend。
5. 支持 duplicate_check。
```

验收：

```text
[ ] 用户可以说“找几道铺路面积类似题”。
[ ] 用户可以说“给我这道错题的相似题”。
[ ] 用户可以请求查重。
```

---

## 第 14 阶段：学习计划与学习总结

目标：

```text
让 AI 助手能制定计划和总结学习情况。
```

任务：

```text
1. 实现 study_plan_tools.py。
2. 实现 study_plan_node.py。
3. 实现 summary_tools.py。
4. 实现 summary_node.py。
5. 基于错题、掌握度、练习历史生成计划和总结。
```

验收：

```text
[ ] 用户可以生成 3 天 / 7 天复习计划。
[ ] 用户可以查看本周学习总结。
[ ] 计划可以一键生成练习单。
```

---

## 第 15 阶段：前端 AI 助手完整页面

目标：

```text
完成用户可用的 AI 助手页面。
```

任务：

```text
1. 实现聊天窗口。
2. 实现消息列表。
3. 实现输入框。
4. 实现 PracticePreviewCard。
5. 实现 WeakPointCard。
6. 实现 WrongQuestionCard。
7. 实现 QuestionExplainCard。
8. 实现 SimilarQuestionCard。
9. 实现 StudyPlanCard。
10. 实现 StudySummaryCard。
```

验收：

```text
[ ] 用户可以连续聊天。
[ ] 不同 actions 能渲染不同卡片。
[ ] 卡片按钮能继续触发操作。
```

---

## 第 16 阶段：多轮上下文

目标：

```text
支持基于上一轮继续操作。
```

用户示例：

```text
用户：帮我生成一套几何面积练习。
AI：已生成预览。
用户：难一点。
AI：基于上一套练习调整难度并换题。
```

任务：

```text
1. 读取最近 5-10 条消息。
2. AgentState 增加 history。
3. RouterNode 结合上下文识别。
4. 保存上一轮 practice_preview。
5. 支持“换一批”“难一点”“简单点”“就这个生成”。
```

验收：

```text
[ ] 用户可以基于上一轮继续调整。
[ ] 用户说“确认生成”能识别上一轮预览。
[ ] 用户说“换一批”能重新生成。
```

---

## 第 17 阶段：安全、限流与容错

目标：

```text
保证系统能稳定运行。
```

任务：

```text
1. 所有工具必须使用当前登录 user_id。
2. 禁止 LLM 决定 user_id。
3. 禁止执行模型生成 SQL。
4. 单用户限流。
5. 全局 LLM 并发限制。
6. Qdrant 超时 fallback。
7. 练习单确认生成幂等。
8. 错误信息脱敏。
```

验收：

```text
[ ] 用户不能访问别人数据。
[ ] 高频请求会被限制。
[ ] Qdrant 不可用时不影响核心功能。
[ ] AI 失败时有 fallback。
```

---

## 第 18 阶段：测试与上线

测试内容：

```text
1. Assistant API 测试
2. Intent 识别测试
3. MySQL 工具测试
4. 向量检索测试
5. 练习单生成测试
6. 错题查询测试
7. 学情分析测试
8. 题目讲解测试
9. 查重测试
10. 权限隔离测试
```

上线优化：

```text
1. 关闭 reload=True。
2. 使用多 worker。
3. 数据库连接池 pool_pre_ping。
4. LLM 调用 timeout。
5. Qdrant 调用 timeout。
6. 日志记录 tool_args / tool_result。
7. 生产环境日志脱敏。
```

---

# 13. 前端 actions 类型

```text
show_practice_preview
show_weak_points
show_wrong_question_list
show_question_explanation
show_similar_questions
show_study_plan
show_study_summary
quick_actions
system_help
```

---

# 14. 最终完整闭环

## 14.1 练习单闭环

```text
用户自然语言
    ↓
Agent 识别 practice_generate
    ↓
MySQL 查询题库 / 错题 / 掌握度
    ↓
Qdrant 推荐相似题
    ↓
生成练习单预览
    ↓
前端展示卡片
    ↓
用户确认
    ↓
MySQL 写入练习单
```

---

## 14.2 错题闭环

```text
用户查看错题
    ↓
MySQL 查询错题
    ↓
Agent 总结错因
    ↓
Qdrant 推荐相似题
    ↓
生成错题重练
    ↓
用户完成练习
    ↓
MySQL 更新掌握度
```

---

## 14.3 学情闭环

```text
练习历史
    ↓
错题记录
    ↓
掌握度表
    ↓
Agent 分析薄弱点
    ↓
生成学习计划
    ↓
生成练习单
    ↓
继续练习和更新数据
```

---

## 14.4 题库智能化闭环

```text
新题录入
    ↓
向量查重
    ↓
确认入库
    ↓
生成 embedding
    ↓
进入语义检索
    ↓
用于相似题和举一反三
```

---

# 15. 最终验收清单

## 15.1 后端

```text
[ ] Assistant API 可用。
[ ] LangGraph Agent 可运行。
[ ] MySQL 会话消息可保存。
[ ] Qdrant 可连接。
[ ] 题库 embedding 可构建。
[ ] 相似题检索可用。
[ ] 题库查重可用。
[ ] Agent 可调用 MySQL 工具。
[ ] Agent 可调用向量检索工具。
[ ] 所有工具有权限隔离。
```

---

## 15.2 前端

```text
[ ] AI 助手页面可用。
[ ] 聊天消息可展示。
[ ] 练习单卡片可展示。
[ ] 错题卡片可展示。
[ ] 薄弱点卡片可展示。
[ ] 相似题卡片可展示。
[ ] 学习计划卡片可展示。
[ ] 卡片按钮可操作。
```

---

## 15.3 功能

```text
[ ] 可以生成练习单。
[ ] 可以查询薄弱点。
[ ] 可以查看错题。
[ ] 可以生成错题重练。
[ ] 可以生成举一反三。
[ ] 可以讲解题目。
[ ] 可以制定学习计划。
[ ] 可以查看学习总结。
[ ] 可以语义搜索题目。
[ ] 可以题库查重。
[ ] 可以回答系统使用问题。
```

---

## 15.4 安全与稳定

```text
[ ] 用户数据隔离正常。
[ ] Agent 不执行模型生成 SQL。
[ ] LLM 调用有超时。
[ ] Qdrant 不可用时有 fallback。
[ ] 高频请求会限流。
[ ] 练习单确认生成不重复。
```

---

# 16. 推荐开发顺序

最推荐按照下面顺序做：

```text
1. MySQL 会话和消息表
2. Qdrant 接入
3. 题库 embedding
4. 相似题检索
5. 举一反三接入向量检索
6. 题库查重
7. LangGraph Agent 骨架
8. Agent 接入系统帮助
9. Agent 接入练习单
10. Agent 接入学情分析
11. Agent 接入错题助手
12. Agent 接入题目讲解
13. Agent 接入向量搜索
14. Agent 接入学习计划和学习总结
15. 前端完整卡片交互
16. 多轮上下文
17. 安全、限流、测试和上线
```

---

# 17. 最终原则

实现时必须坚持：

```text
MySQL 是权威业务数据库。
向量数据库只负责语义召回。
Agent 只负责编排工具，不直接操作数据库。
所有写操作都必须由后端工具校验。
所有用户数据都必须根据当前登录 user_id 查询。
```

最终系统目标：

```text
题库管理
    +
错题管理
    +
练习单生成
    +
学情诊断
    +
向量相似题
    +
AI 学习助手 Agent
```

形成完整的：

```text
AI 学习诊断与个性化练习闭环
```
