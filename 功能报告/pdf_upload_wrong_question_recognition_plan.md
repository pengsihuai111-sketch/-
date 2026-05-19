# 上传 PDF 识别错题功能实现计划报告

## 1. 项目背景

当前系统已经实现了图片识别错题功能，用户可以通过上传图片或截图录入错题。现阶段需要扩展为支持 **PDF 文件上传识别错题**，使用户可以直接上传试卷 PDF、错题整理 PDF、扫描版 PDF 或老师发放的电子文档，系统自动解析并识别其中的错题。

当前大模型方案采用 **智谱视觉/多模态模型**。由于 PDF 可能包含文本、图片、表格、几何图、批改痕迹、扫描页等复杂内容，因此本功能不能简单地将 PDF 直接交给模型，而应采用“PDF 解析 + 页面转换 + 智谱模型识别 + Markdown 中间格式 + 题库匹配 + 用户确认”的完整流程。

---

## 2. 功能目标

### 2.1 核心目标

实现用户上传 PDF 后，系统能够自动完成：

1. 判断 PDF 类型：电子版 PDF 或扫描版 PDF。
2. 将 PDF 内容转换为可识别的中间格式。
3. 提取 PDF 中的文字、图片、题目区域和页面截图。
4. 使用智谱模型识别题目内容。
5. 将识别结果转换为结构化错题候选数据。
6. 自动匹配系统题库中的原题。
7. 由用户确认后加入错题本。

### 2.2 支持的 PDF 类型

| PDF 类型 | 示例 | 处理方式 |
|---|---|---|
| 电子版 PDF | 教师导出的试卷、系统生成的练习单 | 提取文本和图片，生成 Markdown，再结构化识别 |
| 扫描版 PDF | 拍照试卷、扫描试卷、图片型 PDF | PDF 转图片，调用智谱视觉模型识别 |
| 带批改痕迹 PDF | 有红笔批改、学生手写、圈画 | 页面转图片，预处理后调用智谱视觉模型 |
| 带图题 PDF | 几何图、统计图、表格题 | 保留图片资源，Markdown 中引用图片，模型结合图文识别 |

---

## 3. 总体设计思路

### 3.1 核心设计原则

PDF 上传识别不要直接等同于“上传文件后让大模型一次性识别整份 PDF”，而应设计为任务式流程：

```text
用户上传 PDF
↓
创建识别任务
↓
判断 PDF 类型
↓
提取文本 / 转换页面图片
↓
生成 Markdown 中间文件
↓
抽取图片资源和题目区域
↓
调用智谱模型识别
↓
输出结构化候选错题
↓
匹配题库
↓
用户确认
↓
加入错题本
```

### 3.2 为什么引入 Markdown 中间格式

PDF 直接解析不利于后续处理，因此建议将 PDF 转换为 Markdown 中间格式。

Markdown 的作用：

1. 保存从 PDF 中提取出来的题干文本。
2. 保留题号、段落、表格等结构。
3. 使用图片链接保存几何图、统计图、截图题。
4. 方便后续传给大模型做结构化识别。
5. 方便调试和人工查看识别过程。

但要注意：**Markdown 不能替代图片资源本身**。对于几何图、统计图、看图题，必须保留原图或题目截图。

---

## 4. 文件处理流程设计

## 4.1 上传入口设计

建议新增统一接口：

```http
POST /api/wrong-questions/recognize-pdf
```

请求类型：

```http
Content-Type: multipart/form-data
```

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | File | 是 | 上传的 PDF 文件 |
| exam_name | string | 否 | 考试名称 |
| exam_date | date | 否 | 考试日期 |
| default_error_type | string | 否 | 默认错误类型 |
| recognition_mode | string | 否 | auto / text / vision |
| need_match_question_bank | boolean | 否 | 是否匹配题库，默认 true |

返回示例：

```json
{
  "task_id": 10001,
  "status": "processing",
  "file_name": "六年级数学错题.pdf",
  "file_type": "pdf",
  "message": "PDF 已上传，正在识别"
}
```

