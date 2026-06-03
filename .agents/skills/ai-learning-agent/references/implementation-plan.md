# AI 学习助手 Agent 实施参考计划

## Goal

Build a LangGraph-based AI learning assistant for the existing 小升初数学题库管理系统.

The assistant should become the natural-language entry point for:

- Practice generation
- Weak-point diagnosis
- Wrong-question review
- Wrong-question practice
- Similar-question recommendation
- Question explanation
- Study planning
- Weekly/monthly summaries
- Semantic question search
- Duplicate checking
- System help

## Architecture

```text
Frontend AIAssistant.vue
  -> POST /api/assistant/chat
  -> FastAPI Assistant API
  -> LangGraph Agent
  -> router_node
  -> tool_node / specialized nodes
  -> response_node
  -> MySQL persistence
  -> reply + actions + data
```

## Database Tables

### assistant_sessions

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

### assistant_messages

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

### vector_sync_jobs

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

## Agent State

```python
class AgentState(TypedDict):
    user_id: int
    session_id: str
    message: str
    history: list
    intent: str
    confidence: float
    tool_name: str
    tool_args: dict
    tool_result: dict
    reply: str
    actions: list
    error: str | None
```

## First-Version Tools

### Practice tools

Wrap existing functions:

- `build_ai_preview`
- `confirm_ai_sheets`
- `replace_ai_question`
- `supplement_ai_question`

### Diagnosis tools

Read:

- `user_knowledge_mastery`
- `user_practice_history`
- `user_wrong_questions`
- `questions`

Return weak points, mastery rate, practice count, correct count, and forgetting risk.

### Wrong-question tools

Read:

- `user_wrong_questions`
- `questions`

Support recent wrong questions and unmastered wrong questions.

### Question tools

Prefer stored `answer` and `solution`.

Call LLM only when explanation is missing or insufficient.

### System tools

Answer usage questions such as uploading wrong questions, recognizing PDFs, generating practice sheets, and checking diagnosis.

## Frontend Action Types

- `show_practice_preview`
- `show_weak_points`
- `show_wrong_question_list`
- `show_question_explanation`
- `show_similar_questions`
- `show_study_plan`
- `show_study_summary`
- `system_help`
- `quick_actions`

## Qdrant Phase

Use collection `math_questions`.

Embedding text:

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

Payload:

```json
{
  "question_id": 1,
  "knowledge_point": "几何面积",
  "knowledge_category": "几何",
  "question_type": "problem_solving",
  "difficulty": "中等",
  "grade_level": "六年级"
}
```

Expose vector tools:

- `semantic_search_questions`
- `similar_questions`
- `duplicate_check`

## Milestones

### Phase 1: LangGraph MVP

- Add assistant tables and ORM models.
- Add `/api/assistant/chat`.
- Add `AgentState`.
- Add `router_node`, `tool_node`, `response_node`.
- Implement first-version intents.
- Add frontend assistant page with simple chat.

### Phase 2: Practice loop

- Render `PracticePreviewCard`.
- Confirm generation.
- Replace question.
- Supplement question.
- Save generated sheets.

### Phase 3: Diagnosis and wrong-question loop

- Render weak-point and wrong-question cards.
- Add one-click generate practice from weak points.
- Add one-click wrong-question practice.

### Phase 4: Question explanation

- Render explanation card.
- Explain by `question_id`.
- Explain pasted question text.
- Add easy-mistake notes.

### Phase 5: Qdrant

- Add vector module.
- Build full question index.
- Add incremental sync jobs.
- Add fallback when Qdrant is unavailable.

### Phase 6: Vector-enhanced learning

- Connect similar question recommendation.
- Connect semantic search.
- Connect duplicate check.
- Use vector results inside Agent tools.

### Phase 7: Multi-turn context

- Read recent 10 messages.
- Save previous practice preview.
- Support "难一点", "简单点", "换一批", "就这个生成".

### Phase 8: Study plan and summary

- Add study plan tool and card.
- Add weekly/monthly summary tool and card.
- Allow plan tasks to generate practice sheets.

### Phase 9: Hardening

- Enforce user data isolation.
- Add LLM timeout and concurrency limits.
- Add Qdrant timeout and fallback.
- Add rate limiting.
- Add idempotent confirmation for practice creation.
- Avoid logging secrets.

## Safety Rules

- Always derive `user_id` from auth dependency.
- Never execute SQL produced by LLM.
- Never let LLM select arbitrary table names or columns.
- Validate all tool args with Pydantic or explicit checks.
- Treat all write operations as confirmable actions.
- Return friendly fallback messages when LLM or Qdrant fails.
