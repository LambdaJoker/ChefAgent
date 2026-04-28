from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException

from app.core.config import Settings, get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngredientRecognitionResponse,
    OssUploadResponse,
    RecognizeByUrlRequest,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
)
from app.services.minimax_client import MinimaxClient
from app.services.oss_service import OssService
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/api/v1")


def get_minimax_client(settings: Settings = Depends(get_settings)) -> MinimaxClient:
    return MinimaxClient(settings)


def get_recipe_service() -> RecipeService:
    return RecipeService()


def get_oss_service(settings: Settings = Depends(get_settings)) -> OssService:
    return OssService(settings)


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(service=settings.app_name)


@router.post("/recognize", response_model=IngredientRecognitionResponse)
async def recognize_ingredients(
    image: UploadFile = File(...),
    hint: str = Form(default=""),
    minimax: MinimaxClient = Depends(get_minimax_client),
) -> IngredientRecognitionResponse:
    raw = await image.read()
    mime_type = image.content_type or "image/jpeg"
    try:
        ingredients, raw_description = await minimax.recognize_ingredients(
            image_bytes=raw,
            mime_type=mime_type,
            user_hint=hint,
        )
        return IngredientRecognitionResponse(
            ingredients=ingredients,
            raw_description=raw_description,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recognize-by-url", response_model=IngredientRecognitionResponse)
async def recognize_ingredients_by_url(
    request: RecognizeByUrlRequest,
    minimax: MinimaxClient = Depends(get_minimax_client),
) -> IngredientRecognitionResponse:
    """
    功能:
        通过图片 URL 调用模型进行食材识别，适配 OSS 上传后的识别链路。
    参数:
        request: 包含 image_url 和 hint 的请求体。
        minimax: 模型客户端依赖。
    返回:
        IngredientRecognitionResponse: 标准识别响应。
    关键流程:
        1) 接收前端上传后回传的图片 URL；
        2) 调用 URL 识别方法；
        3) 返回识别结果给前端。
    异常处理:
        URL 不可访问或模型失败时会抛出 HTTP 异常。
    """
    try:
        ingredients, raw_description = await minimax.recognize_ingredients_from_image_url(
            image_url=request.image_url,
            user_hint=request.hint,
        )
        return IngredientRecognitionResponse(
            ingredients=ingredients,
            raw_description=raw_description,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/uploads/image", response_model=OssUploadResponse)
async def upload_image_to_oss(
    image: UploadFile = File(...),
    oss_service: OssService = Depends(get_oss_service),
) -> OssUploadResponse:
    """
    功能:
        接收前端图片并上传至阿里云 OSS，返回对象路径和访问 URL。
    参数:
        image: 前端上传的图片文件。
        oss_service: OSS 上传服务依赖。
    返回:
        OssUploadResponse: 包含 object_key 与 object_url。
    关键流程:
        1) 读取上传文件二进制；
        2) 调用 OSS 服务上传；
        3) 返回上传结果供前端后续识别接口使用。
    异常处理:
        OSS 配置缺失或上传失败时抛出异常。
    """
    try:
        raw_bytes = await image.read()
        object_key, object_url = oss_service.upload_image(
            image_bytes=raw_bytes,
            filename=image.filename or "unknown.jpg",
        )
        return OssUploadResponse(object_key=object_key, object_url=object_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipes/recommend", response_model=RecipeRecommendResponse)
async def recommend_recipes(
    request: RecipeRecommendRequest,
    service: RecipeService = Depends(get_recipe_service),
) -> RecipeRecommendResponse:
    recipes = service.recommend(request.ingredients, request.top_k)
    return RecipeRecommendResponse(recipes=recipes)


@router.post("/chat", response_model=ChatResponse)
async def cooking_chat(
    request: ChatRequest,
    minimax: MinimaxClient = Depends(get_minimax_client),
) -> ChatResponse:
    try:
        answer = await minimax.cooking_chat(request.message, request.ingredients)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
