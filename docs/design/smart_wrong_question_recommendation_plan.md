# 智慧推荐错题功能实现计划

## 1. 背景与目标

当前系统已经具备题库管理、错题管理、练习单生成、错题反馈、知识点掌握度追踪和遗忘风险分析等基础能力。在此基础上，计划在“错题管理 / 错题重练”模块中增加“智慧推荐错题”能力。

本功能主要解决两个问题：

1. 在生成错题练习单时，支持选择时间段，生成该时间段内的所有错题。
2. 在生成错题重练时，支持用户自定义计算题、原错题、举一反三题的数量，并通过智慧推荐算法自动生成题单。

其中：

- 计算题：来自用户错题题库，题型为计算题。
- 原错题：来自用户错题题库。
- 举一反三题：不来自错题题库，而是从普通题库中选择与错题知识点、分类、难度相近的变式题。

---

## 2. 功能范围

### 2.1 时间段错题练习单

在生成错题练习单时，新增时间段筛选功能。

用户可以选择：

- 最近 7 天
- 最近 30 天
- 本学期
- 自定义时间段
- 全部错题

系统根据用户选择的时间范围，从 `user_wrong_questions` 中筛选该时间段内产生的错题，生成练习单。

### 2.2 智慧错题重练

在“生成错题重练”功能中，新增以下配置项：

| 配置项 | 说明 |
|---|---|
| 计算题数量 | 从错题库中选择计算类错题 |
| 原错题数量 | 从错题库中选择普通错题 |
| 举一反三数量 | 从普通题库中选择同知识点或相似知识点题目 |
| 时间范围 | 限定错题来源时间 |
| 推荐策略 | 支持智慧推荐、最新错题、薄弱知识点、遗忘风险 |

---

## 3. 前端改造计划

### 3.1 错题练习单增加时间段筛选

在“生成练习单”页面中，当练习类型选择为“错题重练”时，增加以下表单项：

```text
错题时间范围：
[开始日期] 至 [结束日期]

快捷选项：
- 最近 7 天
- 最近 30 天
- 本学期
- 全部错题
```

推荐默认值：最近 30 天。

前端提交示例：

```json
{
  "start_date": "2026-05-01",
  "end_date": "2026-05-12",
  "only_unmastered": true
}
```

### 3.2 错题重练增加题目数量配置

在“生成错题重练”区域中增加配置卡片：

```text
智慧推荐错题重练

计算题数量：[ 2 ]
原错题数量：[ 3 ]
举一反三数量：[ 2 ]

推荐策略：
○ 智慧推荐
○ 按最新错题
○ 按薄弱知识点
○ 按遗忘风险
```

前端提交示例：

```json
{
  "calculation_count": 2,
  "wrong_question_count": 3,
  "similar_question_count": 2,
  "start_date": "2026-05-01",
  "end_date": "2026-05-12",
  "strategy": "smart"
}
```

---

## 4. 后端接口设计

### 4.1 生成时间段错题练习单

建议新增接口：

```http
POST /api/practice/generate-wrong-period
```

请求参数：

```json
{
  "name": "近30天错题练习单",
  "start_date": "2026-04-12",
  "end_date": "2026-05-12",
  "difficulty": ["基础", "中等", "挑战"],
  "only_unmastered": true
}
```

返回结果：

```json
{
  "sheet_id": 1001,
  "sheet_name": "近30天错题练习单",
  "total_questions": 12,
  "estimated_time": 36,
  "questions": []
}
```

### 4.2 生成智慧错题重练

建议改造现有接口：

```http
POST /api/practice/generate-redo
```

扩展请求参数：

```json
{
  "name": "智慧错题重练",
  "calculation_count": 2,
  "wrong_question_count": 3,
  "similar_question_count": 2,
  "start_date": "2026-04-01",
  "end_date": "2026-05-12",
  "strategy": "smart",
  "difficulty": ["基础", "中等", "挑战"],
  "knowledge_points": [],
  "exclude_recent_days": 3,
  "only_unmastered": true,
  "include_mastered": false
}
```

返回结构：

```json
{
  "sheet_id": 1001,
  "sheet_name": "智慧错题重练",
  "total_questions": 7,
  "estimated_time": 21,
  "sections": [
    {
      "title": "计算巩固",
      "source_type": "calculation",
      "questions": []
    },
    {
      "title": "原错题重练",
      "source_type": "wrong",
      "questions": []
    },
    {
      "title": "举一反三",
      "source_type": "similar",
      "questions": []
    }
  ]
}
```

---

## 5. 数据模型改造计划

### 5.1 `user_wrong_questions` 表扩展

