from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str


class IngredientRecognitionResponse(BaseModel):
    ingredients: list[str]
    raw_description: str


class RecognizeByUrlRequest(BaseModel):
    image_url: str
    hint: str = ""


class RecipeItem(BaseModel):
    name: str
    ingredients: list[str]
    difficulty: str
    nutrition_score: float = Field(ge=0, le=10)
    recommendation_score: float = Field(ge=0, le=1)
    reason: str


class RecipeRecommendRequest(BaseModel):
    ingredients: list[str]
    top_k: int = Field(default=5, ge=1, le=20)


class RecipeRecommendResponse(BaseModel):
    recipes: list[RecipeItem]


class ChatRequest(BaseModel):
    message: str
    ingredients: list[str] = []


class ChatResponse(BaseModel):
    answer: str


class OssUploadResponse(BaseModel):
    object_key: str
    object_url: str
