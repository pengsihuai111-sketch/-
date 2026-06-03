---
name: ai-learning-agent
description: Build, review, or extend the project's AI 学习助手 Agent for the 小升初数学题库管理系统. Use when implementing LangGraph assistant workflows, assistant chat APIs, MySQL-backed assistant sessions/messages, Agent tools for practice generation, wrong-question review, learning diagnosis, question explanation, study plans, Qdrant vector search, semantic similar-question recommendation, duplicate checking, or frontend assistant cards.
---

# AI Learning Agent

## Core Direction

Implement the assistant as a real LangGraph-based Agent, not a plain chatbot.

Use this architecture:

```text
Frontend AIAssistant.vue
  -> POST /api/assistant/chat
  -> Assistant API
  -> LangGraph graph
  -> router_node
  -> tool_node / intent-specific node
  -> response_node
  -> persist assistant_sessions / assistant_messages
  -> return reply + actions + data
```

Keep these boundaries:

- MySQL is the source of truth for users, questions, wrong questions, practice sheets, mastery, and assistant messages.
- Qdrant is an enhancement layer for semantic recall, similar questions, and duplicate checking.
- LangGraph orchestrates intent routing and tool calls.
- Tools perform real business operations and must validate inputs.
- LLMs may parse, plan, and explain, but must not execute SQL or decide `user_id`.
- All tools must use the authenticated backend `user_id`.
- Write operations must be preview-first or confirmation-based.

## Required Project References

Read [references/implementation-plan.md](references/implementation-plan.md) before implementing substantial Agent work.

Also inspect the current code before editing:

- `backend/app/utils/practice_ai.py` for AI practice preview/confirm/replace/supplement.
- `backend/app/api/practice_ai.py` for existing AI practice endpoints.
- `backend/app/api/practice.py` for practice, wrong practice, and completion flows.
- `backend/app/models/__init__.py` for ORM models.
- `backend/app/schemas/__init__.py` for Pydantic schemas.
- `frontend/src/components/AIPracticeDialog.vue` for the existing AI generation UX.
- `frontend/src/views/Practice.vue`, `WrongQuestions.vue`, `Diagnosis.vue` for reusable UI patterns.

## Recommended Implementation Order

1. Create Assistant MVP with LangGraph, MySQL sessions/messages, `/api/assistant/chat`, and a basic frontend page.
2. Add practice-generation preview by wrapping existing `build_ai_preview`.
3. Add assistant cards for practice preview, weak points, wrong questions, and question explanation.
4. Add multi-turn confirmation and adjustment: confirm generation, replace question, supplement question.
5. Add Qdrant vector module and question embedding synchronization.
6. Connect vector search to similar questions, duplicate checking, semantic search, and Agent vector tools.
7. Add study plan and study summary after the core learning loop is stable.
8. Add limits, guardrails, fallback behavior, and tests.

## First Version Intents

Start with these intents:

- `practice_generate`
- `learning_diagnosis`
- `wrong_question_review`
- `question_explain`
- `system_help`
- `smalltalk`
- `fallback`

Add these later:

- `practice_confirm`
- `practice_adjust`
- `wrong_practice_generate`
- `similar_question_recommend`
- `semantic_question_search`
- `duplicate_check`
- `study_plan`
- `study_summary`

## Backend Shape

Prefer this structure:

```text
backend/app/agents/
├── graph.py
├── state.py
├── service.py
├── router.py
├── response.py
├── guardrails.py
├── memory.py
├── constants.py
├── tools/
│   ├── practice_tools.py
│   ├── diagnosis_tools.py
│   ├── wrong_tools.py
│   ├── question_tools.py
│   ├── vector_tools.py
│   ├── study_tools.py
│   └── system_tools.py
└── prompts/
    ├── router.md
    ├── response.md
    ├── tutor.md
    └── study_plan.md
```

Add `backend/app/api/assistant.py`.

Use a small LangGraph first:

```text
START -> router_node -> tool_node -> response_node -> END
```

Only split into many intent-specific nodes after the first assistant loop is working.

## Response Contract

Return structured responses from `/api/assistant/chat`:

```json
{
  "session_id": "string",
  "reply": "string",
  "intent": "practice_generate",
  "actions": [
    {
      "type": "show_practice_preview",
      "data": {}
    }
  ],
  "suggestions": ["确认生成", "换一批", "降低难度"]
}
```

Frontend cards must render from `actions[].type`, not from ad hoc response shapes.

## Frontend Shape

Add:

```text
frontend/src/views/AIAssistant.vue
frontend/src/api/assistant.js
frontend/src/components/assistant/
```

First card components:

- `PracticePreviewCard.vue`
- `WeakPointCard.vue`
- `WrongQuestionCard.vue`
- `QuestionExplainCard.vue`
- `QuickActionBar.vue`

Later card components:

- `SimilarQuestionCard.vue`
- `StudyPlanCard.vue`
- `StudySummaryCard.vue`

## Vector Phase

Add Qdrant only after the LangGraph MVP is usable.

Use:

```text
backend/app/vector/
├── client.py
├── embedding.py
├── indexer.py
├── search.py
├── sync.py
└── hybrid.py
```

Qdrant collection: `math_questions`.

Payload should include `question_id`, `knowledge_point`, `knowledge_category`, `question_type`, `difficulty`, and `grade_level`.

If Qdrant fails, fallback to MySQL rules:

- Similar question: same knowledge point/category/type.
- Duplicate check: text similarity or existing duplicate check.
- Semantic search: keyword search.

## Validation

After backend changes:

```powershell
python -m py_compile backend/app/agents/*.py backend/app/api/assistant.py
```

Adjust paths if directories or files differ.

After frontend changes:

```powershell
npm run build
```

Run from `frontend/`.

## Guardrails

- Do not let the model generate or execute SQL.
- Do not accept `user_id` from request JSON for tool execution.
- Do not write practice sheets without a user confirmation step unless the user explicitly clicked a confirming action.
- Do not make Qdrant a hard dependency for core practice generation.
- Store tool names, tool args, tool results, and errors for debugging, but avoid logging secrets.
