# 已安装的 Skills 和使用指南

## ✅ 已成功安装的 Skills

### 1. **frontend-design** ✨
- **用途**: 创建高质量的前端界面，适用于 Vue/React 等框架
- **使用场景**: 构建 Web 组件、页面或应用程序
- **调用方式**: `/frontend-design` 或在对话中提到前端设计相关需求

### 2. **skill-development** 🛠️
- **用途**: 开发自定义 skills
- **使用场景**: 当你需要创建项目特定的 skill 时
- **调用方式**: `/skill-development`

### 3. **claude-md-improver** 📝
- **用途**: 改进和优化 CLAUDE.md 文档
- **使用场景**: 技术文档编写和改进
- **调用方式**: `/claude-md-improver`

### 4. **skill-creator** 🎨
- **用途**: 创建新的自定义 skills
- **使用场景**: 需要为特定任务创建专门的 skill
- **调用方式**: `/skill-creator`

### 5. **design-md** (已有)
- **用途**: 从 73 个知名网站设计规范中选取风格
- **使用场景**: UI 设计风格指导

### 6. **exam-paper-generator** (已有)
- **用途**: 生成可打印的试卷 PDF
- **使用场景**: 从题库生成练习卷

### 7. **xiaoshengchu-math-bank** (已有)
- **用途**: 小升初数学题库管理系统
- **使用场景**: 题库管理、错题管理、练习单生成

---

## 📋 针对你需求的解决方案

### 1. ✅ Security Review / Code Review
**状态**: 部分可用

**可用功能**:
- 使用内置的 `/review` 命令进行 PR 审查
- 使用内置的 `/security-review` 命令进行安全审查

**推荐安装** (需要通过 CLI):
```bash
/plugin install pr-review-toolkit@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install code-review@claude-plugins-official
```

### 2. ⚠️ Python / FastAPI / Backend Development
**状态**: 需要自定义或使用通用功能

**当前方案**:
- 直接请求 Claude 帮助进行 Python/FastAPI 开发
- 使用 `skill-creator` 创建自定义的 Python 开发 skill

**推荐创建自定义 skill**:
```bash
/skill-creator
# 创建名为 "python-fastapi-dev" 的 skill
```

### 3. ✅ Vue / Frontend Development
**状态**: 已安装

**使用方式**:
```bash
/frontend-design
```
或直接在对话中说："帮我用 Vue 3 创建一个..."

### 4. ⚠️ Pytest / Test Generator
**状态**: 需要自定义

**当前方案**:
- 直接请求 Claude 生成 pytest 测试
- 使用 `skill-creator` 创建专门的测试生成 skill

**示例请求**:
"帮我为 `app/api/auth.py` 中的所有函数生成 pytest 测试用例"

### 5. ✅ Technical Writing / README Writer
**状态**: 已安装 (claude-md-improver)

**使用方式**:
```bash
/claude-md-improver
```
或直接请求："帮我写一个 README.md 文档"

### 6. ⚠️ SQL / MySQL / Database Migration
**状态**: 需要自定义

**当前方案**:
- 直接请求 Claude 帮助处理数据库迁移
- 使用 `skill-creator` 创建数据库迁移 skill

**示例请求**:
"帮我创建一个 Alembic 迁移脚本，添加 xxx 表"

---

## 🎯 创建自定义 Skills

如果你需要创建专门的 skills（如 pytest-generator、database-migration），可以使用：

```bash
/skill-creator
```

### 推荐创建的自定义 Skills:

1. **pytest-generator**
   - 自动为 Python 代码生成 pytest 测试
   - 包含 fixtures、mocks、参数化测试

2. **fastapi-dev**
   - FastAPI 路由、依赖注入、中间件开发
   - Pydantic 模型生成
   - API 文档优化

3. **database-migration**
   - Alembic 迁移脚本生成
   - MySQL 查询优化
   - 数据库架构设计

4. **readme-writer**
   - 项目 README 生成
   - API 文档生成
   - 技术文档模板

---

## 📦 通过 CLI 安装更多 Plugins

如果你想安装提供 agents 和 commands 的 plugins，需要在 Claude Code CLI 中运行：

```bash
# 代码审查工具包
/plugin install pr-review-toolkit@claude-plugins-official

# 安全指导
/plugin install security-guidance@claude-plugins-official

# 代码审查命令
/plugin install code-review@claude-plugins-official

# 功能开发工作流
/plugin install feature-dev@claude-plugins-official

# Python LSP 支持
/plugin install pyright-lsp@claude-plugins-official
```

---

## 🔍 验证安装

运行以下命令查看所有可用的 skills:
```bash
/help
```

或者查看 `.claude/skills/` 目录:
```bash
ls .claude/skills/
```

---

## 💡 使用技巧

1. **直接对话**: 大多数情况下，你不需要显式调用 skill，只需在对话中描述你的需求，Claude 会自动选择合适的 skill。

2. **显式调用**: 如果你想确保使用特定的 skill，可以使用 `/skill-name` 命令。

3. **组合使用**: 可以在一个任务中组合使用多个 skills，例如：
   - 先用 `frontend-design` 设计界面
   - 再用 `pytest-generator` 生成测试
   - 最后用 `claude-md-improver` 更新文档

4. **创建项目特定 Skills**: 对于重复性的任务，使用 `skill-creator` 创建专门的 skill 可以大大提高效率。

---

## 📚 下一步

1. **测试已安装的 skills**: 尝试使用 `/frontend-design` 创建一个组件
2. **创建自定义 skills**: 使用 `/skill-creator` 创建 pytest-generator
3. **安装更多 plugins**: 通过 CLI 安装 pr-review-toolkit 等
4. **优化工作流**: 根据实际使用情况调整和优化 skills

---

## 🆘 获取帮助

- 查看帮助: `/help`
- 列出所有 plugins: `/plugin list`
- 查看 skill 文档: 直接询问 "xxx skill 怎么用？"
