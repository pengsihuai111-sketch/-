#!/bin/bash
# 更新服务器 .env 配置

cat >> /var/www/math_bank_v4/math_bank_v4/backend/.env << 'EOF'

# Vision API 配置（图片识别）
VISION_API_KEY=sk-ef3bcae48dab4243e19ccd2986363a0aec0bc40afb2b2b9df571b076a5063dfe
VISION_API_URL=https://www.vibecd.cc/v1/chat/completions
VISION_MODEL=claude-3-5-sonnet-20241022

# Doubao API 配置（文本生成）
DOUBAO_API_KEY=sk-ef3bcae48dab4243e19ccd2986363a0aec0bc40afb2b2b9df571b076a5063dfe
DOUBAO_API_URL=https://www.vibecd.cc/v1/chat/completions
DOUBAO_MODEL=claude-3-5-sonnet-20241022

# 文本模型提供商选择
TEXT_LLM_PROVIDER=doubao
EOF

echo "✓ .env 配置已更新"
echo ""
echo "重启后端服务..."
systemctl restart math_bank_v4-backend
echo "✓ 后端服务已重启"
