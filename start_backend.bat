@echo off
REM ============================================================================
REM Backend 启动脚本 - Azure OpenAI 混合方案
REM ============================================================================

echo ============================================
echo Backend 启动脚本
echo ============================================
echo.

REM 检查 .env 文件是否存在
if not exist ".env" (
    echo [错误] 未找到 .env 文件！
    echo.
    echo 请先创建 .env 文件：
    echo   1. 复制 .env.example 为 .env
    echo   2. 填写配置信息
    echo.
    pause
    exit /b 1
)

REM 读取 USE_AZURE 环境变量
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="USE_AZURE" set USE_AZURE=%%b
)

echo 当前配置：
if "%USE_AZURE%"=="true" (
    echo   - 模型: Azure OpenAI ^(付费^)
) else (
    echo   - 模型: 本地 Ollama ^(免费^)
)
echo.

REM 检查 Ollama（如果使用本地模型）
if "%USE_AZURE%"=="false" (
    echo [检查] 正在检查 Ollama 服务...
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if errorlevel 1 (
        echo [警告] Ollama 服务未运行！
        echo.
        echo 请先启动 Ollama：
        echo   ollama serve
        echo.
        pause
        exit /b 1
    )
    echo [OK] Ollama 服务运行中
    echo.
)

REM 启动 Backend
echo [启动] 正在启动 Backend...
echo.
python Main.py

pause