```sql
ALTER TABLE user_wrong_questions
ADD COLUMN last_redo_at DATETIME NULL COMMENT '上次重练时间',
ADD COLUMN correct_streak INT DEFAULT 0 COMMENT '连续做对次数',
ADD COLUMN wrong_streak INT DEFAULT 0 COMMENT '连续做错次数',
ADD COLUMN recommend_score FLOAT DEFAULT 0 COMMENT '推荐分',
ADD COLUMN source_practice_sheet_id INT NULL COMMENT '来源练习单ID';
```

字段说明：

| 字段 | 用途 |
|---|---|
| `last_redo_at` | 判断最近是否练过，避免重复推荐 |
| `correct_streak` | 连续做对多次后降低推荐优先级 |
| `wrong_streak` | 连续做错则提高推荐优先级 |
| `recommend_score` | 缓存推荐分 |
| `source_practice_sheet_id` | 追溯错题来源 |

### 5.2 `sheet_questions` 表扩展

```sql
ALTER TABLE sheet_questions
ADD COLUMN source_type VARCHAR(30) DEFAULT 'normal' COMMENT 'normal/wrong/calculation/similar',
ADD COLUMN related_wrong_question_id INT NULL COMMENT '关联的原错题记录ID';
```

`source_type` 枚举建议：

| 值 | 说明 |
|---|---|
| `normal` | 普通练习题 |
| `wrong` | 原错题 |
| `calculation` | 计算类错题 |
| `similar` | 举一反三题 |

### 5.3 新增推荐日志表，可选

