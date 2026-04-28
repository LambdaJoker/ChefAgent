import sqlite3
import os
import json
import httpx
from typing import TypedDict, Annotated, Literal

from langchain_core.messages import AnyMessage, RemoveMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from app.core.config import get_settings

class ChefMemoryState(TypedDict):
    """
    自定义的 State 结构，用于存储消息列表和对话摘要。
    """
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str

# 确保 resources 目录存在
os.makedirs("resources", exist_ok=True)

# 连接sqlite 
connection = sqlite3.connect("resources/personal_chief.db", check_same_thread=False) 

# 初始化checkpointer 
checkpointer = SqliteSaver(connection) 

# 自动建表 
checkpointer.setup() 

# 构造一个支持摘要的 StateGraph
def dummy_node(state: ChefMemoryState):
    """
    功能:
        空节点函数，用于维持 StateGraph 的最小执行流。
    参数:
        state: 当前的记忆状态上下文。
    返回值:
        dict: 空字典（不需要更新状态）。
    关键流程:
        1) 接收消息状态并直接返回。
    """
    return {}

def should_summarize(state: ChefMemoryState) -> Literal["summarize_conversation", END]:
    """
    功能:
        条件边：决定是否需要进行记忆摘要。
    参数:
        state: 当前对话状态。
    返回值:
        "summarize_conversation" 节点名称或 END。
    关键流程:
        如果消息数量超过 6 条（3 轮对话），触发摘要节点，否则结束。
    """
    messages = state.get("messages", [])
    if len(messages) > 6:
        return "summarize_conversation"
    return END

def summarize_conversation(state: ChefMemoryState):
    """
    功能:
        调用大模型对过长的对话历史进行摘要压缩，并删除旧消息释放 Token。
    参数:
        state: 当前对话状态。
    返回值:
        dict: 包含新摘要和需要删除的旧消息 ID。
    关键流程:
        1) 构建摘要提示词。
        2) 调用模型生成新摘要。
        3) 保留最后两条消息，其余旧消息标记为删除。
    """
    settings = get_settings()

    summary = state.get("summary", "")
    messages = state.get("messages", [])

    if summary:
        summary_message = (
            f"这是之前的对话摘要: {summary}\n\n"
            "现在请将以下新的对话内容融入到摘要中，生成一个完整且简练的最新摘要（保留用户的烹饪偏好和已讨论的菜谱等关键信息）。"
        )
    else:
        summary_message = "请对以下对话进行简练的摘要提取，重点保留用户的烹饪偏好、需求和已经讨论过的菜谱方案。"

    # 将摘要指令和当前要压缩的历史消息一起交给模型
    prompt_messages = [{"role": "system", "content": summary_message}]
    for m in messages[:-2]:
        if isinstance(m, HumanMessage):
            prompt_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            prompt_messages.append({"role": "assistant", "content": m.content})

    payload = {
        "model": settings.text_model,
        "messages": prompt_messages,
        "temperature": 0.3
    }
    
    headers = {
        "Authorization": f"Bearer {settings.text_api_key}",
        "Content-Type": "application/json",
    }
    if settings.text_group_id:
        headers["X-Group-Id"] = settings.text_group_id
        
    try:
        url = f"{settings.text_base_url.rstrip('/')}/chat/completions"
        # 使用同步 httpx 客户端发起请求
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            new_summary = data.get("choices", [])[0].get("message", {}).get("content", "")
    except Exception as e:
        # 如果摘要失败，为了不阻塞主流程，暂时保持原样并返回
        print(f"摘要生成失败: {e}")
        return {}

    # 保留最后两句话（通常是一问一答），其余的历史消息删除以释放空间
    delete_messages = [RemoveMessage(id=m.id) for m in messages[:-2]]
    
    return {
        "summary": new_summary,
        "messages": delete_messages
    }

builder = StateGraph(ChefMemoryState)
builder.add_node("dummy", dummy_node)
builder.add_node("summarize_conversation", summarize_conversation)

builder.add_edge(START, "dummy")
builder.add_conditional_edges("dummy", should_summarize)
builder.add_edge("summarize_conversation", END)

# 编译 graph 并绑定我们配置好的 SqliteSaver checkpointer
memory_graph = builder.compile(checkpointer=checkpointer)
