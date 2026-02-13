#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend 诊断脚本

检查：
1. Azure 配置
2. 依赖版本
3. 代码问题扫描
4. 日志错误模式分析
"""

import os
import re
import sys
from pathlib import Path

def check_azure_config():
    """检查 Azure OpenAI 配置"""
    print("\n=== Azure 配置检查 ===")

    from dotenv import load_dotenv
    load_dotenv()

    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '')
    api_key = os.getenv('AZURE_OPENAI_API_KEY', '')

    print(f"Endpoint: {endpoint}")
    print(f"API Key exists: {bool(api_key)}")

    # 检查 endpoint 格式
    if endpoint:
        # Azure endpoint 应该是 https://<resource>.openai.azure.com/
        if not endpoint.startswith('https://'):
            print("❌ Endpoint 格式错误")
            print(f"   当前: {endpoint}")
            print(f"   正确格式: https://<resource>.openai.azure.com/")
        else:
            print("✅ Endpoint 格式正确")

    # 检查 API key
    if api_key:
        # 检查是否以 "sk-" 或 "azure-" 开头
        if api_key.startswith('sk-'):
            print("⚠️ 使用的是 SK key，可能不兼容 Azure OpenAI")
        elif api_key.startswith('azure-'):
            print("✅ 使用的是 Azure OpenAI key")
        else:
            print("❓ 未知的 key 格式")
            print(f"   Key 前缀: {api_key[:10]}...")
    else:
        print("❌ API Key 未设置")

    return endpoint and api_key

def check_dependencies():
    """检查依赖版本"""
    print("\n=== 依赖版本检查 ===")

    # 检查主要依赖
    dependencies = {
        'fastapi': 'FastAPI',
        'starlette': 'Starlette',
        'litellm': 'LiteLLM',
        'python-dotenv': 'python-dotenv',
    }

    for module_name, version in dependencies.items():
        try:
            mod = __import__(module_name)
            version = mod.__version__
            print(f"✅ {module_name}: {version}")
        except ImportError:
            print(f"❌ {module_name}: 未安装")
        except Exception as e:
            print(f"⚠️ {module_name}: {e}")

    # 检查 litellm 配置
    try:
        import litellm
        print(f"✅ litellm: {litellm.__version__}")
    except Exception:
        print(f"⚠️ litellm: {e}")

def scan_code_issues():
    """扫描代码中的常见问题"""
    print("\n=== 代码问题扫描 ===")

    main_py = Path("Main.py")

    if not main_py.exists():
        print("❌ Main.py 不在当前目录")
        return

    content = main_py.read_text(encoding='utf-8', errors='replace')

    issues = []

    # 检查 1: 大量 ^^^^^^ 字符（日志噪音）
    tilda_count = content.count('^')
    if tilda_count > 100:
        issues.append(f"• 发现 {tilda_count} 个 '^' 字符（可能是 Litellm 日志噪音）")
        print(f"  位置: 可能在日志输出或依赖库")

    # 检查 2: UnicodeEncodeError
    if 'UnicodeEncodeError' in content:
        issues.append("• 发现 UnicodeEncodeError（Windows 控制台编码问题）")
        print(f"  建议: 在代码中避免输出中文字符，或设置 PYTHONIOENCODING=utf-8")

    # 检查 3: 未处理的异常
    if 'raise Exception' in content and 'HTTPException' in content:
        issues.append("• 发现 raise Exception('HTTPException')")
        print(f"  建议: 检查异常处理是否完善")

    # 检查 4: Azure API 调用
    azure_refs = content.count('azure/')
    if azure_refs > 10:
        issues.append(f"• 发现 {azure_refs} 处 Azure API 引用（可能配置错误）")

    if not issues:
        print("✅ 未发现明显问题")
    else:
        print(f"⚠️ 发现 {len(issues)} 个潜在问题")

    return issues

def analyze_log_errors():
    """分析日志中的错误模式"""
    print("\n=== 日志错误模式分析 ===")

    print("常见错误模式：")
    print("1. HTTP 500 - 服务器内部错误")
    print("2. UnicodeEncodeError - 编码问题（控制台无法显示中文）")
    print("3. Azure 404 - API endpoint 不存在")
    print("4. 大量 ^^^^^ - Litellm 日志噪音")
    print("5. AI 输出指令性文字 - prompt 泄露")

    print("\n根据日志判断可能原因：")
    print("• 如果看到 'AzureException NotFoundError' → Azure API 配置错误")
    print("• 如果看到大量 '^^^^^^^^' → Litellm 日志级别太高")
    print("• 如果看到 'HTTPException' → 代码有未捕获的异常")
    print("• 如果看到 '**选项：**' → prompt 指令泄露（已修复）")

def main():
    print("""
╔═══════════════════════════════════╗
║           Backend 诊断工具                ║
║        诊断后端崩溃和日志问题              ║
╚═════════════════════════════════╝
""")

    print("\n建议操作：")
    print("1. 检查 .env 文件中的 Azure 配置")
    print("2. 重启后端，观察是否还有 500 错误")
    print("3. 如果仍然崩溃，检查 Godot 控制台的完整错误信息")
    print("4. 测试对话时，留意 AI 是否还输出指令性文字")
    print("5. 考虑降级到 Ollama 模型（避免 Azure API 问题）")

    # 执行检查
    check_azure_config()
    check_dependencies()
    scan_code_issues()
    analyze_log_errors()

    print("\n" + "="*50)
    print("\n按回车退出...")

if __name__ == "__main__":
    main()
