#!/bin/bash
# SCP 部署脚本 - 直接上传代码到服务器

set -e

echo "=========================================="
echo "  SCP 部署流程"
echo "=========================================="

# 步骤 1：打包代码
echo ""
echo "[1/4] 打包本地代码..."
cd /d/project/题库管理/math_bank_v4

# 排除不需要的文件
tar -czf /tmp/math_bank_v4.tar.gz \
    --exclude='node_modules' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='dist' \
    --exclude='.DS_Store' \
    .

echo "✓ 打包完成: $(du -h /tmp/math_bank_v4.tar.gz | cut -f1)"

# 步骤 2：上传到服务器
echo ""
echo "[2/4] 上传到服务器..."
scp /tmp/math_bank_v4.tar.gz root@106.12.191.104:/tmp/
echo "✓ 上传完成"

# 步骤 3：在服务器上解压并更新
echo ""
echo "[3/4] 在服务器上解压并更新..."
ssh root@106.12.191.104 << 'EOF'
cd /var/www/math_bank_v4

# 备份当前代码
if [ -d backend ]; then
    echo "备份当前代码..."
    tar -czf /tmp/backup_$(date +%Y%m%d_%H%M%S).tar.gz backend frontend 2>/dev/null || true
fi

# 解压新代码
echo "解压新代码..."
tar -xzf /tmp/math_bank_v4.tar.gz

# 清理临时文件
rm /tmp/math_bank_v4.tar.gz

echo "✓ 代码更新完成"
EOF

# 步骤 4：重新构建和重启服务
echo ""
echo "[4/4] 重新构建和重启服务..."
ssh root@106.12.191.104 << 'EOF'
cd /var/www/math_bank_v4

# 后端依赖更新
echo "更新后端依赖..."
cd backend
source venv/bin/activate
pip install -r requirements.txt -q

# 前端构建
echo "构建前端..."
cd ../frontend
npm install --silent
npm run build

# 重启后端服务
echo "重启后端服务..."
systemctl restart math_bank_v4-backend

# 检查状态
echo ""
echo "=========================================="
echo "  服务状态"
echo "=========================================="
systemctl status math_bank_v4-backend --no-pager | head -10
EOF

# 清理本地临时文件
rm /tmp/math_bank_v4.tar.gz

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo "访问地址: http://106.12.191.104"
