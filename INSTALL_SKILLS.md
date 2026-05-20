# Claude Code Skills 安装指南

## 需要安装的 Plugins

根据你的需求，以下是推荐安装的 plugins：

### 1. Code Review & Security (代码审查和安全)

#### pr-review-toolkit
- **描述**: 全面的 PR 审查工具包，包含多个专业审查 agents
- **包含的 agents**:
  - code-reviewer: 代码审查
  - code-simplifier: 代码简化
  - comment-analyzer: 注释分析
  - pr-test-analyzer: PR 测试分析
  - silent-failure-hunter: 静默失败检测
  - type-design-analyzer: 类型设计分析

**安装命令**:
```bash
/plugin install pr-review-toolkit@claude-plugins-official
```

#### security-guidance
- **描述**: 安全指导和警告，在编辑文件时提醒潜在的安全问题
- **功能**: 命令注入、XSS、不安全代码模式检测

**安装命令**:
```bash
/plugin install security-guidance@claude-plugins-official
```

#### code-review
- **描述**: 自动化代码审查命令
- **包含**: /code-review 命令

**安装命令**:
```bash
/plugin install code-review@claude-plugins-official
```

### 2. Feature Development (功能开发)

#### feature-dev
- **描述**: 全面的功能开发工作流，包含专业的 agents
- **包含的 agents**:
  - code-explorer: 代码库探索
  - code-architect: 架构设计
  - code-reviewer: 质量审查

**安装命令**:
```bash
/plugin install feature-dev@claude-plugins-official
```

### 3. Frontend Development (前端开发)

#### frontend-design
- **描述**: 前端设计和 UI/UX 实现
- **包含**: frontend-design skill

**安装命令**:
```bash
/plugin install frontend-design@claude-plugins-official
```

### 4. Python Development (Python 开发)

#### pyright-lsp
- **描述**: Python 语言服务器协议支持
- **功能**: 类型检查、代码补全、错误检测

**安装命令**:
```bash
/plugin install pyright-lsp@claude-plugins-official
```

---

## 快速安装所有推荐 Plugins

你可以在 Claude Code CLI 中依次运行以下命令：

```bash
/plugin install pr-review-toolkit@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install code-review@claude-plugins-official
/plugin install feature-dev@claude-plugins-official
/plugin install frontend-design@claude-plugins-official
/plugin install pyright-lsp@claude-plugins-official
```

---

## 安装后的使用

### 使用 Skills
安装后，你可以通过以下方式使用 skills：
```bash
/frontend-design
```

### 使用 Commands
```bash
/code-review
```

### 使用 Agents
Agents 会在需要时自动被 Claude 调用，或者你可以在对话中明确请求使用特定的 agent。

---

## 注意事项

1. **未找到的功能**:
   - 没有找到专门的 pytest/test-generator plugin
   - 没有找到专门的 technical-writing/readme-writer plugin
   - 没有找到专门的 sql/mysql/database-migration plugin

2. **替代方案**:
   - **测试生成**: 可以使用 `pr-review-toolkit` 中的 `pr-test-analyzer` agent
   - **文档写作**: 可以直接请求 Claude 帮助编写文档
   - **数据库迁移**: 可以直接请求 Claude 帮助处理 SQL 和数据库迁移

3. **验证安装**:
   安装后，你可以运行以下命令查看已安装的 plugins：
   ```bash
   /plugin list
   ```

---

## 自定义 Skills

如果你需要创建自定义的 skills（如 pytest-generator、readme-writer、database-migration），可以使用：

```bash
/plugin install skill-creator@claude-plugins-official
```

然后使用 skill-creator 来创建你自己的 skills。

---

## 项目特定配置

这些 plugins 安装后会在全局可用。如果你想在项目级别配置特定的 skills，可以在 `.claude/settings.json` 中添加配置。
