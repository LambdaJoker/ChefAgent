import asyncio
import httpx
import json

async def test_stream():
    url = "http://localhost:8000/api/v1/chat"
    payload = {
        "message": "帮我查一下红烧肉怎么做",
        "ingredients": [],
        "session_id": "test_123"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, timeout=30.0) as response:
                print(f"Status: {response.status_code}")
                async for line in response.aiter_lines():
                    print(f"RAW LINE: {line}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())