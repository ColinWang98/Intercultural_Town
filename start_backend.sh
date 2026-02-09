#!/bin/bash
# ============================================================================
# Backend 启动脚本 - Azure OpenAI 混合方案
# ============================================================================

echo "============================================"
echo "Backend 启动脚本"
echo "============================================"
echo ""

# 检查 .env 文件是否存在
if [ ! -f ".env" ]; then
    echo "[错误] 未找到 .env 文件！"
    echo ""
    echo "请先创建 .env 文件："
    echo "  1. 复制 .env.example 为 .env"
    echo "  2. 填写配置信息"
    echo ""
    exit 1
fi

# 读取 USE_AZURE 环境变量
USE_AZURE=$(grep "^USE_AZURE=" .env | cut -d'=' -f2)

echo "当前配置："
if [ "$USE_AZURE" = "true" ]; then
    echo "  - 模型: Azure OpenAI (付费)"
else
    echo "  - 模型: 本地 Ollama (免费)"
fi
echo ""

# 检查 Ollama（如果使用本地模型）
if [ "$USE_AZURE" != "true" ]; then
    echo "[检查] 正在检查 Ollama 服务..."
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "[警告] Ollama 服务未运行！"
        echo ""
        echo "请先启动 Ollama："
        echo "  ollama serve"
        echo ""
        exit 1
    fi
    echo "[OK] Ollama 服务运行中"
    echo ""
fi

# 启动 Backend
echo "[启动] 正在启动 Backend..."
echo ""
python Main.py
