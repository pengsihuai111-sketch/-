# 小升初数学题库 v3.0 分层分片架构设计文档

**设计日期**: 2026-05-03  
**适用对象**: 冯紫桐  
**目标规模**: 600-800题（可扩展至1000+题）  
**架构版本**: v3.0 Sharded Storage

---

## 1. 架构概览

```
math_bank_v3/
├── index/                        ← 元数据索引层（轻量、高频访问）
│   ├── master_index.json           ← 主索引：每题一条轻量记录(~600字节/题)
│   ├── knowledge_point_index.json  ← 知识点→题目ID映射
│   ├── school_index.json           ← 学校→题目ID映射
│   ├── difficulty_index.json       ← 难度→题目ID映射
│   └── question_type_index.json    ← 题型→题目ID映射
│
├── questions/                     ← 题目内容分片层（按需加载）
│   ├── 几何.json                   ← 几何类：面积/体积/展开图 (~15知识点)
│   ├── 方程与应用.json              ← 应用题：行程/工程/经济/浓度 (~16知识点)
│   ├── 计算.json                   ← 计算类：简便运算/分数运算 (~21知识点)
│   ├── 数论.json                   ← 数论类：因数/倍数/概率 (~16知识点)
│   ├── 逻辑.json                   ← 逻辑类：推理/找规律/新运算 (~15知识点)
│   ├── 基础.json                   ← 基础类：单位换算/解方程 (~8知识点)
│   └── 其他.json                   ← 未分类题目
│
├── images/                        ← 几何题原图
│   └── *.png
│
├── dedup/                         ← 查重索引层
│   └── dedup_index.json           ← 文本指纹 + 变式链 + 来源索引
│
├── student/                       ← 学生状态
│   └── 冯紫桐_学习状态.json        ← 掌握度/错题追踪/出题历史
│
├── wrong_questions/               ← 错题库（独立管理）
│   └── wrong_question_bank.json   ← 错题记录 + 考试历史
│
└── weekly_plans/                  ← 周计划历史（可选）
    └── plan_YYYY-MM-DD.json
```

---

## 2. 核心设计原则

| 原则 | 说明 | 解决什么问题 |
|------|------|-------------|
| **索引与内容分离** | 主索引只存元数据，不存题目原文 | 800题主索引仅~500KB，可秒级加载 |
| **按知识点分片** | 题目按知识点大类拆分到不同文件 | 专题练习直接加载对应分片 |
| **读写分离粒度** | 读索引 → 定位分片 → 读写内容 | 更新1题只需重写~300KB分片 |
| **多维度索引** | 知识点/学校/难度/题型各建独立索引 | 组卷时快速筛选目标题目 |
| **错题独立存储** | 错题库与主题库物理分离 | 错题分析不污染主索引 |

---

## 3. 数据流向图

### 3.1 查询题目流程
```
输入: q_id = "EW_几何面积_001"
  ↓
加载 index/master_index.json (~500KB @ 800题)
  ↓
查找 q_id 记录 → 获取 shard = "几何"
  ↓
加载 questions/几何.json (~300KB)
  ↓
输出: 完整题目数据（原文+答案+解析）
```

### 3.2 生成练习单流程
```
输入: 生成周一练习单（需8题）
  ↓
加载 index/master_index.json
  ↓
筛选条件: difficulty∈{基础,中等}, usage_count=0, last_used < 7天前
  ↓
获取候选ID列表（可能50-80题ID）
  ↓
按需加载2-3个分片文件（如几何+计算+方程）
  ↓
从分片中抽取题目原文 → 组卷 → 输出
  ↓
更新master_index中的 usage_count + last_used
  ↓
保存更新的索引（~500KB重写）
```

### 3.3 新题入库流程
```
输入: 新考试PDF解析出10题
  ↓
加载 dedup/dedup_index.json
  ↓
逐题查重（比对新题指纹 vs 现有指纹）
  ↓
通过查重 → 确定每题shard
  ↓
加载对应分片 → 追加新题 → 保存分片
  ↓
更新master_index（追加10条记录）
  ↓
更新所有辅助索引
  ↓
完成
```

---

## 4. 文件格式规范

### 4.1 master_index.json（主索引）

```json
{
  "_meta": {
    "version": "3.0",
    "total_questions": 800,
    "shards": ["几何", "方程与应用", "计算", "数论", "逻辑", "基础", "其他"]
  },
  "questions": [
    {
      "q_id": "EW_几何面积_001",
      "knowledge_point": "几何面积",
      "shard": "几何",
      "question_type": "problem_solving",
      "difficulty": "挑战",
      "source_school_full": "重庆第二外国语学校",
      "source_exam": "二外真题第1套",
      "source_number": "解答第7题",
      "exam_year": "2025",
      "has_image": true,
      "image_path": "EW_2025_T1_JD7_几何面积_geom.png",
      "is_key_point": true,
      "is_difficult": true,
      "is_high_freq": false,
      "confirmed": true,
      "answer_status": "verified",
      "usage_count": 0,
      "last_used": null
    }
  ]
}
```

### 4.2 questions/{shard}.json（分片内容）

