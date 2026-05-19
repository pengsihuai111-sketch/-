# 诊断脚本 - 检查数据和API问题
$server = "106.12.191.104"

Write-Host "=========================================="
Write-Host "  系统诊断报告"
Write-Host "=========================================="
Write-Host ""

Write-Host "1. 检查Claude API配置..."
ssh root@$server "cat /var/www/math_bank_v4/math_bank_v4/backend/.env | grep ANTHROPIC"
Write-Host ""

Write-Host "2. 检查数据库题目数量..."
ssh root@$server "mysql -umath_user -pMathBank2026 -Dmath_bank -e 'SELECT COUNT(*) as question_count FROM questions;'"
Write-Host ""

Write-Host "3. 查看后端错误日志（最近30行）..."
ssh root@$server "journalctl -u math_bank_v4-backend -n 30 --no-pager"
Write-Host ""

Write-Host "4. 测试Claude API网络连接..."
ssh root@$server "curl -I https://www.vibecd.cc 2>&1 | head -10"
Write-Host ""

Write-Host "5. 查看识别API代码（前80行）..."
ssh root@$server "head -80 /var/www/math_bank_v4/math_bank_v4/backend/app/utils/deepseek.py"
Write-Host ""

Write-Host "=========================================="
Write-Host "  诊断完成"
Write-Host "=========================================="