```sql
CREATE TABLE recommendation_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    sheet_id INT NOT NULL,
    question_id INT NOT NULL,
    source_type VARCHAR(30),
    recommend_score FLOAT,
    reason VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

该表用于记录每道题的推荐原因，后续可用于分析推荐效果。

---

## 6. 智慧推荐算法设计

第一版建议采用“规则评分模型”，不建议一开始直接使用复杂机器学习模型。

原因：

1. 当前系统已经有错题记录、重做次数、掌握状态、知识点掌握率、遗忘风险等数据。
2. 小升初数学题目结构清晰，知识点匹配的效果会比较稳定。
3. 规则模型可解释，方便向学生和家长展示“为什么推荐这道题”。
4. 后续积累更多练习数据后，可以再升级为机器学习模型。

### 6.1 原错题推荐评分

推荐分计算逻辑：

```text
推荐分 = 
错误严重度分
+ 知识点薄弱分
+ 遗忘风险分
+ 最近错误分
+ 重做失败分
- 已掌握惩罚分
- 最近已练惩罚分
```

建议公式：

```text
score =
wrong_count_score * 0.25
+ mastery_score * 0.25
+ forgetting_score * 0.20
+ recent_wrong_score * 0.15
+ redo_fail_score * 0.10
+ difficulty_score * 0.05
- mastered_penalty
- recent_practice_penalty
```

评分因子说明：

| 因子 | 说明 |
|---|---|
| 错误次数分 | 错得越多，分数越高 |
| 掌握度分 | 掌握率越低，分数越高 |
| 遗忘风险分 | 遗忘风险越高，分数越高 |
| 最近错误分 | 最近刚错过的题适当提高优先级 |
| 重做失败分 | 重做仍错的题提高优先级 |
| 难度分 | 中等、挑战题略微加权 |
| 已掌握惩罚 | 已掌握题降低推荐优先级 |
| 最近已练惩罚 | 近 3 天练过的题降低推荐优先级 |

### 6.2 计算题推荐规则

计算题来源于错题题库，筛选条件：

```sql
SELECT *
FROM user_wrong_questions uwq
JOIN questions q ON uwq.question_id = q.id
WHERE uwq.user_id = :user_id
AND q.question_type = 'calculation';
```

排序逻辑：

1. 优先选择最近做错的计算题。
2. 优先选择重做后仍错误的计算题。
3. 优先选择涉及薄弱知识点的计算题。
4. 排除最近已经出现在练习单中的题。

如果计算类错题不足：

1. 先返回已有计算错题。
2. 不足部分从普通题库中选择同知识点计算题补充。
3. 前端提示：计算错题不足，已补充同类计算题。

### 6.3 原错题推荐规则

原错题从 `user_wrong_questions` 中选择。

推荐优先级：

```text
待巩固 > 未掌握 > 重做仍错 > 遗忘风险高 > 最近新增错题 > 已掌握
```

筛选条件建议：

```sql
WHERE is_mastered = false
OR correct_streak < 2
```

不同策略对应不同排序：

| 策略 | 排序方式 |
|---|---|
| `smart` | 按综合推荐分排序 |
| `latest` | 按错题创建时间倒序 |
| `weak_knowledge` | 按知识点掌握率升序 |
| `forgetting_risk` | 按遗忘风险分降序 |

### 6.4 举一反三推荐规则

举一反三题从普通题库 `questions` 中选择，不能来自用户错题题库。

核心思路：

```text
根据已选错题的知识点、知识分类、题型、难度，查找相似但不是同一道的题。
```

筛选条件示例：

```sql
SELECT *
FROM questions
WHERE id NOT IN (:wrong_question_ids)
AND knowledge_point IN (:target_knowledge_points)
AND category IN (:target_categories)
AND difficulty IN (:target_difficulties);
```

难度递进规则：

| 原错题难度 | 举一反三推荐难度 |
|---|---|
| 基础 | 基础 / 中等 |
| 中等 | 中等 / 挑战 |
| 挑战 | 中等 / 挑战 |

举一反三评分公式：

```text
similar_score =
知识点匹配分 * 0.40
+ 分类匹配分 * 0.20
+ 难度匹配分 * 0.15
+ 题型匹配分 * 0.15
+ 高频/经典标签分 * 0.10
```

---

## 7. 生成流程设计

### 7.1 生成时间段错题练习单流程

```text
1. 用户选择错题时间段。
2. 前端提交 start_date、end_date、难度、是否只看待巩固。
3. 后端查询该时间段内的错题。
4. 过滤已掌握题、最近练过题、已删除题。
5. 按知识点分组。
6. 按推荐分排序。
7. 创建 practice_sheets 记录。
8. 写入 sheet_questions。
9. 返回练习单详情。
```

### 7.2 生成智慧错题重练流程

```text
1. 用户输入计算题数量、原错题数量、举一反三数量。
2. 后端获取用户错题池。
3. 计算每道错题的推荐分。
4. 选择计算题：来源为错题库，题型为 calculation。
5. 选择原错题：来源为错题库，排除已选计算题。
6. 根据已选错题提取知识点画像。
7. 选择举一反三题：来源为普通题库，排除用户错题。
8. 合并题目并分区排序。
9. 创建练习单。
10. 返回练习单结果。
```

---

## 8. 后端伪代码

### 8.1 生成智慧错题重练

```python
def generate_smart_redo_sheet(
    user_id: int,
    calculation_count: int,
    wrong_question_count: int,
    similar_question_count: int,
    start_date=None,
    end_date=None,
    strategy="smart"
):
    # 1. 查询用户错题
    wrong_records = query_user_wrong_questions(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        only_unmastered=True
    )

    # 2. 计算推荐分
    for record in wrong_records:
        record.recommend_score = calculate_wrong_question_score(record)

    # 3. 选择计算类错题
    calculation_records = [
        r for r in wrong_records
        if r.question.question_type == "calculation"
    ]
    selected_calculations = select_top(
        calculation_records,
        calculation_count
    )

    # 4. 选择原错题
    used_question_ids = {r.question_id for r in selected_calculations}

    candidate_wrong_records = [
        r for r in wrong_records
        if r.question_id not in used_question_ids
    ]

    selected_wrong_records = select_top(
        candidate_wrong_records,
        wrong_question_count
    )

    # 5. 提取知识点画像
    selected_wrong_all = selected_calculations + selected_wrong_records
    target_knowledge_points = extract_knowledge_points(selected_wrong_all)
    target_categories = extract_categories(selected_wrong_all)

    # 6. 选择举一反三题
    similar_questions = recommend_similar_questions(
        user_id=user_id,
        knowledge_points=target_knowledge_points,
        categories=target_categories,
        exclude_wrong_questions=True,
        count=similar_question_count
    )

    # 7. 创建练习单
    sheet = create_practice_sheet(
        user_id=user_id,
        name="智慧错题重练",
        sheet_type="wrong_redo"
    )

    # 8. 写入题目
    add_sheet_questions(sheet.id, selected_calculations, source_type="calculation")
    add_sheet_questions(sheet.id, selected_wrong_records, source_type="wrong")
    add_sheet_questions(sheet.id, similar_questions, source_type="similar")

    return sheet
