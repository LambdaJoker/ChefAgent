import base64
import json
from typing import Any

import httpx
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import Settings


class MinimaxClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._text_chat_url = f"{settings.text_base_url.rstrip('/')}/chat/completions"
        self._vision_chat_url = f"{settings.vision_base_url.rstrip('/')}/chat/completions"

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
        if not self.settings.vision_api_key:
            if self.settings.allow_mock_without_key:
                return ["鸡蛋", "番茄", "西兰花"], "检测到鸡蛋、番茄、西兰花等常见食材。"
            raise ValueError("VISION_API_KEY 未配置，无法进行图片识别。")

        prompt_text = self._build_recognition_prompt(user_hint)

        image_data = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{image_data}"

        payload = {
            "model": self.settings.vision_model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": str(prompt_text)},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        }
        content = await self._call_vision(payload)
        parsed = self._parse_json(content)
        ingredients = parsed.get("ingredients") or []
        raw_description = parsed.get("raw_description") or content
        cleaned = [str(item).strip() for item in ingredients if str(item).strip()]
        return cleaned, str(raw_description)

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
        if not self.settings.vision_api_key:
            if self.settings.allow_mock_without_key:
                return ["鸡蛋", "番茄", "西兰花"], "检测到鸡蛋、番茄、西兰花等常见食材。"
            raise ValueError("VISION_API_KEY 未配置，无法进行图片识别。")

        prompt_text = self._build_recognition_prompt(user_hint)
        payload = {
            "model": self.settings.vision_model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        },
                    ],
                }
            ],
        }
        content = await self._call_vision(payload)
        parsed = self._parse_json(content)
        ingredients = parsed.get("ingredients") or []
        raw_description = parsed.get("raw_description") or content
        cleaned = [str(item).strip() for item in ingredients if str(item).strip()]
        return cleaned, str(raw_description)

    async def cooking_chat(self, message: str, ingredients: list[str]) -> str:
        """
        功能:
            基于用户问题和已识别食材生成烹饪建议。
        参数:
            message: 用户输入问题，必填。
            ingredients: 当前食材列表，可为空。
        返回:
            str: 模型回复文本。
        关键流程:
            1) 组织系统角色与用户上下文；
            2) 调用文本模型接口；
            3) 提取首条候选消息文本返回。
        异常处理:
            未配置密钥且禁用 mock 时抛出 ValueError；
            接口错误由 _call_text 透传异常。
        """
        if not self.settings.text_api_key:
            if self.settings.allow_mock_without_key:
                context = "、".join(ingredients) if ingredients else "暂无食材"
                return f"当前可用食材：{context}。建议先做番茄炒蛋，步骤短、成功率高。"
            raise ValueError("TEXT_API_KEY 未配置，无法进行对话。")

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是 AI 私厨，回答要简洁、实用，优先给出可执行步骤和替代方案。",
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
        payload = {
            "model": self.settings.text_model,
            "temperature": 0.6,
            "messages": [{"role": "user", "content": messages[1].content}],
        }
        return await self._call_text(payload)

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

    async def _call_text(self, payload: dict[str, Any]) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.text_api_key}",
            "Content-Type": "application/json",
        }
        if self.settings.text_group_id:
            headers["X-Group-Id"] = self.settings.text_group_id

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(self._text_chat_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return self._extract_content(data)
        except httpx.TimeoutException:
            raise RuntimeError("文本模型请求超时，请稍后重试。")
        except httpx.HTTPError as e:
            raise RuntimeError(f"文本模型请求失败: {e}")

    async def _call_vision(self, payload: dict[str, Any]) -> str:
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
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
