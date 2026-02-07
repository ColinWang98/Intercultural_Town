# 📁 Backend 文件夹结构说明

## 项目根目录

```
D:\Backend\
├── Main.py                    # FastAPI 应用入口（状态机、对话编排）
├── personas.py                # Persona 配置（Mikko、Aino、专家、Observer）
├── tools.py                   # AgentTool 缓存管理
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略配置
├── README.md                  # 项目说明
├── README_ARCHITECTURE.md     # 完整架构文档
├── start_backend.bat          # Windows 启动脚本
└── start_backend.sh           # Linux/Mac 启动脚本
```

---

## 📂 核心目录

### 🧪 tests/
**项目测试代码**
```
tests/
├── __init__.py               # 测试包初始化
├── conftest.py               # pytest 配置
└── test_main_api.py          # FastAPI API 测试
```
- 测试 REST API 端点
- 测试消息过滤
- 测试状态机逻辑

---

## 📂 AI 工具配置目录

### 🤖 .claude/
**Claude Code 配置**
```
.claude/
├── settings.local.json       # Claude Code 权限配置
└── skills/                   # 技能目录（软链接）
    └── godot-gdscript-patterns -> .agents/skills/godot-gdscript-patterns
```
- `settings.local.json`: 配置允许的操作（Bash、git 等）
- `skills/`: Godot GDScript 技能

### 🤖 .agents/
**Claude Code Agents**
```
.agents/
└── skills/
    └── godot-gdscript-patterns/  # Godot 4 GDScript 最佳实践
        ├── SKILL.md              # 技能主文件
        └── resources/            # 技能资源文件
```
- Godot 开发指南
- GDScript 代码模式
- 信号、资源、状态机等

### 📝 .sisyphus/
**Sisyphus 计划工具**（项目规划和管理）
```
.sisyphus/
├── boulder.json              # 配置文件
├── plans/                    # 项目计划
│   ├── multi-agent-collaboration.md      # 多智能体协作计划
│   └── sub-agents-migration.md          # 子代理迁移计划
├── drafts/                   # 草稿
│   └── multi-agent-collaboration-design.md
└── notepads/                 # 笔记
    ├── multi-agent-collaboration/
    │   └── 2026-02-04_conflict-detected.md
    └── sub-agents-migration/
        └── learnings.md
```

---

## 📂 归档目录

### 📦 code_archive/
**不再使用的旧代码**
```
code_archive/
├── README.md                 # 归档说明
├── my_maori_agent/           # 旧的毛利人 Agent
├── godot_example/            # 旧 Godot 示例
├── godot_2d_example/         # 2D Godot 示例（已迁移到 Godot 项目）
├── godot-mcp/                # Godot MCP TypeScript 项目
└── adk-python/               # Google ADK Python 库完整源代码
```

### 📚 docs_archive/
**过时的文档**
```
docs_archive/
├── README.md                 # 归档说明
├── README_GAME_OVERVIEW.md   # 游戏总览（旧版）
├── AZURE_INTEGRATION_SUMMARY.md  # Azure 集成总结
└── AZURE_OPENAI_GUIDE.md     # Azure OpenAI 使用指南
```

### 🗂️ temp_dirs/
**临时文件和空目录**
```
temp_dirs/
├── README.md                 # 说明文档
├── create_dirs.py            # 临时脚本
├── api/routes/               # 空（重构计划未使用）
├── services/                 # 空
├── utils/                    # 空
└── prompts/.adk/             # 旧 ADK 会话数据库
```

### 📊 logs/
**后端运行日志**
```
logs/
├── README.md                 # 日志说明
├── backend.log               # 后端运行日志
├── backend_test.log          # 测试日志
├── server.log                # 服务器日志
├── server_error.txt          # 错误日志
└── server_output.txt         # 输出日志
```

### 🧪 test_data/
**测试 JSON 数据**
```
test_data/
├── README.md                 # 测试数据说明
├── response*.json            # API 响应测试
├── test_*.json               # 对话测试（宗教、过敏等）
└── final_test*.json          # 最终测试数据
```

---

## 🗑️ 已删除的目录

以下目录在清理时已删除：
- `.cursor/` - Cursor IDE 配置（空）
- `.codex/` - OpenAI Codex 配置
- `.opencode/` - OpenCode 配置（含 node_modules）
- `.adk/` - ADK 会话数据

---

## 📌 总结

### 保留在根目录的核心文件
| 文件 | 用途 |
|------|------|
| `Main.py` | FastAPI 应用 + 状态机 |
| `personas.py` | Persona 配置 |
| `tools.py` | 工具函数 |
| `requirements.txt` | Python 依赖 |
| `.env.example` | 环境变量模板 |
| `README*.md` | 项目文档 |
| `start_backend.*` | 启动脚本 |

### AI 工具目录（可选）
- `.claude/` - Claude Code 配置
- `.agents/` - Claude Code agents
- `.sisyphus/` - 项目规划工具

### 归档目录（可在 .gitignore 中忽略）
- `code_archive/` - 旧代码
- `docs_archive/` - 过时文档
- `temp_dirs/` - 临时文件
- `logs/` - 运行日志
- `test_data/` - 测试数据

---

*生成时间: 2026-02-07*
