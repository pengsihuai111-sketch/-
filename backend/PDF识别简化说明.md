# PDF识别简化说明

## 改动概述

根据用户反馈，PDF识别流程已简化，**强制使用纯文本Markdown方式进行识别，不再fallback到图片识别模式**。

## 改动原因

1. **图片识别模式问题多**
   - 将PDF每页转换成图片进行识别
   - 识别速度慢、准确率低
   - 用户体验差（看到页面截图）

2. **纯文本识别更直接、更准确**
   - PDF转Markdown后，文本内容完整清晰
   - LLM可以直接从文本中提取题目、答案、解析
   - 减少图片处理的性能开销

3. **用户体验更好**
   - 识别速度更快（无需图片转换）
   - 结果更稳定（不依赖视觉识别）
   - 减少存储空间占用

## 修改的文件

### 1. `backend/app/api/wrong_questions.py`

**修改位置1**：`recognize_pdf_async` 函数（第1141-1213行）- 移除PDF图片提取

**修改内容**：
```python
# 移除前：
# Extract images from PDF (for questions with diagrams)
from ..utils.pdf_to_markdown import extract_images_from_pdf
pdf_images = extract_images_from_pdf(pdf_bytes, max_pages=30)
logger.info(f"Extracted images from {len(pdf_images)} pages")

# Extract questions using LLM
questions = await extract_questions_from_markdown(markdown_text, call_text_llm, pdf_images)

# 修改后：
# Extract questions using LLM (no image extraction, pure markdown mode)
questions = await extract_questions_from_markdown(markdown_text, call_text_llm, pdf_images=None)
```

**修改位置2**：`recognize_pdf_async` 函数（第1214-1227行）- 移除fallback逻辑

**修改内容**：
```python
# 移除前：
except ValueError as e:
    # PDF is scanned or has no extractable text - fall through to image recognition
    logger.warning(f"Markdown extraction failed: {e}, falling back to image recognition")
    db.rollback()
    # Don't return here, let it fall through to Method 2

# 修改后：
except ValueError as e:
    # PDF is scanned or has no extractable text - return error instead of fallback
    logger.warning(f"Markdown extraction failed: {e}")
    db.rollback()
    raise HTTPException(
        status_code=400,
        detail=f"PDF识别失败：{str(e)}。建议使用截图识别功能对单个题目进行识别。"
    )
```

**修改位置3**：`recognize_pdf_async` 函数（第1228-1283行）- 限制图片模式只在明确请求时使用

**修改内容**：
```python
# 修改前：
# Method 2: Image-based recognition (fallback for scanned PDFs)
logger.info("Using image-based recognition for PDF (scanned document or markdown extraction failed)")
try:
    page_images = pdf_to_images(pdf_bytes)
    # ... 后续处理

# 修改后：
# Method 2: Image-based recognition (only when use_markdown=False)
if not use_markdown:
    logger.info("Using image-based recognition for PDF (user explicitly requested)")
    try:
        page_images = pdf_to_images(pdf_bytes)
        # ... 后续处理
else:
    # use_markdown=True but we reached here - should not happen
    raise HTTPException(
        status_code=400,
        detail="PDF Markdown识别模式已启用，但未能成功识别。请检查PDF格式。"
    )
```

### 2. `backend/app/utils/pdf_to_markdown.py`

**修改1**：`extract_questions_from_markdown` 函数文档

```python
# 修改前：
"""Extract structured questions from markdown text using LLM.

Args:
    markdown_text: Markdown-formatted text from PDF
    llm_caller: Async function to call text LLM
    pdf_images: Optional dict mapping page_num -> list of image bytes

Returns:
    List of question dicts with question_text, answer, solution, image_urls, etc.
"""

# 修改后：
"""Extract structured questions from markdown text using LLM.

Args:
    markdown_text: Markdown-formatted text from PDF
    llm_caller: Async function to call text LLM
    pdf_images: Deprecated parameter, no longer used (kept for compatibility)

Returns:
    List of question dicts with question_text, answer, solution, etc.
"""
```

**修改2**：LLM提示词（system_prompt）

移除了以下规则：
- ~~如果题目提到"如图"、"图中"、"下图"但文本中没有图形描述，设置 has_image=true~~

移除了JSON输出中的字段：
- ~~"has_image": false~~

**修改3**：用户提示词（user_prompt）

移除了以下提示：
- ~~如果看到"如图"、"图中"等字样，设置 has_image=true~~

**修改4**：移除图片附加逻辑

```python
# 移除前：
# If PDF has images, save them and add references to questions
if pdf_images:
    questions = _attach_images_to_questions(questions, pdf_images)

# 修改后：
# 直接返回questions，不再附加图片
```

## 保留的功能

### `_attach_images_to_questions` 函数

虽然不再使用，但函数代码保留在文件中，以便将来需要时可以恢复。

### `extract_images_from_pdf` 函数

同样保留，但不再被调用。

### 数据库字段

以下字段保留但不再使用：
- `question_image_urls` - 题目图片URLs（JSON数组）

## 工作流程

### 修改前的流程

