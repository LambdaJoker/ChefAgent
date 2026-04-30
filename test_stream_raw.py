import asyncio
import httpx
import sys

async def test_stream():
    url = "http://localhost:8000/api/v1/chat"
    payload = {
        "message": "帮我查一下红烧肉怎么做，越详细越好",
        "ingredients": [],
        "session_id": "test_1234"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            print("Connecting to backend...", flush=True)
            async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                print(f"Status: {response.status_code}")
                # Use iter_bytes to see EXACTLY what bytes are arriving and WHEN
                async for chunk in response.aiter_bytes(chunk_size=1):
                    # Write directly to stdout to bypass print buffering
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())