---

## 4.2 PDF 类型判断

上传 PDF 后，后端首先判断 PDF 类型。

### 判断逻辑

```python
def detect_pdf_type(pdf_path):
    text = extract_pdf_text(pdf_path)
    if len(text.strip()) > 100:
        return "text_pdf"
    else:
        return "scanned_pdf"
```

### 判断结果

| 类型 | 条件 | 后续流程 |
|---|---|---|
| text_pdf | 能提取到足够文本 | 文本提取 + 图片抽取 + Markdown 生成 |
| scanned_pdf | 几乎无法提取文本 | PDF 转图片 + 智谱视觉模型识别 |

---

# 5. 电子版 PDF 处理方案

## 5.1 处理流程

```text
电子版 PDF
↓
提取文本
↓
提取图片资源
↓
提取表格内容
↓
按页生成 Markdown
↓
按题号切分题目
↓
调用智谱模型结构化
↓
匹配题库
↓
生成候选错题
```

## 5.2 Markdown 生成示例

```md
# PDF 错题识别结果

## Page 1

### 第 1 题

计算：\( \frac{3}{4} + \frac{2}{5} \)。

### 第 2 题

如图，长方形的长是 12cm，宽是 8cm，求阴影部分面积。

![第2题图形](assets/page_1_img_1.png)

### 第 3 题

下面是某班数学成绩统计图，请回答问题。

![第3题统计图](assets/page_1_img_2.png)
```

## 5.3 图片资源处理

PDF 中的图片不能只转为文字，必须单独保存。

建议目录结构：

```text
uploads/recognition_tasks/task_10001/
├── source.pdf
├── document.md
├── result.json
├── pages/
│   ├── page_1.png
│   └── page_2.png
├── assets/
│   ├── page_1_img_1.png
│   └── page_1_img_2.png
└── crops/
    ├── page_1_q_1.png
    └── page_1_q_2.png
```

### 各文件作用

| 文件/目录 | 作用 |
|---|---|
| source.pdf | 原始 PDF 文件 |
| document.md | PDF 转换后的 Markdown 文件 |
| result.json | AI 识别后的结构化结果 |
| pages/ | PDF 每页渲染图，用于预览 |
| assets/ | 从 PDF 中抽取的图片、图形、表格截图 |
| crops/ | 每道题的裁剪图 |

---

# 6. 扫描版 PDF 处理方案

## 6.1 处理流程

扫描版 PDF 本质上是一张张图片，不能直接提取文本。

```text
扫描版 PDF
↓
PDF 每页转高清图片
↓
图片预处理
↓
调用智谱视觉模型识别页面结构
↓
按题号或区域切分题目
↓
每道题单独识别
↓
生成 Markdown
↓
匹配题库
↓
用户确认
```

## 6.2 页面图片转换

建议将 PDF 每页转为 200~300 DPI 的图片。

```python
from pdf2image import convert_from_path

pages = convert_from_path(pdf_path, dpi=300)
for index, page in enumerate(pages):
    page.save(f"pages/page_{index + 1}.png")
```

## 6.3 图片预处理

针对扫描版 PDF 和带批改痕迹 PDF，建议进行基础图像处理：

1. 自动旋转校正。
2. 去阴影。
3. 增强对比度。
4. 裁剪纸张边界。
5. 红色批改痕迹弱化或去除。
6. 压缩图片大小，控制模型输入成本。

### 红色批改痕迹处理

如果 PDF 中有红色批改、圈画、对勾，可以用 OpenCV 先弱化红色区域。

处理逻辑：

```text
原始图片
↓
转换 HSV 色彩空间
↓
识别红色区域
↓
生成红色 mask
↓
弱化或修复红色区域
↓
送入智谱模型识别
```

注意：第一版可以不强制做复杂去痕迹处理，优先通过 Prompt 告诉智谱模型忽略红色批改和手写痕迹。

---

# 7. 智谱模型识别设计

