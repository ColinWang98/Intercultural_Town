from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

# 1. 配置你的 Ollama 模型
model = LiteLlm(
    model="ollama/qwen3:8b",
    api_base="http://localhost:11434"
)

# 2. 定义官方要求的 root_agent [file:1]
root_agent = Agent(
    model=model,
    name='root_agent',
    instruction="""你是一个生活在新西兰的毛利人。
    对毛利文化有很深的了解，热爱旅游，包容心强。
    回复自然友好，带有语气词如‘emm’、‘啊’，常说'Kia Ora'。"""
)
