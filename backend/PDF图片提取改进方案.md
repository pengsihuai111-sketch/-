# PDF图片提取改进方案

## 问题分析

### 当前问题
用户反馈：PDF识别时截取的图片一直不全或不对，导致识别题目不正确

### 根本原因
当前的图片提取逻辑存在以下问题：

1. **图片分配不准确**
   - 提取PDF所有页面的所有图片
   - 将所有图片统一分配给标记了 `has_image=true` 的题目
   - 无法判断哪张图片属于哪道题

2. **图片顺序混乱**
   - 多页PDF的图片混在一起
   - 无法保证图片顺序与题目顺序一致

3. **图片冗余**
   - 一道题可能获得所有图片（包括不相关的）
   - 浪费存储空间，影响显示效果

### 代码位置
- `app/utils/pdf_to_markdown.py:385-419` - `extract_images_from_pdf()` 函数
- `app/utils/pdf_to_markdown.py:325-360` - `_attach_images_to_questions()` 函数

---

## 改进方案

### 方案1：基于页面的图片分配（推荐）

**核心思路**：
1. 在提取文本时，记录每道题所在的页码范围
2. 只将题目所在页面的图片分配给该题目
3. 保持图片在页面中的原始顺序

**优点**：
- 准确率高：图片和题目在同一页，关联性强
- 实现简单：只需记录题目页码
- 性能好：减少不必要的图片保存

**缺点**：
- 如果题目跨页，可能遗漏图片
- 需要修改LLM提示词，让其返回题目页码

### 方案2：基于位置的图片匹配（精确但复杂）

**核心思路**：
1. 提取图片时记录其在页面中的坐标位置
2. 提取文本时记录题目的坐标位置
3. 根据坐标判断图片是否在题目范围内

**优点**：
- 最精确：基于实际位置匹配
- 支持复杂布局（多栏、混排）

**缺点**：
- 实现复杂：需要处理坐标计算
- 性能开销大：需要分析所有元素位置
- 对PDF格式要求高：扫描件无法获取准确坐标

### 方案3：基于视觉识别的图片分类（AI驱动）

**核心思路**：
1. 提取所有图片
2. 使用视觉模型识别每张图片的内容
3. 根据题目内容和图片内容的语义相似度匹配

**优点**：
- 最智能：理解图片和题目的语义关系
- 适用于所有PDF类型

**缺点**：
- 成本高：每张图片都需要调用视觉API
- 速度慢：增加识别时间
- 准确率依赖模型能力

---

## 推荐实施方案

### 阶段1：基于页面的图片分配（立即实施）

#### 1.1 修改LLM提示词，返回题目页码

修改 `pdf_to_markdown.py:242-286` 的 `system_prompt`：

```python
输出纯 JSON：
{
  "questions": [
    {
      "question_no": "题号（如：1、一、(1)、①）",
      "question_text": "完整题目内容",
      "page_no": 1,  # 新增：题目所在页码（从1开始）
      "answer": "答案（含单位）",
      "solution": "分步解析",
      ...
    }
  ]
}
```

#### 1.2 修改图片附加逻辑

修改 `_attach_images_to_questions()` 函数：

```python
def _attach_images_to_questions(questions: List[Dict], pdf_images: Dict[int, List[bytes]]) -> List[Dict]:
    """根据页码将图片精确分配给题目"""
    from ..config import IMAGE_DIR
    import os
    import uuid

    os.makedirs(IMAGE_DIR, exist_ok=True)

    # 为每道题分配其所在页面的图片
    for q in questions:
        if not q.get("has_image"):
            continue
        
        # 获取题目所在页码（从1开始，转换为0索引）
        page_no = q.get("page_no", 1) - 1
        
        # 如果题目跨页，也包含下一页的图片
        page_range = [page_no]
        if q.get("spans_pages"):  # 可选：LLM标记跨页题目
            page_range.append(page_no + 1)
        
        # 收集相关页面的图片
        question_images = []
        for p in page_range:
            if p in pdf_images:
                for img_idx, img_bytes in enumerate(pdf_images[p]):
                    img_name = f"pdf_img_{uuid.uuid4().hex[:8]}_p{p+1}_{img_idx+1}.png"
                    img_path = os.path.join(IMAGE_DIR, img_name)
                    with open(img_path, "wb") as f:
                        f.write(img_bytes)
                    question_images.append(f"/uploads/images/{img_name}")
                    logger.info(f"Saved image for question {q.get('question_no')}: {img_name}")
        
        q["image_urls"] = question_images
        logger.info(f"Attached {len(question_images)} images to question {q.get('question_no')} (page {page_no+1})")

    return questions
```

#### 1.3 优化：过滤无关图片

