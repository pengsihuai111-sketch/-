#!/bin/bash
# 小升初数学题库管理系统 - 百度云服务器一键部署脚本
# 服务器：106.12.191.104 (Ubuntu 24.04.1 LTS)
# 配置：2核4GB 50GB 1Mbps

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  小升初数学题库管理系统 - 一键部署"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="math_bank_v4"
DEPLOY_DIR="/var/www/${PROJECT_NAME}"
BACKEND_PORT=8000
FRONTEND_PORT=80

# 数据库配置
DB_NAME="math_bank"
DB_USER="math_user"
DB_PASSWORD="MathBank2026!@#"  # 建议修改为更安全的密码
DB_HOST="localhost"

echo -e "${YELLOW}[1/10] 更新系统软件包...${NC}"
apt update
apt upgrade -y

echo -e "${YELLOW}[2/10] 安装必要软件...${NC}"
# 安装MySQL
apt install -y mysql-server mysql-client

# 安装Nginx
apt install -y nginx

# 安装Python依赖工具
apt install -y python3-pip python3-venv

# 安装其他工具
apt install -y curl wget unzip

echo -e "${GREEN}✓ 软件安装完成${NC}"

echo -e "${YELLOW}[3/10] 配置MySQL数据库...${NC}"
# 启动MySQL服务
systemctl start mysql
systemctl enable mysql

# 配置MySQL（设置root密码并创建数据库）
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${DB_PASSWORD}';" || true
mysql -uroot -p${DB_PASSWORD} -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -uroot -p${DB_PASSWORD} -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';"
mysql -uroot -p${DB_PASSWORD} -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
mysql -uroot -p${DB_PASSWORD} -e "FLUSH PRIVILEGES;"

echo -e "${GREEN}✓ MySQL配置完成${NC}"
echo -e "  数据库名: ${DB_NAME}"
echo -e "  用户名: ${DB_USER}"
echo -e "  密码: ${DB_PASSWORD}"

echo -e "${YELLOW}[4/10] 创建项目目录...${NC}"
mkdir -p ${DEPLOY_DIR}
cd ${DEPLOY_DIR}

echo -e "${YELLOW}[5/10] 上传项目代码...${NC}"
echo -e "${RED}请在本地执行以下命令上传代码：${NC}"
echo -e "${GREEN}cd d:\\project\\题库管理${NC}"
echo -e "${GREEN}scp -r math_bank_v4 root@106.12.191.104:${DEPLOY_DIR}/${NC}"
echo ""
read -p "代码上传完成后，按回车继续..."

echo -e "${YELLOW}[6/10] 配置后端环境...${NC}"
cd ${DEPLOY_DIR}/math_bank_v4/backend

# 创建Python虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
pip install --upgrade pip
pip install -r requirements.txt

# 创建.env配置文件
cat > .env << EOF
# 数据库配置
DATABASE_URL=mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}/${DB_NAME}

# JWT配置
SECRET_KEY=$(openssl rand -hex 32)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Claude API配置（PDF识别）
ANTHROPIC_BASE_URL=https://www.vibecd.cc
ANTHROPIC_AUTH_TOKEN=sk-ef3bcae48dab4243e19ccd2986363a0aec0bc40afb2b2b9df571b076a5063dfe
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 文件上传配置
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800

# 服务器配置
HOST=0.0.0.0
PORT=${BACKEND_PORT}
EOF

echo -e "${GREEN}✓ 后端环境配置完成${NC}"

echo -e "${YELLOW}[7/10] 初始化数据库...${NC}"
# 运行数据库迁移（创建表结构）
python -c "
from app.database import engine, Base
from app.models import *
Base.metadata.create_all(bind=engine)
print('数据库表创建成功')
"

echo -e "${GREEN}✓ 数据库初始化完成${NC}"

echo -e "${YELLOW}[8/10] 配置前端环境...${NC}"
cd ${DEPLOY_DIR}/math_bank_v4/frontend

# 安装前端依赖
npm install

# 修改API地址为服务器IP
cat > .env.production << EOF
VITE_API_BASE_URL=http://106.12.191.104:${BACKEND_PORT}
EOF

# 构建前端
npm run build

echo -e "${GREEN}✓ 前端构建完成${NC}"

echo -e "${YELLOW}[9/10] 配置Nginx...${NC}"
# 创建Nginx配置文件
cat > /etc/nginx/sites-available/${PROJECT_NAME} << 'EOF'
server {
    listen 80;
    server_name 106.12.191.104;

    # 前端静态文件
    location / {
        root /var/www/math_bank_v4/math_bank_v4/frontend/dist;
        try_files $uri $uri/ /index.html;
        index index.html;
    }

    # 后端API代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置（PDF识别需要较长时间）
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # 上传文件访问
    location /uploads {
        alias /var/www/math_bank_v4/math_bank_v4/backend/uploads;
        autoindex off;
    }

    # 文件上传大小限制
    client_max_body_size 50M;
}
EOF

# 启用站点配置
ln -sf /etc/nginx/sites-available/${PROJECT_NAME} /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试Nginx配置
nginx -t

# 重启Nginx
systemctl restart nginx
systemctl enable nginx

echo -e "${GREEN}✓ Nginx配置完成${NC}"

echo -e "${YELLOW}[10/10] 配置后端服务（systemd）...${NC}"
# 创建systemd服务文件
cat > /etc/systemd/system/${PROJECT_NAME}-backend.service << EOF
[Unit]
Description=Math Bank Backend Service
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${DEPLOY_DIR}/math_bank_v4/backend
Environment="PATH=${DEPLOY_DIR}/math_bank_v4/backend/venv/bin"
ExecStart=${DEPLOY_DIR}/math_bank_v4/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd配置
systemctl daemon-reload

# 启动后端服务
systemctl start ${PROJECT_NAME}-backend
systemctl enable ${PROJECT_NAME}-backend

echo -e "${GREEN}✓ 后端服务配置完成${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "=========================================="
echo ""
echo "访问地址："
echo -e "  前端: ${GREEN}http://106.12.191.104${NC}"
echo -e "  后端API: ${GREEN}http://106.12.191.104/api${NC}"
echo ""
echo "服务管理命令："
echo "  查看后端状态: systemctl status ${PROJECT_NAME}-backend"
echo "  重启后端: systemctl restart ${PROJECT_NAME}-backend"
echo "  查看后端日志: journalctl -u ${PROJECT_NAME}-backend -f"
echo "  重启Nginx: systemctl restart nginx"
echo ""
echo "数据库信息："
echo "  数据库名: ${DB_NAME}"
echo "  用户名: ${DB_USER}"
echo "  密码: ${DB_PASSWORD}"
echo ""
echo -e "${YELLOW}重要提示：${NC}"
echo "1. 请确保百度云安全组已开放 80 和 8000 端口"
echo "2. 首次访问需要注册账号"
echo "3. 数据库密码已保存在 ${DEPLOY_DIR}/math_bank_v4/backend/.env"
echo ""