```

### 8.2 推荐分计算

```python
def calculate_wrong_question_score(record):
    question = record.question
    mastery = get_user_knowledge_mastery(
        user_id=record.user_id,
        knowledge_point=question.knowledge_point
    )

    wrong_count_score = min(record.wrong_count * 10, 100)
    mastery_score = 100 - mastery.mastery_rate
    forgetting_score = mastery.forgetting_risk_score or 0

    recent_wrong_score = calculate_recent_wrong_score(record.created_at)
    redo_fail_score = record.wrong_streak * 20

    difficulty_score_map = {
        "基础": 40,
        "中等": 70,
        "挑战": 90
    }
    difficulty_score = difficulty_score_map.get(question.difficulty, 50)

    mastered_penalty = 40 if record.is_mastered else 0
    recent_practice_penalty = calculate_recent_practice_penalty(record.last_redo_at)

    score = (
        wrong_count_score * 0.25
        + mastery_score * 0.25
        + forgetting_score * 0.20
        + recent_wrong_score * 0.15
        + redo_fail_score * 0.10
        + difficulty_score * 0.05
        - mastered_penalty
        - recent_practice_penalty
    )

    return max(score, 0)
```

---

## 9. 推荐解释设计

为了增强“智慧推荐”的可信度，建议每道题展示推荐原因。

### 9.1 原错题推荐原因示例

```text
推荐原因：
- 该题所属知识点“分数应用题”掌握率较低。
- 最近 30 天内出现过 2 次错误。
- 距离上次重练已超过 10 天，存在遗忘风险。
```

### 9.2 举一反三题推荐原因示例

```text
推荐原因：
- 与错题“分数应用题”知识点一致。
- 难度从基础提升到中等。
- 属于高频考点变式题。
```

接口返回示例：

```json
{
  "question_id": 123,
  "source_type": "similar",
  "recommend_score": 86.5,
  "recommend_reason": [
    "匹配薄弱知识点：分数应用题",
    "与原错题难度相近",
    "高频考点题"
  ]
}
```

---

## 10. 前端展示建议

生成成功后，练习单预览中按类型分区展示：

```text
一、计算巩固
1. ...
2. ...

二、原错题重练
3. ...
4. ...
5. ...

三、举一反三
6. ...
7. ...
```

每个题目右上角可以显示标签：

```text
[计算错题] [原错题] [举一反三] [薄弱知识点] [遗忘风险高]
```

---

## 11. 边界情况处理

### 11.1 计算题数量不足

场景：用户设置计算题 5 道，但错题库里只有 2 道计算错题。

处理方式：

1. 返回已有 2 道计算错题。
2. 剩余 3 道从普通题库中选择同知识点计算题补充。
3. 前端提示：计算错题不足，已补充同知识点计算题。

### 11.2 举一反三题不足

逐级放宽筛选条件：

```text
同知识点 → 同知识分类 → 同题型 → 同难度 → 全题库相近难度
```

### 11.3 时间段内没有错题

提示：

```text
当前时间段内暂无错题，请调整时间范围或选择全部错题。
```

### 11.4 已掌握错题是否推荐

默认不推荐已掌握错题，但可提供开关：

```text
□ 包含已掌握错题
```

### 11.5 避免重复推荐

建议默认近 3 天已经练过的题不再推荐。

如果错题数量不足，可以降低限制，允许补充近期练过但仍未掌握的题。

---

## 12. 开发阶段拆分

### 第一阶段：基础能力改造

目标：实现可用版本。

任务：

1. 前端错题重练表单增加时间段选择。
2. 前端增加计算题、原错题、举一反三题数量配置。
3. 后端 `generate-redo` 接口增加参数。
4. 实现时间段筛选错题。
5. 实现三类题目选择：计算错题、原错题、举一反三题。
6. 生成练习单时保存 `source_type`。

预计周期：2–3 天。

### 第二阶段：智慧推荐评分

目标：让推荐更智能。

任务：

1. 实现错题推荐分计算。
2. 接入知识点掌握率。
3. 接入遗忘风险。
4. 接入重做次数、连续做错次数。
5. 增加推荐原因字段。
6. 生成时按推荐分排序。

预计周期：3–5 天。

### 第三阶段：推荐效果优化

目标：提升推荐质量和可解释性。

任务：

1. 新增推荐日志表。
2. 记录每道题推荐原因。
3. 根据练习结果反向优化推荐权重。
4. 增加推荐策略选择：智慧推荐、最新错题、薄弱知识点、遗忘风险。
5. 前端展示推荐解释。

预计周期：3–5 天。

---

## 13. 最终建议

第一版推荐采用：

```text
规则评分推荐 + 知识点匹配 + 遗忘风险排序 + 最近练习去重
```

最终功能定义为：

```text
智慧推荐 = 先找最值得重练的错题，再围绕这些错题补充相似变式题。
```

这样既能利用现有系统数据，又能保证推荐结果可解释、可实现、可迭代。