## 7.1 模型定位

在本功能中，智谱模型主要负责：

1. 识别图片型 PDF 页面中的题目。
2. 理解带图题、几何题、表格题。
3. 忽略学生手写答案、批改痕迹、圈画和对勾。
4. 将题目转换为结构化 JSON。
5. 根据题干判断题型、知识点、难度。
6. 辅助生成题库匹配关键词。

## 7.2 整页识别 Prompt

用于扫描版 PDF 的页面初步识别。

```text
你是一个小学数学试卷识别助手。

请分析这张 PDF 页面图片，识别页面中的数学题目。

要求：
1. 找出页面中所有题目的题号和大致区域。
2. 区分印刷体原题、学生手写答案、老师批改痕迹。
3. 不要把红色批改、手写演算、对勾、叉号、圈画、分数、老师批注计入题干。
4. 如果题目包含图形、表格、统计图，请标记 has_image 为 true。
5. 输出严格 JSON，不要输出 Markdown，不要输出解释文字。

JSON 格式：
{
  "page_no": 1,
  "questions": [
    {
      "question_no": "1",
      "bbox": [x1, y1, x2, y2],
      "visible_text_summary": "",
      "has_image": false,
      "confidence": 0.0
    }
  ]
}
```

## 7.3 单题识别 Prompt

用于题目区域裁剪图或 Markdown 中的单道题识别。

```text
你是一个小学数学错题识别助手。

请从图片或 Markdown 内容中提取“原始题目”。

重要规则：
1. 只提取试卷上的原始题干。
2. 忽略学生手写答案、演算过程、红色批改、对勾、叉号、圈画、分数、老师批注。
3. 如果题目中有图形、统计图、表格，请结合图片理解题意，并给出 image_description。
4. 如果部分内容被遮挡，请写入 unclear_parts，不要编造。
5. 保留数学符号、分数、单位、图形信息。
6. 判断题型、知识点、知识分类、难度。
7. 输出严格 JSON，不要输出解释文字。

JSON 格式：
{
  "question_no": "",
  "question_text": "",
  "question_type": "fill_blank | choice | calculation | problem_solving",
  "knowledge_points": [],
  "category": "",
  "difficulty": "基础 | 中等 | 挑战",
  "answer": "",
  "analysis": "",
  "keywords": [],
  "has_image": false,
  "image_description": "",
  "is_complete": true,
  "unclear_parts": [],
  "confidence": 0.0
}
```

## 7.4 结构化输出要求

无论是电子版 PDF、扫描版 PDF，还是带图题，最终都统一输出：

```json
{
  "question_no": "3",
  "question_text": "如图，长方形的长是12厘米，宽是8厘米，求阴影部分面积。",
  "question_type": "problem_solving",
  "knowledge_points": ["几何面积"],
  "category": "图形与几何",
  "difficulty": "中等",
  "answer": "",
  "analysis": "",
  "keywords": ["长方形", "阴影部分", "面积", "12厘米", "8厘米"],
  "has_image": true,
  "image_urls": ["/uploads/recognition_tasks/task_10001/assets/page_1_img_1.png"],
  "image_description": "图中包含一个长方形和阴影区域，需要根据面积关系求解。",
  "is_complete": true,
  "unclear_parts": [],
  "confidence": 0.86
}
```

---

# 8. 带图片题目的处理方案

## 8.1 设计原则

带图片的题目不能只保存文字，必须同时保存：

1. 题干文本。
2. 图片资源路径。
3. Markdown 内容。
4. 图片描述。
5. 题目裁剪图。

## 8.2 Markdown 中保留图片引用

示例：

```md
### 第 5 题

如图，求阴影部分面积。

![第5题图形](assets/page_2_q5.png)
```

## 8.3 数据库存储建议

题目候选数据中保存：