```json
{
  "_meta": {
    "shard_name": "几何",
    "total_questions": 43,
    "knowledge_points": ["几何面积", "圆柱与圆锥", "立体几何"]
  },
  "questions": [
    {
      "q_id": "EW_几何面积_001",
      "knowledge_point": "几何面积",
      "question_type": "problem_solving",
      "difficulty": "挑战",
      "source_school_full": "重庆第二外国语学校",
      "source_exam": "二外真题第1套",
      "source_number": "解答第7题",
      "exam_year": "2025",
      "exam_outline_year": "2025",
      "question_text": "如图，长方形ABCD的面积为48cm²...",
      "answer": "(1) 6:1；(2) 18cm²",
      "solution": "设AB=a，BC=b，ab=48...",
      "has_image": true,
      "image_path": "EW_2025_T1_JD7_几何面积_geom.png",
      "image_caption": "几何面积相关图形",
      "is_key_point": true,
      "is_difficult": true,
      "is_high_freq": false,
      "is_classic": false,
      "is_obsolete": false,
      "confirmed_by_user": true,
      "confirmed_date": "2026-05-02",
      "confirmed_version": "v2.1",
      "added_date": "2026-05-02",
      "usage_count": 0,
      "variation_of": null,
      "recommend_global": false,
      "global_reviewed": false,
      "verification_status": "ai_generated"
    }
  ]
}
```

---

## 5. 关键操作API（概念）

### get_question(q_id)
```
1. 加载 master_index.json
2. 在 questions 数组中二分查找 q_id（或哈希查找）
3. 获取 shard 字段
4. 加载 questions/{shard}.json
5. 在分片中查找 q_id
6. 返回完整题目对象
```

### list_by_filter(filters)
```
1. 加载 master_index.json
2. 根据 filters（knowledge_point/difficulty/school等）筛选ID列表
3. 按 shard 分组
4. 按需加载各分片
5. 组装结果
```

### update_answer(q_id, new_answer, new_solution)
```
1. 从 master_index 获取 shard
2. 加载 questions/{shard}.json
3. 找到题目并更新 answer/solution
4. 更新 master_index 中的 answer_status
5. 保存分片（~300KB重写）
6. 保存 master_index（~500KB重写）
```

### add_questions(new_questions[])
```
1. 加载 dedup_index.json
2. 逐题查重
3. 对每题：确定shard → 加载分片 → 追加题目
4. 更新 master_index（追加记录）
5. 更新辅助索引
6. 更新 dedup_index
```

---

## 6. 扩展性设计

### 6.1 扩展到1000+题
- 主索引按 shard 分二级索引（如 master_index_part1.json, master_index_part2.json）
- 或保持单文件，但启用gzip压缩（500KB→~150KB）
- 分片策略不变，单分片最大控制在500题以内

### 6.2 多学生支持
- `student/{student_name}/` 目录
- 共享 `questions/` 和 `dedup/` 层
- 每个学生的错题库、掌握度独立存储

### 6.3 图片资源管理
- 当前：全部放在 `images/` 根目录
- 扩展：按知识点子目录 `images/几何/`、`images/行程/`
- 图片命名规则：`{学校代码}_{年份}_{套卷}_{题号}_{知识点}_geom.png`

---

## 7. 与SKILL.md规范的兼容性

v3.0架构完全兼容现有技能规范的所有字段要求：

| SKILL.md 要求 | v3.0 实现位置 |
|---------------|--------------|
| `q_id` | master_index + 分片内容 |
| `knowledge_point` | master_index + 分片内容 |
| `question_type` | master_index + 分片内容 |
| `difficulty` | master_index + 分片内容 |
| `source_school_full` | master_index + 分片内容 |
| `exam_year` | master_index + 分片内容 |
| `source_exam` | master_index + 分片内容 |
| `source_number` | master_index + 分片内容 |
| `question_text` | 分片内容 |
| `answer` | 分片内容 |
| `solution` | 分片内容 |
| `image_path` | master_index + 分片内容 |
| `has_image` | master_index + 分片内容 |
| `confirmed_by_user` | 分片内容 |
| `usage_count` | master_index + 分片内容 |
| `variation_of` | 分片内容 |
| `dedup fingerprint` | dedup/dedup_index.json |

---

## 8. 版本演进路线图

| 版本 | 规模 | 架构 | 状态 |
|------|------|------|------|
| v1.0 | ~50题 | 简单数组 | 已废弃 |
| v2.0 | 200题 | 单文件JSON | 当前已生成 |
| **v3.0** | **600-800题** | **分层分片** | **✅ 已生成，推荐使用** |
| v3.1 | 800+题 | 分片+压缩 | 规划中 |
| v4.0 | 1000+题 | SQLite/轻量数据库 | 远期规划 |

---

## 9. 立即使用建议

1. **保留v2.0文件作为备份**，直到v3.0验证稳定
2. **后续新题全部入库到v3.0架构**
3. **答案完善操作在v3.0分片中进行**，避免回写v2.0
4. **几何图片上传后**，在对应分片中补全 `image_path` 和 `has_image`
5. **生成练习单时**，优先使用v3.0架构（加载快、筛选快）

---

**文档结束**
