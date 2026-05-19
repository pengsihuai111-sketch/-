#!/bin/bash
# 诊断脚本 - 检查数据和API问题

SERVER="106.12.191.104"

echo "=========================================="
echo "  系统诊断报告"
echo "=========================================="
echo ""

echo "1. 检查后端服务状态..."
ssh root@${SERVER} "systemctl status math_bank_v4-backend --no-pager | head -20"
echo ""

echo "2. 查看后端错误日志（最近50行）..."
ssh root@${SERVER} "journalctl -u math_bank_v4-backend -n 50 --no-pager"
echo ""

echo "3. 检查数据库题目数量..."
ssh root@${SERVER} "mysql -umath_user -pMathBank2026 -Dmath_bank -e 'SELECT COUNT(*) as question_count FROM questions;'"
echo ""

echo "4. 检查Claude API配置..."
ssh root@${SERVER} "cat /var/www/math_bank_v4/math_bank_v4/backend/.env | grep ANTHROPIC"
echo ""

echo "5. 测试Claude API网络连接..."
ssh root@${SERVER} "curl -I https://www.vibecd.cc 2>&1 | head -10"
echo ""

echo "6. 查看识别API代码..."
ssh root@${SERVER} "cat /var/www/math_bank_v4/math_bank_v4/backend/app/utils/deepseek.py | head -80"
echo ""

echo "7. 检查API路由配置..."
ssh root@${SERVER} "cat /var/www/math_bank_v4/math_bank_v4/backend/app/api/wrong_questions.py | grep -A 20 'recognize'"
echo ""

echo "=========================================="
echo "  诊断完成"
echo "=========================================="
