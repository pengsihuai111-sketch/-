#!/bin/bash
# 在服务器上配置 Git 部署

echo "=========================================="
echo "  在服务器上配置 Git 仓库"
echo "=========================================="

ssh root@106.12.191.104 << 'EOF'
cd /var/www/math_bank_v4

# 初始化 Git（如果还没有）
if [ ! -d .git ]; then
    git init
    git remote add origin https://github.com/pengsihuai111-sketch/-.git
fi

# 拉取最新代码
git fetch origin
git reset --hard origin/master

echo "Git 配置完成！"
EOF

echo ""
echo "服务器 Git 配置完成！"
