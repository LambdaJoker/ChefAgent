from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    功能:
        加载并校验环境变量配置。
    关键流程:
        1) 使用 pydantic_settings 自动读取 .env 文件。
        2) 校验并填充默认值。
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "ChefAgent Backend"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    frontend_origin: str = "http://localhost:5173"

    text_api_key: str = ""
    text_group_id: str = ""
    text_base_url: str = "https://api.minimax.chat/v1"
    text_model: str = "MiniMax-M2.7"
    
    vision_api_key: str = ""
    vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    vision_model: str = "qwen-vl-plus-latest"

    minimax_timeout: int = 60
    allow_mock_without_key: bool = True

    # Tavily 搜索配置
    tavily_api_key: str = ""

    # 备用模型供应商配置（当前代码主链路默认使用 Minimax）
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"

    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket_name: str = ""
    oss_endpoint: str = ""
    oss_bucket_domain: str = ""
    oss_object_prefix: str = "chefagent/uploads"


@lru_cache
def get_settings() -> Settings:
    """
    功能:
        单例模式获取配置实例。
    返回值:
        Settings: 包含全部环境变量和默认值的配置实例。
    关键流程:
        1) 调用 pydantic 解析环境并实例化 Settings。
        2) 通过 lru_cache 缓存结果以提升性能。
    """
    return Settings()
