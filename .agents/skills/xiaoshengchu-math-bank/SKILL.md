---
name: xiaoshengchu-math-bank
description: 小升初数学题库管理系统。Vue 3 + Element Plus + FastAPI + MySQL。支持题库浏览与录入(OCR/PDF识别)、错题管理、练习单生成(PDF)、学情诊断。当用户提到"题库"、"错题"、"练习单"、"组卷"、"诊断"、"PDF"、"录入"、"识别"等时触发。
---

# 小升初数学题库管理系统

## 项目结构

```
math_bank_v4/
├── frontend/                          # Vue 3 前端
│   ├── src/
│   │   ├── api/                       # Axios 封装
│   │   │   ├── request.js             # Axios 实例 + 401 拦截器
│   │   │   ├── auth.js                # 登录/注册
│   │   │   ├── question.js            # 题目 CRUD + OCR + PDF 识别
│   │   │   └── practice.js            # 练习单 + 错题 + 诊断 + 支付
│   │   ├── views/
│   │   │   ├── Questions.vue          # 题库浏览（筛选+分页+详情弹窗）
│   │   │   ├── QuestionInput.vue      # 题目录入（单题/批量/OCR/PDF 四标签页）
│   │   │   ├── WrongQuestions.vue     # 错题管理（手动/OCR录入+反馈+统计）
│   │   │   ├── Practice.vue           # 练习单（生成+查看+下载PDF）
│   │   │   ├── Diagnosis.vue          # 学情诊断报告
│   │   │   ├── Dashboard.vue          # 首页统计
│   │   │   ├── Member.vue             # 会员中心
│   │   │   ├── Login.vue / Register.vue
│   │   ├── components/Layout.vue      # 侧边栏+顶栏布局
│   │   ├── router/index.js            # 路由 + beforeEach 鉴权守卫
│   │   └── utils/
│   │       ├── storage.js             # localStorage 封装
│   │       └── math.js                # KaTeX 公式渲染工具
│   └── vite.config.js                 # Vite proxy /api -> localhost:8000
│
├── backend/
│   └── app/
│       ├── main.py                    # FastAPI 入口 + CORS
│       ├── config.py                  # 环境配置
│       ├── database.py                # SQLAlchemy 引擎
│       ├── models/__init__.py         # 所有 ORM 模型 + 枚举
│       ├── schemas/__init__.py        # Pydantic 请求/响应模型
│       ├── api/
│       │   ├── auth.py                # /api/auth/*
│       │   ├── questions.py           # /api/questions/*
│       │   ├── practice.py            # /api/practice/*
│       │   ├── wrong_questions.py     # /api/wrong-questions/*
│       │   └── payment.py             # /api/payment/*
│       └── utils/
│           ├── auth.py                # JWT 生成/验证
│           ├── deepseek.py            # Codex API 题目识别
│           └── kimi.py                # Kimi API 错题识别
│
└── database/
    └── migrate_v3_to_v4.py            # v3 JSON 迁移到 v4 MySQL
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端框架 | Vue 3 (Composition API, `<script setup>`) | 所有组件使用 |
| UI 库 | Element Plus | 全局注册 |
| 路由 | vue-router (createWebHistory) | beforeEach 鉴权 |
| HTTP | Axios + 原生 fetch (文件下载) | 统一拦截器处理 401 |
| 构建 | Vite 8.x | proxy + allowedHosts |
| 公式渲染 | KaTeX (CDN-free, 本地包) | `renderMath()` 处理 $...$ 和 \(...\) |
| PDF 生成 | html2canvas + jspdf | 前端 DOM→Canvas→PDF |
| 后端 | FastAPI + SQLAlchemy + MySQL | localhost:8000 |

## 数据模型

### 题目 (Question) — `questions` 表

```python
question_id       # Integer PK, autoincrement
q_id              # String(50) unique, 如 "KP_几何面积_001"
knowledge_point   # String(100) not null, 具体知识点名
knowledge_category # String(50), 知识大类 (几何/计算/数论/方程与应用/逻辑/基础/其他)
question_type     # fill_blank | choice | calculation | problem_solving
difficulty        # 基础 | 中等 | 挑战
question_text     # Text, 题目正文 (支持 $...$ LaTeX)
answer            # Text, 正确答案 (支持 \(...\) LaTeX)
solution          # Text, 解析 (支持 \(...\) LaTeX)
has_image         # Boolean
image_path        # String(255)
source_school     # 来源学校缩写, 如 HFBZ
source_exam       # 如 "真卷（十）"
source_number     # 原题题号
exam_year         # 考试年份
grade_level       # 默认 "六年级"
is_key_point / is_difficult / is_high_freq / is_classic  # 标记字段
verification_status  # pending | ai_generated | verified | needs_review
variation_of      # Integer, 变式链父题 q_id
global_usage_count  # 全局使用次数
```

### 错题记录 (UserWrongQuestion) — `user_wrong_questions` 表

```python
record_id         # PK
user_id           # FK -> users
question_id       # FK -> questions
error_type        # 概念错误 | 计算错误 | 审题错误 | 方法错误 | 其他
mastered          # Boolean, 是否已掌握
redo_count        # Integer
exam_date         # Date
exam_name         # 考试名称
notes             # Text
```

### 练习单 (PracticeSheet) — `practice_sheets` 表

```python
sheet_id          # PK
user_id           # FK -> users
sheet_name        # String(100)
sheet_type        # daily | wrong_redo | special_topic | custom
total_questions   # Integer
estimated_time    # Integer, 分钟
generated_date    # DateTime
completed         # Boolean
score             # DECIMAL(5,2)
```

### 练习单-题目关联 (SheetQuestion) — `sheet_questions` 表

```python
id                # PK
sheet_id          # FK
question_id       # FK
question_order    # Integer, 题目顺序
is_correct        # Boolean, 批改结果
user_answer       # Text
```

### 知识点掌握度 (UserKnowledgeMastery) — `user_knowledge_mastery` 表

```python
mastery_id        # PK
user_id           # FK
knowledge_point   # String(100)
total_practiced   # Integer
correct_count     # Integer
mastery_rate      # DECIMAL(5,2), 百分比
last_practiced_date  # Date
forgetting_risk_score  # Integer, 0-100
is_weak_point     # Boolean, mastery_rate < 60%
```

## 知识体系 (SKILL_v3.1 设计稿)

```
├── 分数应用题/        ─── 基础/中等/挑战
├── 行程问题/          ─── 流水行船、相遇、追及
├── 工程问题/
├── 浓度问题/
├── 经济问题/
├── 几何面积/          ─── 必须附带原题图片
├── 圆柱与圆锥/        ─── 必须附带原题图片
├── 立体几何/          ─── 必须附带原题图片
├── 简便运算/
├── 解方程/
├── 定义新运算/
├── 找规律/
├── GCD与LCM/
├── 因数与倍数/
├── 比和比例/
├── 鸡兔同笼/
├── 牛吃草问题/
├── 逻辑推理/
└── 平均数与统计/
```

数据库里通过 `knowledge_category` (大类) + `knowledge_point` (具体点) 两级组织。

## 关键 API 端点

### 题目
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/questions | 分页列表 (category/difficulty/keyword 筛选) |
| POST | /api/questions | 创建单题 |
| GET | /api/questions/stats | 统计数据 |
| GET | /api/questions/knowledge-points/list | 知识点 (按 category 分组) |
| GET | /api/questions/categories/list | 分类列表 |
| GET | /api/questions/grades/list | 年级列表 |
| POST | /api/questions/batch | 批量导入 |
| POST | /api/questions/recognize | OCR 图片识别 (Codex API) |
| POST | /api/questions/recognize-pdf | PDF 识别 |

### 练习单
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/practice/generate | 生成练习单 (支持 knowledge_group_counts) |
| GET | /api/practice/sheets | 历史列表 (limit 50) |
| GET | /api/practice/sheets/{id} | 详情 (含题目数组) |
| DELETE | /api/practice/sheets/{id} | 删除 |
| POST | /api/practice/sheets/{id}/submit | 提交批改 (自动对比答案) |
| POST | /api/practice/sheets/{id}/upload | 上传做题图片 |

### 错题
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/wrong-questions | 错题列表 (含嵌套 question 对象) |
| POST | /api/wrong-questions | 录入错题 |
| PUT | /api/wrong-questions/feedback | 反馈对错 (更新掌握度) |
| DELETE | /api/wrong-questions/{id} | 删除记录 |
| POST | /api/wrong-questions/recognize | 拍照识别错题 |
| GET | /api/wrong-questions/diagnosis | 诊断报告 |

## 通用开发规则

### 组件开发
- 全部使用 Composition API + `<script setup>` 语法
- 模板中 ref 自动解包，不要写 `.value` (如 `selectedRecordIds.size` 而非 `.value.size`)
- `el-table` 跨页勾选：设 `row-key` + `reserve-selection` + `selection-change` 事件维护 Set
- API 统一通过 `src/api/` 模块调用，错误由 Axios 拦截器处理 (401 跳登录)

### 公式渲染
- 使用 `src/utils/math.js` 的 `renderMath(text)` 函数
- 支持 `$...$` (题目正文) 和 `\(...\)` (答案/解析) 两种 LaTeX 标记
- 在模板中用 `v-html="renderMath(text)"` 显示
- KaTeX CSS 通过 `math.js` 全局引入，无需额外 import
- 渲染失败时自动降级显示原始文本

### PDF 生成 (html2canvas + jspdf)
```js
// 标准流程
const container = document.createElement('div')
container.innerHTML = htmlContent
document.body.appendChild(container)
await Promise.all(imgs.map(img => new Promise(r => { img.onload = r; img.onerror = r })))
const canvas = await html2canvas(container, { scale: 2, useCORS: true })
document.body.removeChild(container)
const pdf = new jsPDF('p', 'mm', 'a4')
// 分页：addImage → 循环 addPage + addImage (偏移 pos -= pdfH)
pdf.save(filename)
```
- 容器设 `position: absolute; left: -9999px` 防闪烁
- 宽 794px (A4 @ 96dpi)，内边距 40px 56px
- 图片等待加载后再 canvas 渲染
- 多页用 `pos` 偏移切割 canvas，而非逐页重建 DOM

### 分组选题 (generate API 参数格式)
```json
{
  "sheet_type": "daily",
  "difficulties": ["基础", "中等", "挑战"],
  "knowledge_group_counts": [
    { "knowledge_category": "几何", "knowledge_points": ["几何面积", "圆柱与圆锥"], "count": 2 },
    { "knowledge_category": "计算", "knowledge_points": ["简便运算"], "count": 1 }
  ]
}
```
后端逻辑：对每组执行独立 SQL 查询 (按 knowledge_points 筛选 + 今日去重)，每组随机选 N 题，合并后 shuffle。

### PDF 分数渲染 (FRACTION_CSS)
- 带分数 `3\frac{1}{2}` → `<span class="mixed-frac">...`
- 真分数 `5/9` → `<span class="frac"><span class="num">5</span><span class="den">9</span></span>`
- `renderFractions()` 函数先用正则处理带分数，再处理真分数
- 与 KaTeX 互补：KaTeX 处理 LaTeX 标记内的公式，renderFractions 处理纯文本 `a/b`

### PDF 题型答题留空
| 题型 | 留空方式 |
|------|---------|
| fill_blank | 0.8cm 短横线 |
| choice | 0.6cm 短横线 |
| calculation | 3cm 虚线框 |
| problem_solving | 8cm 虚线框 + "解：" + "答：___________" |

## 常见开发场景

### 1. 新增页面/路由
1. `src/views/` 下新建 Vue 文件 (Composition API + `<script setup>`)
2. `src/router/index.js` 的 `children` 数组添加路由 (放在 Layout 下)
3. `src/components/Layout.vue` 的 `el-menu` 添加菜单项

### 2. 修改后端 API
1. `backend/app/api/` 对应模块添加路由函数
2. 路径以 `/api` 开头，Vite 代理到 localhost:8000
3. 需要在 `schemas/__init__.py` 中添加 Pydantic 模型
4. 带文件上传的接口用 `UploadFile` + FormData，设长 timeout

### 3. 添加 PDF 生成
1. 构建 HTML 字符串 (用 `${}` 拼接)
2. `renderFractions(renderMath(text))` 处理公式
3. 用 `renderToPdf(html, filename)` 统一渲染下载
4. 需要分离学生卷和答案卷时，分两次调用 `renderToPdf`

### 4. 添加批量操作
- 表格加 `type="selection"` + `row-key` + `reserve-selection`
- `selection-change` 事件维护 Set
- 逐条调用 API (无批量端点时)

### 5. OCR 识别流程
1. 前端上传图片 → FormData append `file`
2. 后端调用 Codex/Kimi API 识别
3. 返回结构化题目数据 (含 question_text/answer/solution 等)
4. 前端展示在可编辑表单中 (已加 KaTeX 实时预览)
5. 用户确认后 batchImport

## 参考文件
- `SKILL_v3.1_完整参考版.md` — 完整设计文档 (含组卷算法、PDF 规范、诊断逻辑)
- `frontend/src/` — 前端源码
- `backend/app/` — 后端源码
- `vite.config.js` — Vite 配置