```
PDF文件 (use_markdown=true)
  ↓
PDF转Markdown（文本提取）
  ↓
提取PDF中的图片 ← 已移除
  ↓
LLM识别题目
  ↓
根据页码匹配图片到题目 ← 已移除
  ↓
如果失败 → fallback到图片识别模式 ← 已移除
  ↓
PDF转图片（每页一张）
  ↓
视觉识别每一页
```

### 修改后的流程

```
PDF文件 (use_markdown=true，前端默认)
  ↓
PDF转Markdown（文本提取 + OCR fallback）
  ↓
LLM识别题目（纯文本）
  ↓
保存题目（答案+解析）
  ↓
如果失败 → 返回错误，提示使用截图识别
```

**关键改变**：
- ✅ 移除了PDF图片提取逻辑
- ✅ 移除了图片-题目匹配逻辑  
- ✅ **移除了fallback到图片识别模式的逻辑**
- ✅ Markdown识别失败时直接返回错误，不再自动转换为图片识别

## 优势对比

| 方面 | 修改前 | 修改后 |
|------|--------|--------|
| **识别准确率** | 低（图片识别不准确） | 高（纯文本识别） |
| **识别速度** | 很慢（PDF转图片+视觉识别） | 快（只处理文本） |
| **存储空间** | 大（保存每页图片） | 小（只保存文本） |
| **维护复杂度** | 高（两种模式+fallback逻辑） | 低（纯文本处理） |
| **错误率** | 高（图片识别+fallback） | 低（文本提取稳定） |
| **用户体验** | 差（看到页面截图） | 好（直接看到题目） |

## 行为变化

### 之前的行为

1. 用户上传PDF（前端设置 `use_markdown=true`）
2. 后端尝试Markdown识别
3. **如果失败，自动fallback到图片识别模式**
4. 用户看到PDF每页的截图
5. 识别速度慢、准确率低

### 现在的行为

1. 用户上传PDF（前端设置 `use_markdown=true`）
2. 后端尝试Markdown识别
3. **如果失败，返回错误提示**
4. 提示用户："PDF识别失败，建议使用截图识别功能对单个题目进行识别"
5. 用户可以选择截图识别单个题目

## 适用场景

### 适合纯文本识别的PDF

✅ **适合**：
- 电子版试卷（Word/LaTeX生成的PDF）
- 文本清晰的扫描件（OCR效果好）
- 纯文字题目（无图表、无几何图形）

❌ **不适合**：
- 包含大量图表的题目
- 几何题（需要看图）
- 函数图像题
- 统计图表题

### 对于包含图片的题目

如果PDF中的题目包含图片（如几何图形、函数图像等），建议：

1. **使用截图识别功能**
   - 对单个题目进行截图
   - 上传截图进行识别
   - 支持图像增强，识别更准确

2. **手动录入**
   - 对于复杂的图形题
   - 可以先识别文本部分
   - 再手动补充图片相关内容

## 后续优化建议

### 短期优化

1. **改进OCR质量**
   - 对扫描件PDF使用更好的OCR引擎
   - 提高文本提取准确率

2. **优化LLM提示词**
   - 提高题目识别准确率
   - 改进答案和解析的质量

### 长期优化

1. **智能识别模式选择**
   - 自动检测PDF是否包含图片
   - 如果包含图片，提示用户使用截图识别
   - 如果纯文本，使用Markdown识别

2. **混合识别模式**
   - 文本部分使用Markdown识别
   - 图片部分使用视觉识别
   - 最后合并结果

## 测试建议

### 测试用例

1. **纯文字PDF**
   - 上传纯文字试卷PDF
   - 验证题目、答案、解析是否完整
   - 验证识别速度是否提升

2. **扫描件PDF**
   - 上传扫描件PDF
   - 验证OCR是否正常工作
   - 验证识别准确率

3. **包含图片的PDF**
   - 上传包含图片的PDF
   - 观察识别结果（可能缺少图片相关内容）
   - 验证是否需要使用截图识别补充

### 预期结果

- ✅ 识别速度提升 50%+
- ✅ 存储空间减少 80%+
- ✅ 纯文字题目识别准确率 95%+
- ⚠️ 包含图片的题目可能需要额外处理

## 回滚方案

如果需要恢复图片提取功能：

1. 在 `wrong_questions.py` 中恢复图片提取代码：
```python
from ..utils.pdf_to_markdown import extract_images_from_pdf
pdf_images = extract_images_from_pdf(pdf_bytes, max_pages=30)
questions = await extract_questions_from_markdown(markdown_text, call_text_llm, pdf_images)
```

2. 在 `pdf_to_markdown.py` 中恢复提示词中的 `has_image` 字段

3. 在 `extract_questions_from_markdown` 中恢复图片附加逻辑：
```python
if pdf_images:
    questions = _attach_images_to_questions(questions, pdf_images)
```

## 总结

这次简化移除了PDF识别中复杂且容易出错的图片提取和匹配逻辑，改为纯文本Markdown识别方式。这样做的好处是：

1. **更快** - 无需图片处理
2. **更准** - 文本识别更稳定
3. **更简** - 代码逻辑更清晰
4. **更省** - 减少存储空间

对于包含图片的题目，建议使用截图识别功能进行单题识别。
