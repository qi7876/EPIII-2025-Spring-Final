# ai_agent/agent_config.py

# 中间服务器的WebSocket地址
# 注意URL中的 {client_type} 和 {client_id} 占位符
# 我们将在连接时替换它们
INTERMEDIARY_SERVER_URL_TEMPLATE = "ws://localhost:8000/ws/{client_type}/{client_id}"
AGENT_ID = "cli_agent_001" # 此AI代理的唯一ID

# LLM API 相关配置 (后续使用)
LLM_API_KEY = "sk-c65c010ea3f64c8fbda2d3d841c46ab4" # 替换为你的API Key
LLM_BASE_URL = "https://api.deepseek.com" # 替换为你的API Base URL
LLM_MODEL = "deepseek-chat" # 替换为你的模型名称