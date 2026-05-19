# PDF 识别功能改进说明

## 改进概述

按照新的设计思路，改进了 PDF 识别流程，实现了智能判断文字/图片类型，并支持题目图片保留和答案解析生成。

## 改进内容

### 1. 智能 PDF 识别流程

**新流程：**
```
PDF 上传
    ↓
判断 PDF 类型
    ↓
如果能提取文字：
    PDF → Markdown → DeepSeek 结构化
    ↓
如果不能提取文字（扫描件）：
    PDF → OCR 提取文字 → Markdown → DeepSeek 结构化
    ↓
如果题目带图片：
    提取 PDF 中的图片
    Markdown 保留图片引用
    数据库保存 image_urls
    前端展示图片供用户确认
```

**关键改进：**
- ✅ 自动检测 PDF 是否有文本层
- ✅ 有文本层：直接提取文字转 Markdown（快速、准确）
- ✅ 无文本层（扫描件）：使用 Tesseract OCR 提取文字转 Markdown
- ✅ **不再将 PDF 转成图片进行视觉识别**，统一使用文字提取 + LLM 结构化
- ✅ 自动提取 PDF 中的图片（如几何图形、示意图）
- ✅ 图片与题目关联保存

### 2. 数据库模型更新

**新增字段：**

`wrong_question_recognition_blocks` 表：
- `question_image_urls` (TEXT): 题目中的图片 URL 列表（JSON 数组）
- `ai_answer` (TEXT): AI 生成的答案
- `ai_solution` (TEXT): AI 生成的详细解析

**迁移脚本：**
```sql
-- 位置：backend/migrations/add_question_image_urls.sql
ALTER TABLE wrong_question_recognition_blocks
ADD COLUMN question_image_urls TEXT DEFAULT NULL;

ALTER TABLE wrong_question_recognition_blocks
ADD COLUMN ai_answer TEXT DEFAULT NULL;

ALTER TABLE wrong_question_recognition_blocks
ADD COLUMN ai_solution TEXT DEFAULT NULL;
```

### 3. 代码改进

#### 3.1 `pdf_to_markdown.py`

**新增功能：**
- `pdf_to_markdown()` 返回元组 `(markdown_text, used_ocr)`，标识是否使用了 OCR
- 新增 `_ocr_page()` 函数：使用 Tesseract OCR 提取扫描页文字
- 新增 `_attach_images_to_questions()` 函数：将 PDF 图片关联到题目
- `extract_questions_from_markdown()` 支持传入 `pdf_images` 参数

**OCR 支持：**
```python
# 当 PDF 页面没有文本层时，自动使用 OCR
if not text_blocks and not plain_text.strip():
    if use_ocr_fallback and TESSERACT_AVAILABLE:
        ocr_text = _ocr_page(page)
        # 使用 OCR 提取的文字继续处理
```

#### 3.2 `wrong_questions.py`

**改进识别流程：**
```python
# 1. 转换 PDF 为 Markdown（自动 OCR 后备）
markdown_text, used_ocr = pdf_to_markdown(pdf_bytes, use_ocr_fallback=True)

# 2. 提取 PDF 中的图片
pdf_images = extract_images_from_pdf(pdf_bytes)

# 3. 使用 LLM 提取题目（传入图片）
questions = await extract_questions_from_markdown(markdown_text, call_text_llm, pdf_images)

# 4. 保存题目、答案、解析、图片
for q in questions:
    block = WrongQuestionRecognitionBlock(
        ai_question_text=q.get("question_text"),
        ai_answer=q.get("answer"),
        ai_solution=q.get("solution"),
        question_image_urls=json.dumps(q.get("image_urls", [])),
        ...
    )
```

### 4. LLM 提示词优化

**系统提示词要求：**
1. 识别所有题目（通过题号）
2. 提取完整题目内容
3. **生成完整答案（含单位）**
4. **生成详细解析（小学生能看懂每一步）**
5. 判断题型、知识点、难度
6. 检测题目是否包含图片（"如图"、"图中"等关键词）

**输出格式：**
```json
{
  "questions": [
    {
      "question_no": "1",
      "question_text": "完整题目内容",
      "answer": "答案（含单位）",
      "solution": "分步解析",
      "question_type": "fill_blank|choice|calculation|problem_solving|other",
      "difficulty": "基础|中等|挑战",
      "knowledge_point": "具体知识点",
      "has_image": false,
      "is_complete": true,
      "confidence": 0.95
    }
  ]
}
```

## 使用说明

### 1. 运行数据库迁移

```bash
cd backend
mysql -u root -p math_bank < migrations/add_question_image_urls.sql
```

### 2. 安装 Tesseract OCR（可选，用于扫描件识别）

**Windows:**
```bash
# 下载安装：https://github.com/UB-Mannheim/tesseract/wiki
# 安装后添加到 PATH 环境变量
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim
```

**Python 依赖：**
```bash
pip install pytesseract
```

### 3. 重启后端服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 功能特性

### ✅ 已实现

1. **智能 PDF 类型检测**
   - 自动判断 PDF 是否有文本层
   - 有文本：直接提取（快速）
   - 无文本：OCR 提取（扫描件）

2. **题目图片支持**
   - 自动提取 PDF 中的图片
   - 图片与题目关联保存
   - 数据库保存图片 URL 列表

3. **答案和解析生成**
   - AI 自动生成完整答案
   - AI 生成详细解析（分步骤）
   - 保存到数据库供前端展示

4. **错误处理优化**
   - Markdown 提取失败自动降级到图片识别
   - OCR 失败有明确提示
   - 日志记录详细，便于调试

### 🔄 待前端配合

1. **展示题目图片**
   - 读取 `question_image_urls` 字段
   - 在题目详情页展示图片

2. **展示答案和解析**
   - 读取 `ai_answer` 和 `ai_solution` 字段
   - 在错题详情页展示

3. **识别模式提示**
   - 显示是否使用了 OCR（`recognition_mode` 字段）
   - 提示用户识别方式

## 技术栈

- **PDF 文本提取**: PyMuPDF (fitz)
- **OCR 引擎**: Tesseract OCR
- **LLM**: DeepSeek / GLM-4
- **图片处理**: PIL (Pillow)
- **数据库**: MySQL

## 性能对比

| 方式 | 速度 | 准确度 | 适用场景 |
|------|------|--------|----------|
| 文字提取 | ⚡⚡⚡ 快 | ⭐⭐⭐ 高 | 电子版 PDF |
| OCR 提取 | ⚡⚡ 中 | ⭐⭐ 中 | 扫描件 PDF |
| 图片识别（旧） | ⚡ 慢 | ⭐ 低 | 已废弃 |

## 注意事项

1. **OCR 依赖**：扫描件识别需要安装 Tesseract OCR
2. **图片大小**：PDF 中的图片会被提取并保存，注意存储空间
3. **识别准确度**：OCR 识别准确度取决于扫描质量
4. **LLM Token 消耗**：文字提取方式比图片识别节省 Token

## 后续优化方向

1. 支持更多 OCR 引擎（PaddleOCR、EasyOCR）
2. 图片压缩和优化
3. 批量 PDF 识别
4. 识别结果缓存
5. 前端实时预览识别进度
