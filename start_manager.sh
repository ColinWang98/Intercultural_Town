#!/bin/bash
echo "======================================"
echo "  Backend Manager - 图形化管理界面"
echo "======================================"
echo ""

python3 backend_manager.py

if [ $? -ne 0 ]; then
    echo ""
    echo "启动失败，请检查："
    echo "1. Python 是否已安装"
    echo "2. 是否在 Backend 目录下运行"
    echo ""
fi
