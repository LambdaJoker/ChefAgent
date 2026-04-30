from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    功能:
        定义健康检查响应的数据模型。
    """
    status: str = "ok"
    service: str


class IngredientRecognitionResponse(BaseModel):
    """
    功能:
        定义食材识别结果的响应数据模型。
    """
    ingredients: list[str]
    raw_description: str


class RecognizeByUrlRequest(BaseModel):
    """
    功能:
        定义通过 URL 识别食材的请求体数据模型。
    """
    image_url: str
    hint: str = ""


class RecipeItem(BaseModel):
    """
    功能:
        定义单个菜谱信息的数据模型。
    """
    name: str
    ingredients: list[str]
    difficulty: str
    nutrition_score: float = Field(ge=0, le=10)
    recommendation_score: float = Field(ge=0, le=1)
    reason: str


class RecipeRecommendRequest(BaseModel):
    """
    功能:
        定义菜谱推荐请求体的数据模型。
    """
    ingredients: list[str]
    top_k: int = Field(default=5, ge=1, le=20)


class RecipeRecommendResponse(BaseModel):
    """
    功能:
        定义菜谱推荐列表响应的数据模型。
    """
    recipes: list[RecipeItem]


class ChatRequest(BaseModel):
    """
    功能:
        定义私厨聊天请求体的数据模型。
    """
    message: str
    ingredients: list[str] = []
    session_id: str | None = None


class ChatResponse(BaseModel):
    """
    功能:
        定义聊天响应体的数据模型。
    """
    answer: str


class OssUploadResponse(BaseModel):
    """
    功能:
        定义 OSS 文件上传成功的响应数据模型。
    """
    object_key: str
    object_url: str