```json
{
  "question_text": "如图，求阴影部分面积。",
  "markdown_content": "如图，求阴影部分面积。\n\n![第5题图形](assets/page_2_q5.png)",
  "image_urls": ["/uploads/tasks/10001/assets/page_2_q5.png"],
  "crop_image_url": "/uploads/tasks/10001/crops/page_2_q5.png",
  "image_description": "图中包含一个扇形和阴影区域。"
}
```

## 8.4 前端展示方式

前端确认页应展示：

```text
题目文本
+ 题目图片
+ AI 图片描述
+ 题库匹配结果
+ 用户确认按钮
```

不能只展示识别出的文字，否则用户无法确认几何题、统计图题、看图题是否正确。

---

# 9. 题库匹配设计

## 9.1 匹配目标

PDF 识别出的题目不建议直接入库，应先匹配系统题库。

匹配成功：

```text
关联已有 question_id，加入 user_wrong_questions。
```

匹配失败：

```text
进入“新题待确认”，用户确认后先写入 questions，再加入 user_wrong_questions。
```

## 9.2 匹配流程

```text
AI 识别题目
↓
提取关键词
↓
根据题干全文检索题库
↓
根据知识点、题型、难度过滤
↓
返回 Top 5 候选题
↓
用户选择或确认
```

## 9.3 相似度规则

建议综合以下因素：

| 因素 | 权重 |
|---|---:|
| 题干文本相似度 | 50% |
| 关键词匹配度 | 20% |
| 知识点一致性 | 15% |
| 题型一致性 | 10% |
| 难度一致性 | 5% |

匹配结果示例：

```json
{
  "matched_questions": [
    {
      "question_id": 1023,
      "similarity": 0.92,
      "question_text": "如图，长方形的长是12厘米，宽是8厘米，求阴影部分面积。",
      "knowledge_point": "几何面积",
      "difficulty": "中等"
    }
  ]
}
```

---

# 10. 前端交互设计

## 10.1 上传页面

在错题录入页面新增：

```text
录入方式：
- 手动选择题库
- 上传图片识别
- 上传 PDF 文件识别
```

PDF 上传区域：

```text
支持格式：PDF
文件大小：建议 ≤ 50MB
页数限制：建议 ≤ 30 页
说明：支持电子版 PDF、扫描版 PDF、带批改痕迹 PDF
```

## 10.2 任务进度页

上传后展示识别进度：

```text
文件名：六年级数学错题.pdf
文件类型：PDF
页数：12 页
当前状态：正在识别第 3 页
已识别候选题：8 道
需要确认：8 道
```

任务状态：

| 状态 | 说明 |
|---|---|
| pending | 已上传，等待处理 |
| processing | 正在解析和识别 |
| need_confirm | 识别完成，等待用户确认 |
| completed | 已确认并加入错题本 |
| failed | 识别失败 |

## 10.3 识别结果确认页

每一道候选错题展示：

```text
第 1 页 第 3 题

原图/题目截图
AI 识别题干
题型
知识点
难度
题库匹配候选
错误类型选择
考试名称
考试日期

[确认加入错题本]
[忽略]
[编辑识别结果]
[手动匹配题库]
[作为新题入库]
```

## 10.4 批量操作

支持：

1. 全选高置信度题目。
2. 批量确认加入错题本。
3. 批量忽略。
4. 只查看未匹配题。
5. 只查看带图题。
6. 只查看低置信度题。

---

# 11. 后端接口设计

## 11.1 上传 PDF 识别

```http
POST /api/wrong-questions/recognize-pdf
```

返回：

```json
{
  "task_id": 10001,
  "status": "processing",
  "message": "PDF 已上传，正在识别"
}
```

## 11.2 查询识别任务

```http
GET /api/wrong-questions/recognition-tasks/{task_id}
```

返回：

