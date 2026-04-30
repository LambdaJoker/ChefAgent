import asyncio
import base64
import json
import logging
import re
import time
from typing import Any

import httpx
from langchain_core.prompts import ChatPromptTemplate
from tavily import AsyncTavilyClient

from app.core.config import Settings
from app.services.memory import memory_graph

logger = logging.getLogger(__name__)


class MinimaxClient:
    """
    功能:
        封装与 AI 模型（Minimax/Qwen）的文本与视觉接口交互逻辑。
    关键流程:
        1) 提供图片识别食材的方法。
        2) 提供流式聊天生成菜谱的方法，并集成工具调用和上下文记忆。
    """
    def __init__(self, settings: Settings) -> None:
        """
        功能:
            初始化模型客户端。
        参数:
            settings: 包含各模型 API Key、Base URL 的配置实例。
        返回值:
            None
        关键流程:
            1) 绑定设置对象。
            2) 拼接最终的聊天补全请求 URL。
        """
        self.settings = settings
        self._text_chat_url = f"{settings.text_base_url.rstrip('/')}/chat/completions"
        self._vision_chat_url = f"{settings.vision_base_url.rstrip('/')}/chat/completions"

    def _should_enable_web_search(self, message: str) -> bool:
        """
        功能:
            根据用户问题判断是否真的需要联网搜索。
        说明:
            普通烹饪问答优先直接由模型流式回答，只有在明确涉及“搜索/最新/网上查询”等需求时，
            才启用 Tavily 工具，避免所有请求都先进入工具调用阶段，影响流式体验。
        """
        if not self.settings.tavily_api_key:
            return False

        normalized = (message or "").strip().lower()
        if not normalized:
            return False

        trigger_keywords = [
            "搜索",
            "查一下",
            "帮我查",
            "查查",
            "联网",
            "网上",
            "网搜",
            "最新",
            "最近",
            "资讯",
            "新闻",
            "百科",
            "来源",
            "tavily",
            "search",
            "google",
            "bing",
            "website",
            "web",
        ]
        return any(keyword in normalized for keyword in trigger_keywords)

    def _format_sse_event(self, event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _build_system_prompt(self, use_web_search: bool) -> str:
        base_prompt = (
            "你是一名私人厨师。请基于用户提供的食材和需求，直接输出给用户可执行、清晰、自然的最终回答。"
            "不要输出你的思考过程、推理过程、内部分析、工具调用说明、协议字段或 [TOOL_CALL] 之类的控制文本。"
            "回答优先给出明确结论和可执行步骤。"
            "如果适合补充，请在结尾自然加入“下一步建议”，例如可以提前准备什么、接下来怎么炒、可以搭配什么、失败时怎么补救、口味上还能怎么调整。"
            "当用户问做法时，尽量包含：食材准备、步骤、火候/时间要点、常见翻车提醒。"
            "当信息不足时，可以简短说明需要补充什么，但仍要先给出当前最有帮助的建议。"
        )

        if use_web_search:
            return (
                base_prompt
                + "当问题明确需要联网搜索时，可以调用 web_search 工具查找食谱、做法和参考来源。"
                + "调用工具后，最终回复里要整理出有用结论，并附上参考链接或来源。"
            )

        return (
            base_prompt
            + "当前回合不要调用任何工具，也不要假装调用工具。"
            + "请仅依靠已有知识直接回答。"
        )

    async def _do_recognize(self, prompt_text: str, image_url_or_data: str) -> tuple[list[str], str]:
        if not self.settings.vision_api_key:
            if self.settings.allow_mock_without_key:
                return ["鸡蛋", "番茄", "西兰花"], "检测到鸡蛋、番茄、西兰花等常见食材。"
            raise ValueError("VISION_API_KEY 未配置，无法进行图片识别。")

        payload = {
            "model": self.settings.vision_model,
            "temperature": 0.2,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": str(prompt_text)},
                    {"type": "image_url", "image_url": {"url": image_url_or_data}},
                ],
            }],
        }
        content = await self._call_vision(payload)
        parsed = self._parse_json(content)
        ingredients = [str(item).strip() for item in parsed.get("ingredients", []) if str(item).strip()]
        return ingredients, str(parsed.get("raw_description", content))

    async def recognize_ingredients(
        self,
        image_bytes: bytes,
        mime_type: str,
        user_hint: str | None = None,
    ) -> tuple[list[str], str]:
        """
        功能:
            调用视觉模型多模态接口识别图片中的食材，并输出结构化结果。
        参数:
            image_bytes: 图片二进制内容，必填。
            mime_type: 图片 MIME 类型，例如 image/jpeg。
            user_hint: 用户补充信息，可选。
        返回:
            tuple[list[str], str]: (食材列表, 原始描述文本)。
        关键流程:
            1) 构造标准提示词与 data URI 图片内容；
            2) 请求模型接口并提取文本响应；
            3) 解析 JSON 并清洗食材列表。
        异常处理:
            未配置密钥且禁用 mock 时抛出 ValueError；
            网络或模型响应异常由下层请求抛出异常。
        """
        prompt_text = self._build_recognition_prompt(user_hint)
        image_data = base64.b64encode(image_bytes).decode("utf-8")
        return await self._do_recognize(prompt_text, f"data:{mime_type};base64,{image_data}")

    async def recognize_ingredients_from_image_url(
        self, image_url: str, user_hint: str | None = None
    ) -> tuple[list[str], str]:
        """
        功能:
            基于公开图片 URL 调用视觉模型识别食材，适配 OSS 上传后的识别流程。
        参数:
            image_url: 可访问图片 URL，必填。
            user_hint: 用户补充信息，可选。
        返回:
            tuple[list[str], str]: (食材列表, 原始描述文本)。
        关键流程:
            1) 生成识别提示词；
            2) 以 image_url 形式构造多模态消息；
            3) 请求模型并解析 JSON 输出。
        异常处理:
            未配置密钥且禁用 mock 时抛出 ValueError；
            响应非 JSON 时降级为空结构并保留原文。
        """
        prompt_text = self._build_recognition_prompt(user_hint)
        return await self._do_recognize(prompt_text, image_url)

    async def _parse_minimax_stream(self, response_stream) -> Any:
        """统一处理 Minimax 模型的 SSE 流解析，提取 content 和 tool_calls"""
        async for line in response_stream.aiter_lines():
            line = line.strip()
            if not line:
                continue
                
            data_str = line
            if line.startswith("data: "):
                data_str = line[6:].strip()
                
            if data_str == "[DONE]":
                break
                
            try:
                data_json = json.loads(data_str)
                choices = data_json.get("choices") or []
                if not choices:
                    continue
                    
                choice = choices[0]
                delta = choice.get("delta") or {}
                
                content = delta.get("content", "")
                tool_calls = delta.get("tool_calls", [])
                
                # 兼容某些情况下直接返回 message 而不是 delta
                if not content and not tool_calls:
                    msg = choice.get("message") or {}
                    content = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])
                    
                if content or tool_calls:
                    yield {"content": content, "tool_calls": tool_calls}
            except json.JSONDecodeError:
                pass

    async def cooking_chat_stream(self, message: str, ingredients: list[str], session_id: str | None = None) -> Any:
        """
        功能:
            基于用户问题和已识别食材生成流式的烹饪建议。
        参数:
            message: 用户输入问题，必填。
            ingredients: 当前食材列表，可为空。
            session_id: 当前会话标识，可选。
        返回值:
            AsyncGenerator[str, None]: 流式的模型回复文本。
        关键流程:
            1) 校验并构建系统和用户提示词。
            2) 根据 session_id 从记忆图获取历史消息并注入上下文。
            3) 配置网络搜索工具并发起首次对话。
            4) 解析流式响应，若发生工具调用则执行并进入第二轮请求。
            5) 保存对话记忆到图中。
        异常处理:
            超时或配置缺失时进行异常抛出或 mock 返回。
        """
        if not self.settings.text_api_key:
            if self.settings.allow_mock_without_key:
                context = "、".join(ingredients) if ingredients else "暂无食材"
                async def mock_stream():
                    yield self._format_sse_event("status", {
                        "phase": "answer",
                        "label": "正在生成回答",
                        "detail": "使用本地 mock 回复",
                    })
                    mock_text = f"当前可用食材：{context}。建议先做番茄炒蛋，步骤短、成功率高。"
                    yield self._format_sse_event("content", {"text": mock_text})
                    yield self._format_sse_event("done", {"final_text": mock_text})
                return mock_stream()
            raise ValueError("TEXT_API_KEY 未配置，无法进行对话。")

        use_web_search = self._should_enable_web_search(message)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    self._build_system_prompt(use_web_search),
                ),
                (
                    "human",
                    "当前食材：{ingredients}\n用户问题：{question}",
                ),
            ]
        )
        messages = prompt.format_messages(
            ingredients="、".join(ingredients) if ingredients else "暂无",
            question=message,
        )
        system_payload = {"role": "system", "content": messages[0].content}
        user_payload = {"role": "user", "content": messages[1].content}
        
        # Load history from memory_graph
        history_payloads = []
        if session_id:
            config = {"configurable": {"thread_id": session_id}}
            state = memory_graph.get_state(config)
            
            # 【摘要优化】：如果有摘要，将其作为前置记忆注入到系统提示中
            summary = state.values.get("summary", "")
            if summary:
                system_payload["content"] += f"\n\n[之前的对话摘要]: {summary}"

            history_messages = state.values.get("messages", [])
            
            # 截断过长的历史记录（仅保留最近几条消息以辅助短期理解，配合长期摘要）
            MAX_HISTORY = 4  # 保留近 2 轮对话即可，其他由 summary 承担
            if len(history_messages) > MAX_HISTORY:
                history_messages = history_messages[-MAX_HISTORY:]

            for m in history_messages:
                if m.type == "human":
                    history_payloads.append({"role": "user", "content": m.content})
                elif m.type == "ai":
                    history_payloads.append({"role": "assistant", "content": m.content})

        tools = []
        if use_web_search:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "根据食材列表搜索网络上的食谱和烹饪方法",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "搜索关键词，例如：番茄 鸡蛋 菜谱推荐"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]

        payload = {
            "model": self.settings.text_model,
            "temperature": 0.6,
            "stream": True,
            "messages": [system_payload] + history_payloads + [user_payload],
        }
        if use_web_search:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        headers = {
            "Authorization": f"Bearer {self.settings.text_api_key}",
            "Content-Type": "application/json",
        }
        if self.settings.text_group_id:
            headers["X-Group-Id"] = self.settings.text_group_id

        async def stream_generator():
            try:
                stream_started_at = time.perf_counter()
                first_model_chunk_logged = False
                second_model_chunk_logged = False
                first_chunk_count = 0
                second_chunk_count = 0
                logger.info(
                    "chat stream start session_id=%s use_web_search=%s ingredients_count=%s",
                    session_id,
                    use_web_search,
                    len(ingredients or []),
                )
                # 初始通知前端
                if use_web_search:
                    yield self._format_sse_event("status", {
                        "phase": "thinking",
                        "label": "思考中",
                        "detail": "正在评估是否需要检索菜谱",
                    })
                else:
                    yield self._format_sse_event("status", {
                        "phase": "thinking",
                        "label": "思考中",
                        "detail": "正在分析你的需求并生成做法",
                    })
                
                async with httpx.AsyncClient(timeout=120) as client:
                    # 第一轮请求必须使用 HTTP 流式读取，否则上游会先整包返回，前端看不到打字机效果。
                    tool_calls_accumulator = {}
                    is_tool_call = False
                    first_pass_content = ""

                    async with client.stream("POST", self._text_chat_url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()

                        # 统一解析流式响应
                        async for parsed in self._parse_minimax_stream(resp):
                            content = parsed.get("content", "")
                            if content:
                                first_chunk_count += 1
                                first_pass_content += content
                                if not first_model_chunk_logged:
                                    first_model_chunk_logged = True
                                    logger.info(
                                        "chat first-pass first chunk session_id=%s elapsed_ms=%.1f preview=%s",
                                        session_id,
                                        (time.perf_counter() - stream_started_at) * 1000,
                                        content[:80],
                                    )
                                    yield self._format_sse_event("status", {
                                        "phase": "answer",
                                        "label": "正在生成回答",
                                        "detail": "已开始输出回答",
                                    })
                                # 无论是否使用 web_search，都直接流式输出内容，不要做过滤
                                yield self._format_sse_event("content", {"text": content})

                            # 处理工具调用
                            tool_calls = parsed.get("tool_calls", [])
                            if tool_calls:
                                is_tool_call = True
                                for tc in tool_calls:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_accumulator:
                                        tool_calls_accumulator[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": "function",
                                            "function": {"name": tc.get("function", {}).get("name", ""), "arguments": ""}
                                        }

                                    # 拼接参数
                                    func = tc.get("function", {})
                                    if "arguments" in func:
                                        tool_calls_accumulator[idx]["function"]["arguments"] += func["arguments"]
                                
                    final_response_content = first_pass_content

                    # 如果发生工具调用，我们需要执行工具，然后发起第二轮请求
                    if is_tool_call:
                        logger.info(
                            "chat tool-call detected session_id=%s first_pass_chunks=%s elapsed_ms=%.1f",
                            session_id,
                            first_chunk_count,
                            (time.perf_counter() - stream_started_at) * 1000,
                        )
                        yield self._format_sse_event("status", {
                            "phase": "thinking",
                            "label": "正在搜索",
                            "detail": "模型已决定调用搜索工具",
                        })
                        
                        # 构造助手消息
                        assistant_message = {
                            "role": "assistant",
                            "content": first_pass_content.strip(),
                            "tool_calls": list(tool_calls_accumulator.values()),
                        }
                        messages_payload = [system_payload] + history_payloads + [user_payload, assistant_message]
                        
                        for idx, tc in tool_calls_accumulator.items():
                            func_name = tc["function"]["name"]
                            func_args_str = tc["function"]["arguments"]
                            tool_call_id = tc["id"]
                            
                            if func_name == "web_search":
                                try:
                                    args = json.loads(func_args_str)
                                    query = args.get("query", " ".join(ingredients) + " 食谱")
                                except:
                                    query = " ".join(ingredients) + " 食谱"
                                    
                                yield self._format_sse_event("status", {
                                    "phase": "tool",
                                    "label": "正在搜索",
                                    "detail": query,
                                })
                                logger.info(
                                    "chat web_search start session_id=%s query=%s elapsed_ms=%.1f",
                                    session_id,
                                    query,
                                    (time.perf_counter() - stream_started_at) * 1000,
                                )
                                
                                if self.settings.tavily_api_key:
                                    tavily = AsyncTavilyClient(api_key=self.settings.tavily_api_key)
                                    try:
                                        # 调用 Tavily 搜索时定期回传状态，避免工具阶段长时间静默。
                                        search_task = asyncio.create_task(
                                            tavily.search(query=query, search_depth="basic", max_results=3)
                                        )
                                        search_status_messages = [
                                            "正在连接搜索服务...\n",
                                            "正在抓取相关网页...\n",
                                            "正在提取可用结果...\n",
                                            "正在整理搜索摘要...\n",
                                        ]
                                        status_index = 0
                                        while True:
                                            try:
                                                search_res = await asyncio.wait_for(
                                                    asyncio.shield(search_task),
                                                    timeout=0.8,
                                                )
                                                break
                                            except asyncio.TimeoutError:
                                                yield self._format_sse_event("status", {
                                                    "phase": "tool",
                                                    "label": "正在搜索",
                                                    "detail": search_status_messages[
                                                        min(status_index, len(search_status_messages) - 1)
                                                    ].strip(),
                                                })
                                                status_index += 1
                                        # 【优化】：提取核心字段精简返回给大模型的 JSON 体积，避免浪费 token 和干扰
                                        simplified_results = []
                                        for item in search_res.get("results", []):
                                            simplified_results.append({
                                                "title": item.get("title"),
                                                "url": item.get("url"),
                                                "content": item.get("content")
                                            })
                                        tool_result = json.dumps({"results": simplified_results}, ensure_ascii=False)
                                    except Exception as e:
                                        logger.warning(f"Tavily 搜索失败: {e}")
                                        tool_result = f"搜索失败: {str(e)}"
                                else:
                                    logger.warning("Tavily API Key 未配置，跳过网络搜索")
                                    tool_result = "Tavily API Key 未配置，无法进行网络搜索。请依靠内部知识库回答。"
                                    
                                yield self._format_sse_event("status", {
                                    "phase": "tool",
                                    "label": "搜索完成",
                                    "detail": "已获取搜索结果",
                                })
                                logger.info(
                                    "chat web_search done session_id=%s elapsed_ms=%.1f",
                                    session_id,
                                    (time.perf_counter() - stream_started_at) * 1000,
                                )
                                yield self._format_sse_event("status", {
                                    "phase": "answer",
                                    "label": "正在整理答案",
                                    "detail": "正在结合搜索结果生成最终回复",
                                })
                                
                                messages_payload.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "name": func_name,
                                    "content": tool_result
                                })
                        
                        # 发起第二轮请求，传入工具执行结果
                        payload["messages"] = messages_payload
                        payload.pop("tools", None)
                        payload.pop("tool_choice", None)
                        
                        async with client.stream("POST", self._text_chat_url, headers=headers, json=payload) as resp2:
                            resp2.raise_for_status()
                            async for parsed in self._parse_minimax_stream(resp2):
                                content = parsed.get("content", "")
                                if content:
                                    second_chunk_count += 1
                                    final_response_content += content
                                    if not second_model_chunk_logged:
                                        second_model_chunk_logged = True
                                        logger.info(
                                            "chat second-pass first chunk session_id=%s elapsed_ms=%.1f preview=%s",
                                            session_id,
                                            (time.perf_counter() - stream_started_at) * 1000,
                                            content[:80],
                                        )
                                        yield self._format_sse_event("status", {
                                            "phase": "answer",
                                            "label": "正在生成回答",
                                            "detail": "已开始输出最终答案",
                                        })
                                    yield self._format_sse_event("content", {"text": content})
                    else:
                        final_response_content = first_pass_content.strip()

                    logger.info(
                        "chat stream done session_id=%s first_pass_chunks=%s second_pass_chunks=%s total_length=%s elapsed_ms=%.1f",
                        session_id,
                        first_chunk_count,
                        second_chunk_count,
                        len(final_response_content),
                        (time.perf_counter() - stream_started_at) * 1000,
                    )
                    yield self._format_sse_event("done", {"final_text": final_response_content})

                    # 将当前回合对话保存到记忆
                    if session_id and final_response_content:
                        from langchain_core.messages import HumanMessage, AIMessage
                        
                        config = {"configurable": {"thread_id": session_id}}
                        
                        # 记录人类消息和 AI 消息
                        memory_graph.update_state(config, {"messages": [
                            HumanMessage(content=messages[1].content),
                            AIMessage(content=final_response_content)
                        ]})
                        
                        # 调用图执行，触发条件边中的 summarize_conversation（如果满足条件）
                        # 传入空字典 {} 避免 EmptyInputError，使用 to_thread 防止同步阻塞主事件循环
                        await asyncio.to_thread(memory_graph.invoke, {}, config)

            except httpx.TimeoutException:
                yield self._format_sse_event("error", {"message": "文本模型请求超时，请稍后重试。"})
            except httpx.HTTPError as e:
                yield self._format_sse_event("error", {"message": f"文本模型请求失败: {e}"})

        return stream_generator()

    @staticmethod
    def _build_recognition_prompt(user_hint: str | None) -> str:
        """
        功能:
            构造统一的食材识别提示词，避免重复逻辑。
        参数:
            user_hint: 用户补充信息，可选。
        返回:
            str: 用于模型请求的提示文本。
        关键流程:
            1) 构造系统和用户消息模板；
            2) 注入用户 hint；
            3) 提取最终用户侧提示文本。
        异常处理:
            无显式异常。
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是食材识别助手。你必须仅返回 JSON，格式: "
                    '{{"ingredients":["食材1","食材2"],"raw_description":"..."}}。',
                ),
                (
                    "human",
                    "请识别图片中的食材，尽量给出常见中文名。"
                    "用户补充信息：{hint}",
                ),
            ]
        )
        messages = prompt.format_messages(hint=user_hint or "无")
        return f"{messages[0].content}\n{messages[1].content}"

    async def _call_vision(self, payload: dict[str, Any]) -> str:
        """
        功能:
            调用视觉模型多模态接口。
        参数:
            payload: 模型请求体 JSON，包含图片 URL 或 base64。
        返回值:
            str: 模型生成的识别文本。
        关键流程:
            1) 设置视觉模型专属请求头。
            2) 发起 POST 请求。
            3) 解析并返回模型内容。
        异常处理:
            超时或网络异常时抛出 RuntimeError。
        """
        headers = {
            "Authorization": f"Bearer {self.settings.vision_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(self._vision_chat_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return self._extract_content(data)
        except httpx.TimeoutException:
            raise RuntimeError("视觉模型请求超时，请稍后重试。")
        except httpx.HTTPError as e:
            raise RuntimeError(f"视觉模型请求失败: {e}")

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        """
        功能:
            从标准模型返回格式中提取对话文本内容。
        参数:
            data: 模型返回的 JSON 字典。
        返回值:
            str: 纯文本内容。
        关键流程:
            1) 解析 choices 和 message 结构。
            2) 兼容并处理 list 格式的 content (如包含 text 的 list)。
        """
        choices = data.get("choices") or []
        if not choices:
            return "模型未返回有效内容。"
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "\n".join(part for part in text_parts if part).strip()
        return str(content).strip()

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        """
        功能:
            安全的 JSON 解析器，自动去除模型多余的 Markdown 代码块标记。
        参数:
            raw: 模型生成的原始字符串。
        返回值:
            dict[str, Any]: 解析出的 JSON 字典，解析失败则为空字典。
        关键流程:
            1) 移除前后的反引号和 "json" 标识。
            2) 尝试 loads 解析。
            3) 异常时静默并返回空。
        """
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
