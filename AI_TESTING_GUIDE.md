# AI功能测试指南

## 修复说明

### 问题
之前的实现使用了错误的组件调用方式：
- ❌ 使用 `ref` 和 `.open()` 方法
- ❌ 监听 `@generated` 事件

### 修复
正确的实现方式：
- ✅ 使用 `v-model` 绑定显示状态
- ✅ 监听 `@created` 事件（组件实际emit的事件名）

## 测试步骤

### 1. 启动服务

#### 后端
```bash
cd backend
python main.py
# 或
uvicorn app.main:app --reload --port 8000
```

#### 前端
```bash
cd frontend
npm run dev
```

### 2. 访问页面
打开浏览器访问：`http://localhost:5173`（或前端实际端口）

### 3. 测试AI功能

#### 步骤1：找到AI按钮
1. 登录系统
2. 进入"练习单"页面
3. 在左侧"生成练习单"卡片中，找到 **🤖 AI智能生成** 按钮（绿色）

#### 步骤2：打开AI对话框
1. 点击"🤖 AI智能生成"按钮
2. 应该弹出"AI 智能生成练习单"对话框

#### 步骤3：测试AI生成
在对话框中输入需求，例如：
- **简单测试**：`给我10道计算题，难度中等`
- **专题测试**：`给我一份分数应用题练习，8题，中等偏难，30分钟左右`
- **错题测试**：`根据我最近错题出一份查漏补缺练习，应用题多一点，10题`
- **多套测试**：`根据我最近一周的错题出三份查漏补缺练习，每张试卷计算题保证4个，每套12题`

#### 步骤4：查看预览
1. 点击"生成预览"按钮
2. AI会分析需求并显示：
   - AI理解结果（左侧）
   - 题目预览（右侧）
   - 可以看到题目数量、预计时间等信息

#### 步骤5：调整题目（可选）
- **替换题目**：点击题目右侧的"换一题"按钮
- **补充题目**：点击"补一题"按钮添加更多题目

#### 步骤6：确认生成
1. 点击"确认生成"按钮
2. 等待生成完成
3. 应该看到成功提示：`AI练习单已生成 X 套`
4. 对话框自动关闭
5. 练习单列表自动刷新，新生成的练习单出现在列表中

### 4. 验证生成结果

在"已有练习单"表格中：
1. 找到刚生成的练习单
2. 点击"PDF下载"按钮，下载PDF文件
3. 点击"查看"按钮，预览题目内容
4. 验证题目是否符合需求

## 常见问题排查

### 问题1：点击按钮没反应
**检查项**：
- 浏览器控制台是否有错误？（按F12打开）
- 前端是否正确构建？运行 `npm run build` 检查
- 是否使用了开发模式？应该用 `npm run dev`

### 问题2：对话框弹出但生成失败
**检查项**：
- 后端是否正常运行？访问 `http://localhost:8000/docs` 检查API文档
- 是否配置了AI API密钥？检查 `backend/.env` 文件
- 数据库中是否有题目数据？

### 问题3：生成预览成功但确认失败
**检查项**：
- 查看浏览器控制台的网络请求（Network标签）
- 查看后端日志输出
- 检查 `/practice/ai-generate-confirm` 端点是否正常

### 问题4：生成成功但列表不刷新
**检查项**：
- 手动刷新页面，看练习单是否存在
- 检查 `loadSheets()` 函数是否被调用
- 查看浏览器控制台是否有错误

## 技术细节

### 组件通信方式
```vue
<!-- Practice.vue -->
<AIPracticeDialog 
  v-model="showAIDialog"    <!-- 控制显示/隐藏 -->
  @created="onAIGenerated"  <!-- 监听生成完成事件 -->
/>

<script setup>
const showAIDialog = ref(false)

function openAIDialog() {
  showAIDialog.value = true  // 打开对话框
}

function onAIGenerated(result) {
  showAIDialog.value = false  // 关闭对话框
  loadSheets()                // 刷新列表
  ElMessage.success(`AI练习单已生成 ${result.created_count || 0} 套`)
}
</script>
```

### API端点
- `POST /practice/ai-generate-preview` - 生成预览
- `POST /practice/ai-generate-confirm` - 确认生成
- `POST /practice/ai-replace-question` - 替换题目
- `POST /practice/ai-supplement-question` - 补充题目

### 数据流
```
用户输入需求
    ↓
点击"生成预览"
    ↓
调用 /ai-generate-preview
    ↓
AI解析需求 + 智能选题
    ↓
返回预览数据（题目列表）
    ↓
用户调整题目（可选）
    ↓
点击"确认生成"
    ↓
调用 /ai-generate-confirm
    ↓
创建练习单记录
    ↓
返回生成结果
    ↓
刷新练习单列表
```

## 成功标志

✅ 点击"🤖 AI智能生成"按钮，对话框正常弹出
✅ 输入需求后，AI能正确解析并生成预览
✅ 可以替换和补充题目
✅ 确认生成后，练习单出现在列表中
✅ 可以下载PDF和查看题目内容

## 相关文件

- `frontend/src/views/Practice.vue` - 练习单页面（集成AI按钮）
- `frontend/src/components/AIPracticeDialog.vue` - AI对话框组件
- `frontend/src/api/practice.js` - API封装
- `backend/app/api/practice_ai.py` - AI路由
- `backend/app/utils/practice_ai.py` - AI核心算法

## Git提交记录

- `81d2019` - fix: 修正AI对话框的调用方式
- `d0913a6` - feat: 集成AI智能生成练习单功能到前端界面
- `bbbb58c` - fix: 恢复AI生成题单功能