```json
{
  "task_id": 10001,
  "status": "need_confirm",
  "file_name": "六年级数学错题.pdf",
  "file_type": "pdf",
  "total_pages": 12,
  "total_candidates": 18,
  "success_count": 16,
  "failed_count": 2,
  "markdown_url": "/uploads/tasks/10001/document.md",
  "candidates": [
    {
      "candidate_id": 1,
      "page_no": 1,
      "question_no": "3",
      "recognized_text": "如图，长方形的长是12厘米，宽是8厘米，求阴影部分面积。",
      "markdown_content": "如图，长方形的长是12厘米，宽是8厘米，求阴影部分面积。\n\n![题图](assets/page_1_img_1.png)",
      "image_urls": ["/uploads/tasks/10001/assets/page_1_img_1.png"],
      "crop_image_url": "/uploads/tasks/10001/crops/page_1_q3.png",
      "question_type": "problem_solving",
      "knowledge_points": ["几何面积"],
      "difficulty": "中等",
      "confidence": 0.86,
      "matched_questions": [
        {
          "question_id": 1023,
          "similarity": 0.92,
          "question_text": "如图，长方形的长是12厘米，宽是8厘米，求阴影部分面积。"
        }
      ],
      "need_manual_confirm": true
    }
  ]
}
```

## 11.3 确认加入错题本

```http
POST /api/wrong-questions/recognition-tasks/{task_id}/confirm
```

请求：

```json
{
  "items": [
    {
      "candidate_id": 1,
      "question_id": 1023,
      "error_type": "计算错误",
      "exam_name": "六年级期中测试",
      "exam_date": "2026-05-12",
      "remark": "PDF识别导入"
    }
  ]
}
```

返回：

```json
{
  "success_count": 1,
  "failed_count": 0,
  "created_wrong_question_ids": [3001]
}
```

## 11.4 忽略候选题

```http
POST /api/wrong-questions/recognition-candidates/{candidate_id}/ignore
```

## 11.5 编辑候选题

```http
PUT /api/wrong-questions/recognition-candidates/{candidate_id}
```

---

# 12. 数据库设计

## 12.1 PDF 识别任务表

```sql
CREATE TABLE wrong_question_recognition_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_type VARCHAR(30) NOT NULL DEFAULT 'pdf',
    file_size BIGINT DEFAULT 0,
    total_pages INT DEFAULT 0,
    pdf_type VARCHAR(30) NULL COMMENT 'text_pdf/scanned_pdf/mixed_pdf',
    recognition_mode VARCHAR(30) DEFAULT 'auto',
    model_provider VARCHAR(50) DEFAULT 'zhipu',
    model_name VARCHAR(100) NULL,
    markdown_url VARCHAR(500) NULL,
    status VARCHAR(30) DEFAULT 'pending',
    total_candidates INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    error_message TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 12.2 识别候选题表

```sql
CREATE TABLE wrong_question_recognition_candidates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id INT NOT NULL,
    user_id INT NOT NULL,
    page_no INT NULL,
    question_no VARCHAR(50) NULL,
    source_type VARCHAR(50) COMMENT 'pdf_text/pdf_page_image/pdf_crop/pdf_asset',
    unit_index INT DEFAULT 0,
    raw_text TEXT NULL,
    recognized_text TEXT NULL,
    markdown_content TEXT NULL,
    image_urls JSON NULL,
    page_image_url VARCHAR(500) NULL,
    crop_image_url VARCHAR(500) NULL,
    image_description TEXT NULL,
    question_type VARCHAR(50) NULL,
    knowledge_points JSON NULL,
    category VARCHAR(100) NULL,
    difficulty VARCHAR(50) NULL,
    answer TEXT NULL,
    analysis TEXT NULL,
    keywords JSON NULL,
    ai_result JSON NULL,
    ai_raw_response JSON NULL,
    confidence FLOAT NULL,
    matched_question_id INT NULL,
    match_similarity FLOAT NULL,
    status VARCHAR(30) DEFAULT 'need_confirm',
    created_wrong_question_id INT NULL,
    error_message TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 12.3 错题表补充字段

如果 `user_wrong_questions` 中还没有来源字段，建议增加：

