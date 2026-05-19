#!/bin/bash
# 快速部署脚本（使用 SCP）

set -e

echo "=========================================="
echo "  开始同步代码到服务器..."
echo "=========================================="

# 创建临时目录，排除不需要的文件
TEMP_DIR=$(mktemp -d)
echo "创建临时目录: $TEMP_DIR"

# 复制需要的文件到临时目录
cp -r math_bank_v4 "$TEMP_DIR/"

# 删除不需要的文件
echo "清理不需要的文件..."
rm -rf "$TEMP_DIR/math_bank_v4/frontend/node_modules"
rm -rf "$TEMP_DIR/math_bank_v4/frontend/dist"
rm -rf "$TEMP_DIR/math_bank_v4/backend/venv"
rm -rf "$TEMP_DIR/math_bank_v4/backend/__pycache__"
rm -rf "$TEMP_DIR/math_bank_v4/backend/uploads"
find "$TEMP_DIR" -name "*.pyc" -delete
find "$TEMP_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 使用 SCP 上传
echo "上传代码到服务器..."
scp -r "$TEMP_DIR/math_bank_v4/"* root@106.12.191.104:/var/www/math_bank_v4/

# 清理临时目录
rm -rf "$TEMP_DIR"
echo "临时目录已清理"

echo ""
echo "=========================================="
echo "  代码同步完成，正在重启服务..."
echo "=========================================="

# 在服务器上执行重启命令
ssh root@106.12.191.104 << 'EOF'
cd /var/www/math_bank_v4

# 后端依赖更新
cd backend
source venv/bin/activate
pip install -r requirements.txt -q

# 前端构建
cd ../frontend
npm install --silent
npm run build

# 重启后端服务
systemctl restart math_bank_v4-backend

# 检查状态
echo ""
echo "后端服务状态："
systemctl status math_bank_v4-backend --no-pager | head -10

echo ""
echo "Nginx 状态："
systemctl status nginx --no-pager | head -5
EOF

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo "访问地址: http://106.12.191.104"