添加图片尺寸和类型过滤，排除装饰性图片：

```python
def extract_images_from_pdf(pdf_bytes: bytes, max_pages: int = 30, min_size: int = 5000) -> Dict[int, List[bytes]]:
    """提取PDF图片，过滤小尺寸装饰图"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    page_images = {}

    for page_num in range(total_pages):
        page = doc[page_num]
        images = page.get_images()

        if not images:
            continue

        page_images[page_num] = []

        for img_index, img_info in enumerate(images):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # 过滤小图片（可能是装饰、图标等）
                if len(image_bytes) < min_size:
                    logger.info(f"Skipped small image on page {page_num + 1}: {len(image_bytes)} bytes")
                    continue
                
                # 检查图片尺寸
                img_width = base_image.get("width", 0)
                img_height = base_image.get("height", 0)
                if img_width < 50 or img_height < 50:
                    logger.info(f"Skipped tiny image on page {page_num + 1}: {img_width}x{img_height}")
                    continue
                
                page_images[page_num].append(image_bytes)
                logger.info(f"Extracted image {img_index + 1} from page {page_num + 1}: {len(image_bytes)} bytes, {img_width}x{img_height}")
                
            except Exception as e:
                logger.warning(f"Failed to extract image {img_index + 1} from page {page_num + 1}: {e}")

    doc.close()
    return page_images
```

---

## 实施步骤

### Step 1: 修改图片提取函数（添加过滤）
- 文件：`app/utils/pdf_to_markdown.py`
- 函数：`extract_images_from_pdf()`
- 修改：添加尺寸过滤，排除装饰图

### Step 2: 修改LLM提示词（返回页码）
- 文件：`app/utils/pdf_to_markdown.py`
- 函数：`extract_questions_from_markdown()`
- 修改：在 `system_prompt` 中要求返回 `page_no` 字段

### Step 3: 修改图片附加逻辑（基于页码）
- 文件：`app/utils/pdf_to_markdown.py`
- 函数：`_attach_images_to_questions()`
- 修改：根据题目页码只附加相关页面的图片

### Step 4: 测试验证
- 准备包含图片的PDF测试文件
- 验证图片是否正确匹配到题目
- 检查是否有遗漏或错误的图片

---

## 预期效果

### 改进前
- ❌ 所有图片分配给所有标记 `has_image=true` 的题目
- ❌ 第1题可能显示第3页的图片
- ❌ 包含大量无关的装饰图片

### 改进后
- ✅ 每道题只获得其所在页面的图片
- ✅ 图片和题目在同一页，关联性强
- ✅ 过滤掉小尺寸装饰图片
- ✅ 减少存储空间和显示混乱

---

## 后续优化方向

### 优化1：智能图片排序
- 根据图片在页面中的Y坐标排序
- 确保图片顺序与题目顺序一致

### 优化2：图片内容识别
- 使用视觉模型识别图片类型（几何图形、表格、照片等）
- 优先保留几何图形和表格，过滤照片和装饰

### 优化3：跨页题目处理
- 让LLM标记跨页题目
- 自动包含相邻页面的图片

### 优化4：用户反馈机制
- 允许用户手动调整图片-题目关联
- 收集反馈数据优化匹配算法

---

## 风险和注意事项

1. **LLM可能无法准确返回页码**
   - 缓解：在提示词中强调页码的重要性
   - 备用：如果没有页码，回退到当前逻辑

2. **跨页题目可能遗漏图片**
   - 缓解：检测题目是否跨页，包含相邻页图片
   - 备用：允许用户手动添加图片

3. **过滤可能误删有用图片**
   - 缓解：设置合理的尺寸阈值（5KB，50x50像素）
   - 备用：提供"显示所有图片"选项

4. **性能影响**
   - 当前方案不会增加性能开销
   - 反而减少了不必要的图片保存

---

## 测试用例

### 用例1：单页单题带图
- PDF：1页，1道题，1张图
- 预期：题目正确关联到图片

### 用例2：单页多题带图
- PDF：1页，3道题，2张图
- 预期：每道题只显示本页图片

### 用例3：多页多题带图
- PDF：3页，每页2道题，每页1张图
- 预期：第1页的题只显示第1页的图

### 用例4：跨页题目
- PDF：题目从第2页末尾延续到第3页开头
- 预期：题目显示第2页和第3页的图片

### 用例5：装饰图片过滤
- PDF：包含小logo、页眉图标等
- 预期：只保留题目相关的大图片

---

## 总结

**推荐方案**：基于页面的图片分配（方案1）

**实施难度**：中等（需要修改3个函数）

**预期效果**：显著提升图片-题目匹配准确率

**实施时间**：约1-2小时

**风险等级**：低（有备用逻辑）
