# 小升初数学题库管理系统 v4.0

一个面向小升初学生的数学题库管理与学情诊断系统，支持题库浏览、错题管理、练习单生成、AI识别录题和智能学情诊断。

## 系统架构

```
前端 (Vue 3 + Element Plus)  →  后端 API (FastAPI)  →  数据库 (MySQL 8.0)
```

## 核心功能

| 模块 | 功能说明 |
|------|---------|
| 用户认证 | 注册、登录、JWT鉴权 |
| 题库浏览 | 搜索、筛选、分页浏览、查看题目详情 |
| 错题管理 | 手动录入、拍照识别、答题反馈、错题分类 |
| 练习单生成 | 每日练习、错题重做、专题练习、自定义组卷、导出PDF |
| 学情诊断 | 知识点掌握度分析、薄弱点识别、遗忘曲线预警 |
| AI识别 | PDF/图片识别、题目自动提取、支持多种AI模型 |
| 会员中心 | 套餐购买、订单管理、支付模拟 |

## 技术栈

**前端**
- Vue 3 + Composition API
- Element Plus UI组件库
- Pinia 状态管理
- Vue Router 路由
- Axios HTTP客户端
- KaTeX 数学公式渲染
- html2canvas + jsPDF 导出功能

**后端**
- FastAPI Web框架
- SQLAlchemy ORM
- PyMySQL 数据库驱动
- JWT 身份认证
- Pillow 图像处理
- 多AI模型支持（DeepSeek、豆包等）

**数据库**
- MySQL 8.0
- 题库总题数: 403题（从v3.0迁移）

## 项目结构

```
project-root/
├── README.md                    # 项目说明文档
├── .env.example                 # 环境变量模板
├── .gitignore                   # Git忽略配置
├── math_bank_v4/               # 主项目目录
│   ├── backend/                # 后端代码
│   │   ├── app/               # 应用核心
│   │   │   ├── api/          # API路由
│   │   │   ├── models/       # 数据模型
│   │   │   ├── schemas/      # Pydantic模式
│   │   │   ├── services/     # 业务逻辑
│   │   │   ├── utils/        # 工具函数
│   │   │   ├── config.py     # 配置文件
│   │   │   ├── database.py   # 数据库连接
│   │   │   └── main.py       # 应用入口
│   │   ├── requirements.txt   # Python依赖
│   │   └── run.py            # 启动脚本
│   └── frontend/              # 前端代码
│       ├── src/              # 源代码
│       ├── package.json      # Node依赖
│       └── vite.config.js    # Vite配置
├── docs/                       # 文档目录
│   ├── design/               # 设计文档
│   ├── recognition/          # 识别功能文档
│   ├── deployment/           # 部署文档
│   └── troubleshooting/      # 故障排查
├── scripts/                    # 脚本工具
│   ├── start_backend.bat     # 启动后端（Windows）
│   ├── start_frontend.bat    # 启动前端（Windows）
│   └── deploy_to_baidu_cloud.sh  # 部署脚本
└── tests/                      # 测试文件
    ├── backend/              # 后端测试
    └── recognition/          # 识别功能测试
```

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 16+
- MySQL 8.0+

### 1. 数据库初始化

```bash
# 登录MySQL
mysql -u root -p

# 创建数据库
CREATE DATABASE question_bank_v4 DEFAULT CHARACTER SET utf8mb4;

# 导入数据表结构（如果有schema.sql）
USE question_bank_v4;
SOURCE database/schema.sql;
```

### 2. 配置环境变量

复制 `.env.example` 到 `math_bank_v4/backend/.env` 并填写配置：

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=question_bank_v4

# JWT密钥（请修改为随机字符串）
JWT_SECRET=your_random_secret_key

# AI API配置（可选，用于题目识别功能）
DOUBAO_API_KEY=your_api_key
VISION_API_KEY=your_api_key
```

### 3. 启动后端服务

```bash
cd math_bank_v4/backend

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认端口8000）
python run.py
```

后端健康检查: http://localhost:8000/api/health

### 4. 启动前端服务

```bash
cd math_bank_v4/frontend

# 安装依赖
npm install

# 启动开发服务器（默认端口5173）
npm run dev
```

### 5. 访问系统

浏览器打开: http://localhost:5173

## AI识别配置

系统支持多种AI模型进行题目识别：

1. **DeepSeek** - 备选文本模型
2. **豆包/智谱** - 主要文本和视觉模型

在 `.env` 文件中配置对应的API密钥和端点即可启用识别功能。

## 常见问题

### 数据库连接失败
- 检查MySQL服务是否启动
- 确认 `.env` 中的数据库配置正确
- 确保数据库已创建且字符集为utf8mb4

### 前端无法连接后端
- 确认后端服务已启动（端口8000）
- 检查防火墙设置
- 查看浏览器控制台的网络请求错误

### AI识别功能不可用
- 确认已配置API密钥
- 检查API额度是否充足
- 查看后端日志中的错误信息

## 开发指南

### 启动脚本

Windows用户可以使用批处理脚本快速启动：

```bash
# 启动后端
scripts\start_backend.bat

# 启动前端
scripts\start_frontend.bat
```

### 运行测试

```bash
# 后端测试
cd tests/backend
python test_api.py

# 识别功能测试
cd tests/recognition
python test_recognition.py
```

## 部署说明

详细的部署文档请参考：
- [服务器配置需求分析](docs/deployment/服务器配置需求分析.md)
- [线上部署方案](docs/deployment/线上部署方案.md)
- [阿里云购买指南](docs/deployment/阿里云购买指南.md)

## 文档索引

- **设计文档**: [docs/design/](docs/design/)
- **识别功能**: [docs/recognition/](docs/recognition/)
- **故障排查**: [docs/troubleshooting/](docs/troubleshooting/)

## 后续规划

- [ ] Docker Compose 一键部署
- [ ] 完善API文档（Swagger/OpenAPI）
- [ ] 增加自动化测试覆盖
- [ ] 添加CI/CD流程
- [ ] 优化学情诊断算法
- [ ] 增加更多题型支持

## 许可证

本项目仅供学习和研究使用。

## 联系方式

如有问题或建议，欢迎提交Issue。
