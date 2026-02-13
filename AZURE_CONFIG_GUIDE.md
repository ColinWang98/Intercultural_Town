# Azure OpenAI 配置指南

## 默认行为

**默认优先使用 Azure OpenAI**，如未配置则自动回退到本地 Ollama。

---

## 使用 Azure OpenAI

### 方法 1: 环境变量（推荐）

在启动后端前设置以下环境变量：

```bash
# Windows PowerShell
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-api-key"
$env:AZURE_OPENAI_API_VERSION = "2024-02-01"

# Windows CMD
set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
set AZURE_OPENAI_API_KEY=your-api-key
set AZURE_OPENAI_API_VERSION=2024-02-01

# Linux/Mac
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_API_VERSION="2024-02-01"
```

### 方法 2: .env 文件

在 `D:\Backend\.env` 文件中添加：

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-01
```

---

## 模型分配

| Persona | Azure 模型 | Ollama 模型 |
|---------|-----------|-------------|
| mikko | azure/gpt-5-nano | ollama_chat/qwen3:4b-instruct |
| aino | azure/gpt-5-nano | ollama_chat/qwen3:4b-instruct-2507-fp16 |
| observer | azure/gpt-5-nano | ollama_chat/qwen3:8b |
| analyser | azure/gpt-4o | ollama_chat/qwen3:8b |

**默认模型**: `azure/gpt-5.2-chat`

---

## 强制使用 Ollama

如果想强制使用本地 Ollama 而不是 Azure：

```bash
# Windows PowerShell
$env:USE_AZURE = "false"

# Windows CMD
set USE_AZURE=false

# Linux/Mac
export USE_AZURE=false
```

或在 `.env` 文件中添加：
```
USE_AZURE=false
```

---

## 启动后端

```bash
cd D:/Backend
python Main.py
```

**预期输出**：

**使用 Azure:**
```
[INFO] 使用 Azure OpenAI 模型
[INFO] Registered AgentTool: mikko
[INFO] Registered AgentTool: aino
[INFO] Registered AgentTool: observer
[INFO] Registered AgentTool: analyser
```

**回退到 Ollama (未配置 Azure):**
```
[WARN] Azure 配置不完整，自动回退到本地 Ollama 模型
[WARN] 如需使用 Azure，请设置: AZURE_OPENAI_ENDPOINT 和 AZURE_OPENAI_API_KEY
[INFO] 使用本地 Ollama 模型
```

---

## 验证配置

```bash
python -X utf8 -c "
import personas
print('USE_AZURE:', personas.USE_AZURE)
print('当前模型:', 'Azure' if personas.USE_AZURE else 'Ollama')
"
```

---

## 常见问题

### Q: 为什么默认是 Azure 但实际用的是 Ollama？
**A**: 因为没有配置 Azure 环境变量。系统会自动回退到 Ollama 并给出警告提示。

### Q: 如何确认正在使用 Azure？
**A**: 启动时看到 `[INFO] 使用 Azure OpenAI 模型` 表示正在使用 Azure。

### Q: Azure 配置错误会怎样？
**A**: 系统会自动回退到 Ollama，不会导致后端启动失败。

### Q: 可以混合使用 Azure 和 Ollama 吗？
**A**: 当前不支持。要么全部用 Azure，要么全部用 Ollama。
