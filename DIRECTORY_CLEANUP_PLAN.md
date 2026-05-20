# 项目目录整理方案

## 📋 当前问题分析

### 问题清单
1. ❌ backend/和frontend/直接在根目录，与README.md描述不符
2. ❌ 根目录有大量部署脚本（deploy*.sh, setup*.sh）
3. ❌ 根目录有测试文件（test_recognition_optimization.py, check_stats.py）
4. ❌ 有多个旧版本备份（math_bank_v3/, math_bank_v4/）
5. ❌ 有中文目录名（功能报告/, 试卷/）
6. ❌ 有临时文件（test.png, openapi_dump.json, project_structure.txt）
7. ❌ 有奇怪的文件名（C:Usershp-pcAppDataLocalTempqid_test.json）

### 目录大小统计
- frontend/: 167.87 MB
- math_bank_v4/: 596.46 MB (子模块备份)
- uploads/: 414.05 MB
- math_bank_v3/: 20.98 MB
- backend/: 1.05 MB

---

## 🎯 整理目标

### 理想的目录结构

```
题库管理/
├── backend/                    # 后端服务（保持在根目录）
├── frontend/                   # 前端应用（保持在根目录）
├── uploads/                    # 上传文件（保持在根目录）
│
├── docs/                       # 📚 所有文档
│   ├── design/                # 设计文档
│   ├── deployment/            # 部署文档
│   ├── api/                   # API文档
│   ├── reports/               # 功能报告（原"功能报告/"）
│   └── samples/               # 样例文件（原"试卷/"）
│
├── scripts/                    # 🔧 所有脚本
│   ├── deploy/                # 部署脚本
│   │   ├── deploy.sh
│   │   ├── deploy_git.sh
│   │   └── deploy_scp.sh
│   ├── setup/                 # 环境配置脚本
│   │   ├── setup_git_on_server.sh
│   │   └── setup_ssh_key.sh
│   └── utils/                 # 工具脚本
│       └── check_stats.py
│
├── tests/                      # 🧪 所有测试
│   ├── backend/               # 后端测试
│   ├── recognition/           # 识别测试
│   │   └── test_recognition_optimization.py
│   └── fixtures/              # 测试数据
│       └── test.png
│
├── archive/                    # 📦 归档（旧版本）
│   ├── math_bank_v3/          # v3版本备份
│   └── math_bank_v4/          # v4开发备份（子模块）
│
├── database/                   # 🗄️ 数据库相关
│   └── schema.sql
│
├── .agents/                    # Claude Code配置
├── .claude/                    # Claude Code内存
├── .git/                       # Git仓库
│
├── .env.example               # 环境变量模板
├── .gitignore                 # Git忽略配置
├── .gitmodules                # Git子模块配置
├── README.md                  # 项目说明
├── PROJECT_STRUCTURE.md       # 项目结构文档
├── OPTIMIZATION_SUMMARY.md    # 优化总结
└── PERFORMANCE_OPTIMIZATION.md # 性能优化文档
```

---

## 📝 整理步骤

### 第1步：整理部署脚本
```bash
mkdir -p scripts/deploy scripts/setup scripts/utils
mv deploy.sh deploy_git.sh deploy_scp.sh scripts/deploy/
mv setup_git_on_server.sh setup_ssh_key.sh scripts/setup/
mv check_stats.py scripts/utils/
```

### 第2步：整理测试文件
```bash
mkdir -p tests/recognition tests/fixtures
mv test_recognition_optimization.py tests/recognition/
mv test.png tests/fixtures/
```

### 第3步：归档旧版本
```bash
mkdir -p archive
mv math_bank_v3 archive/
# math_bank_v4是子模块，保持不动或移除子模块引用
```

### 第4步：整理文档和中文目录
```bash
mkdir -p docs/reports docs/samples docs/api
mv 功能报告/* docs/reports/
mv 试卷/* docs/samples/
mv openapi_dump.json docs/api/
rmdir 功能报告 试卷
```

### 第5步：清理临时文件
```bash
rm -f "C:Usershp-pcAppDataLocalTempqid_test.json"
rm -f project_structure.txt
```

### 第6步：更新文档
- 更新README.md，反映新的目录结构
- 更新.gitignore，忽略临时文件
- 更新PROJECT_STRUCTURE.md

---

## ⚠️ 注意事项

### 不能移动的文件/目录
- ✅ backend/ - 当前工作版本
- ✅ frontend/ - 当前工作版本
- ✅ uploads/ - 运行时需要
- ✅ database/ - 数据库脚本
- ✅ .git/ - Git仓库
- ✅ .env.example - 配置模板

### 需要更新的引用
1. 部署脚本中的路径引用
2. README.md中的目录结构说明
3. 测试脚本中的路径引用

### 子模块处理
math_bank_v4/是Git子模块，有两个选择：
1. **保留子模块**：移动到archive/但保持子模块配置
2. **移除子模块**：完全删除子模块引用

---

## 🎯 预期效果

### 整理前
- 根目录文件：30+ 个
- 目录层级：混乱
- 中文目录：2个
- 临时文件：多个

### 整理后
- 根目录文件：10个左右（主要是配置和文档）
- 目录层级：清晰的功能分类
- 中文目录：0个
- 临时文件：0个

### 优势
✅ 目录结构清晰，易于导航
✅ 符合标准项目规范
✅ 便于新成员理解项目
✅ 减少根目录混乱
✅ 便于CI/CD配置

---

**整理时间**: 预计5-10分钟  
**风险等级**: 低（不影响核心功能）  
**建议**: 整理前先提交当前代码，确保可以回滚