```sql
ALTER TABLE user_wrong_questions
ADD COLUMN source_type VARCHAR(50) DEFAULT 'manual' COMMENT 'manual/image/pdf/docx/practice',
ADD COLUMN source_task_id INT NULL COMMENT '来源识别任务ID',
ADD COLUMN source_candidate_id INT NULL COMMENT '来源候选题ID',
ADD COLUMN original_file_url VARCHAR(500) NULL COMMENT '原始文件地址',
ADD COLUMN crop_image_url VARCHAR(500) NULL COMMENT '错题截图地址';
```

## 12.4 题目图片附件表

为了支持带图题，建议新增：

```sql
CREATE TABLE question_assets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    question_id INT NOT NULL,
    asset_type VARCHAR(30) DEFAULT 'image',
    asset_url VARCHAR(500) NOT NULL,
    asset_desc TEXT NULL,
    source_candidate_id INT NULL,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

# 13. 后端模块拆分建议

建议新增以下服务模块：

```text
app/services/pdf_recognition/
├── pdf_detector.py          # 判断 PDF 类型
├── pdf_text_extractor.py    # 提取电子版 PDF 文本
├── pdf_image_converter.py   # PDF 转图片
├── markdown_builder.py      # 生成 Markdown
├── asset_extractor.py       # 提取 PDF 图片资源
├── question_segmenter.py    # 按题切分
├── zhipu_recognizer.py      # 调用智谱模型识别
├── question_matcher.py      # 题库匹配
└── task_service.py          # 识别任务调度
```

## 13.1 核心伪代码

```python
def recognize_pdf_wrong_questions(user_id: int, pdf_file):
    task = create_recognition_task(user_id, pdf_file)

    pdf_type = detect_pdf_type(pdf_file.path)
    update_task(task.id, pdf_type=pdf_type, status="processing")

    if pdf_type == "text_pdf":
        units = process_text_pdf(pdf_file.path, task.id)
    else:
        units = process_scanned_pdf(pdf_file.path, task.id)

    candidates = []

    for unit in units:
        try:
            ai_result = recognize_unit_with_zhipu(unit)
            candidate = create_candidate(task.id, user_id, unit, ai_result)
            matched = match_question_bank(ai_result)
            update_candidate_match(candidate.id, matched)
            candidates.append(candidate)
        except Exception as e:
            create_failed_candidate(task.id, user_id, unit, str(e))

    update_task_summary(task.id)
    return task
```

## 13.2 识别单元结构

```python
class RecognitionUnit:
    unit_id: str
    content_type: str  # text/image/mixed
    source_type: str   # pdf_text/pdf_page_image/pdf_crop
    page_no: int
    question_no: str
    raw_text: str
    markdown_content: str
    image_urls: list[str]
    crop_image_url: str
