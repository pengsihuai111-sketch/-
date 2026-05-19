#!/bin/bash
# Git 部署脚本 - 推送代码并在服务器上更新

set -e

echo "=========================================="
echo "  Git 部署流程"
echo "=========================================="

# 步骤 1：提交本地更改
echo ""
echo "[1/4] 检查本地更改..."
cd /d/project/题库管理/math_bank_v4

if [[ -n $(git status -s) ]]; then
    echo "发现未提交的更改："
    git status -s
    echo ""
    read -p "是否提交这些更改？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "请输入提交信息: " commit_msg
        git add .
        git commit -m "$commit_msg"
        echo "✓ 本地提交完成"
    else
        echo "跳过提交"
    fi
else
    echo "✓ 没有未提交的更改"
fi

# 步骤 2：推送到 GitHub
echo ""
echo "[2/4] 推送到 GitHub..."
git push origin master
echo "✓ 推送完成"

# 步骤 3：在服务器上拉取最新代码
echo ""
echo "[3/4] 在服务器上拉取最新代码..."
ssh root@106.12.191.104 << 'EOF'
cd /var/www/math_bank_v4

# 拉取最新代码
git fetch origin
git reset --hard origin/master

echo "✓ 代码更新完成"
EOF

# 步骤 4：重新构建和重启服务
echo ""
echo "[4/4] 重新构建和重启服务..."
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
echo "=========================================="
echo "  服务状态"
echo "=========================================="
systemctl status math_bank_v4-backend --no-pager | head -10
EOF

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo "访问地址: http://106.12.191.104"
