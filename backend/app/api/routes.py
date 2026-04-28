from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

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
    """
    功能:
        提供 MinimaxClient 实例的依赖注入函数。
    参数:
        settings: 配置项依赖。
    返回值:
        MinimaxClient: 初始化的 Minimax 客户端。
    关键流程:
        1) 获取当前配置。
        2) 实例化并返回 MinimaxClient。
    """
    return MinimaxClient(settings)


def get_recipe_service() -> RecipeService:
    """
    功能:
        提供 RecipeService 实例的依赖注入函数。
    返回值:
        RecipeService: 初始化的菜谱服务。
    关键流程:
        1) 实例化并返回 RecipeService。
    """
    return RecipeService()


def get_oss_service(settings: Settings = Depends(get_settings)) -> OssService:
    """
    功能:
        提供 OssService 实例的依赖注入函数。
    参数:
        settings: 配置项依赖。
    返回值:
        OssService: 初始化的 OSS 服务。
    关键流程:
        1) 获取当前配置。
        2) 实例化并返回 OssService。
    """
    return OssService(settings)


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    功能:
        健康检查接口，用于探测服务是否正常运行。
    参数:
        settings: 配置项依赖。
    返回值:
        HealthResponse: 包含状态和服务名称的响应。
    关键流程:
        1) 读取配置中的服务名。
        2) 返回服务正常状态。
    """
    return HealthResponse(service=settings.app_name)


@router.post("/recognize", response_model=IngredientRecognitionResponse)
async def recognize_ingredients(
    image: UploadFile = File(...),
    hint: str = Form(default=""),
    minimax: MinimaxClient = Depends(get_minimax_client),
) -> IngredientRecognitionResponse:
    """
    功能:
        接收前端直接上传的图片，调用多模态模型识别食材。
    参数:
        image: 上传的图片文件。
        hint: 用户的额外提示信息。
        minimax: 模型客户端依赖。
    返回值:
        IngredientRecognitionResponse: 食材识别结果及原始描述。
    关键流程:
        1) 读取图片二进制数据及类型。
        2) 调用模型进行多模态识别。
        3) 返回识别的食材列表。
    异常处理:
        识别失败时抛出 500 HTTP 异常。
    """
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
    """
    功能:
        基于给定的食材列表，调用菜谱服务推荐相应菜谱。
    参数:
        request: 包含食材列表和期望返回数量的请求体。
        service: 菜谱服务依赖。
    返回值:
        RecipeRecommendResponse: 包含推荐菜谱列表的响应。
    关键流程:
        1) 接收食材数据并传入服务。
        2) 获取生成的推荐列表。
        3) 构造并返回响应体。
    """
    recipes = service.recommend(request.ingredients, request.top_k)
    return RecipeRecommendResponse(recipes=recipes)


@router.post("/chat")
async def cooking_chat(
    request: ChatRequest,
    minimax: MinimaxClient = Depends(get_minimax_client),
):
    """
    功能:
        提供与 AI 私厨的对话聊天接口，支持流式返回及多轮记忆。
    参数:
        request: 包含用户消息、上下文食材及 session_id 的请求体。
        minimax: 模型客户端依赖。
    返回值:
        StreamingResponse: 聊天结果流，用于前端打字机效果。
    关键流程:
        1) 解析用户请求及 session_id。
        2) 调用 MinimaxClient 的流式接口。
        3) 包装为 StreamingResponse 返回。
    异常处理:
        发生未知错误时抛出 500 异常。
    """
    try:
        # We pass session_id to chat
        generator = await minimax.cooking_chat_stream(
            message=request.message,
            ingredients=request.ingredients,
            session_id=request.session_id,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