```

---

# 14. 异常处理设计

需要处理以下情况：

| 异常 | 处理方式 |
|---|---|
| PDF 文件过大 | 限制大小，提示压缩或拆分上传 |
| PDF 页数过多 | 限制页数，建议分批上传 |
| PDF 加密 | 返回“文件加密，无法识别” |
| PDF 无文本且图片质量差 | 提示重新上传高清版本 |
| 智谱模型调用失败 | 标记当前页失败，允许重试 |
| 单题识别置信度低 | 进入人工确认 |
| 题库匹配失败 | 允许作为新题入库 |
| 重复错题 | 不重复创建，提示已存在并更新来源 |

---

# 15. 性能与体验优化

## 15.1 异步任务处理

PDF 可能有多页，识别耗时较长，建议异步执行。

方案：

```text
前端上传 PDF
↓
后端立即返回 task_id
↓
后台异步识别
↓
前端轮询任务状态
↓
识别完成后进入确认页
```

可选技术：

```text
Celery + Redis
FastAPI BackgroundTasks
RQ
自定义任务队列
```

## 15.2 分页识别

对于多页 PDF，建议逐页处理，并实时更新进度。

```json
{
  "task_id": 10001,
  "status": "processing",
  "current_page": 5,
  "total_pages": 12,
  "progress": 41
}
```

## 15.3 成本控制

1. 电子版 PDF 优先走文本提取，减少视觉模型调用。
2. 扫描版 PDF 先压缩图片，再传模型。
3. 对空白页、封面页、答案页可自动跳过。
4. 对已经匹配到题库的题目，不重复调用大模型。
5. 对低价值页设置人工选择再识别。

---

# 16. 安全与限制

建议限制：

| 项目 | 建议限制 |
|---|---|
| PDF 大小 | 50MB 以内 |
| 单次页数 | 30 页以内 |
| 图片 DPI | 200~300 DPI |
| 单页模型调用超时 | 60 秒 |
| 支持格式 | 仅 PDF |

文件安全：

1. 校验文件 MIME 类型。
2. 禁止执行 PDF 中的脚本或嵌入对象。
3. 文件名重命名，避免路径注入。
4. 用户只能访问自己的识别任务。
5. 定期清理临时页面图和中间文件。

---

# 17. 开发阶段规划

## 第一阶段：基础 PDF 上传识别

目标：支持 PDF 上传并生成候选错题。

任务：

1. 新增 PDF 上传接口。
2. 新增识别任务表。
3. 实现 PDF 类型判断。
4. 实现电子版 PDF 文本提取。
5. 实现扫描版 PDF 转图片。
6. 接入智谱模型识别页面或单题。
7. 返回候选错题列表。

建议周期：3~5 天。

---

## 第二阶段：Markdown 中间格式与图片资源处理

目标：解决带图题、几何题、统计图题的问题。

任务：

1. 生成 document.md。
2. 抽取 PDF 图片资源。
3. Markdown 中保留图片引用。
4. 候选题保存 markdown_content 和 image_urls。
5. 前端支持 Markdown + 图片预览。

建议周期：3~5 天。

---

## 第三阶段：题库匹配与用户确认

目标：提升入库准确率。

任务：

1. 实现题干关键词提取。
2. 实现题库相似度匹配。
3. 返回 Top 5 候选题。
4. 前端确认加入错题本。
5. 支持编辑识别结果、手动匹配、忽略。
6. 支持重复错题检测。

建议周期：4~6 天。

---

## 第四阶段：识别质量优化

目标：提升复杂 PDF 的识别效果。

任务：

1. 支持带批改痕迹 PDF 的红色批改弱化。
2. 支持用户手动框选题目区域。
3. 支持逐页重试识别。
4. 支持低置信度筛选。
5. 优化智谱 Prompt。
6. 统计识别准确率和用户确认率。

建议周期：5~7 天。

---

# 18. 推荐第一版落地方案

第一版不要做得过重，建议先实现以下最小可用版本：

```text
1. 用户上传 PDF
2. 系统判断 PDF 类型
3. 电子版 PDF：提取文本并按题号切分
4. 扫描版 PDF：转图片后调用智谱视觉模型
5. 生成候选错题列表
6. 匹配题库 Top 5
7. 用户确认后加入错题本
```

第一版可暂缓：

```text
1. 自动精准切题
2. 复杂表格还原
3. 自动去除所有批改痕迹
4. 完全自动入库
5. Excel / Word 文件支持
```

---

# 19. 最终推荐架构

最终建议架构如下：

```text
PDF 文件上传
↓
识别任务创建
↓
PDF 类型判断
├── 电子版 PDF
│   ├── 文本提取
│   ├── 图片抽取
│   └── Markdown 生成
│
└── 扫描版 PDF
    ├── PDF 转图片
    ├── 图片预处理
    ├── 智谱视觉识别
    └── Markdown 生成
↓
候选题结构化
↓
题库相似匹配
↓
前端人工确认
↓
写入错题本
```

一句话总结：

> PDF 识别错题功能应采用“PDF 解析 + Markdown 中间格式 + 图片资源保留 + 智谱模型结构化识别 + 题库匹配 + 用户确认”的方案。这样既能处理电子版 PDF，也能处理扫描版 PDF 和带图片的数学题，同时保证错题入库的准确性。
