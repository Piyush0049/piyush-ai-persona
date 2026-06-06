import os
import json
import time
import uuid
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from config import settings
from llm_service import llm_service
from calendar_service import calendar_service
from mongo_logger import mongo_logger

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

class BookingRequest(BaseModel):
    name: str
    email: str
    start_time: str
    end_time: str
    title: Optional[str] = "Interview"

@app.post("/api/chat")
async def api_chat(req: ChatRequest, request: Request):
    try:
        query = req.message
        history = req.history or []
        print(f"API Chat query: {query}")

        # Collect full response for logging
        full_response = ""

        async def stream_generator():
            nonlocal full_response
            try:
                async for chunk in llm_service.generate_response_stream(query, history):
                    full_response += chunk
                    yield chunk
            except Exception as e:
                print(f"Streaming error: {e}")
                error_msg = f"\n[STREAM_ERROR: {str(e)}]"
                full_response += error_msg
                yield error_msg

        # Stream the response
        response = StreamingResponse(stream_generator(), media_type="text/plain")

        # Log to MongoDB after streaming (in background)
        async def log_after_stream():
            await asyncio.sleep(0.5)  # Wait for stream to complete
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")

            mongo_logger.log_message(
                message=query,
                response=full_response,
                session_id=None,  # Could add session tracking later
                metadata={
                    "ip": client_ip,
                    "user_agent": user_agent,
                    "timestamp": time.time()
                }
            )

        # Start logging task in background
        asyncio.create_task(log_after_stream())

        return response
    except Exception as e:
        print(f"API Chat Error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.get("/api/slots")
async def api_slots(date: Optional[str] = None):
    """Get available time slots for a specific date or next 7 days"""
    try:
        slots = calendar_service.get_available_slots(date)
        return JSONResponse({"success": True, "slots": slots})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/bookings")
async def api_get_bookings():
    """Get all existing bookings"""
    try:
        bookings = calendar_service.get_booked_slots()
        return JSONResponse({"success": True, "bookings": bookings})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/config")
async def api_config():
    return JSONResponse({
        "success": True,
        "vapi_public_key": settings.VAPI_PUBLIC_KEY,
        "vapi_assistant_id": settings.VAPI_ASSISTANT_ID
    })

@app.post("/api/book")
async def api_book(req: BookingRequest):
    try:
        res = await calendar_service.book_meeting(
            name=req.name,
            email=req.email,
            start_time=req.start_time,
            end_time=req.end_time,
            title=req.title
        )
        return JSONResponse({"success": True, "booking": res})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def openai_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")
            
        last_message = messages[-1]
        query = last_message.get("content", "")
        
        history = []
        for msg in messages[:-1]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})
                
        print(f"OpenAI Gateway Query: {query}")

        response_text = await llm_service.generate_response(query, history)

        # Log to MongoDB
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        mongo_logger.log_message(
            message=query,
            response=response_text,
            session_id=None,
            metadata={
                "ip": client_ip,
                "user_agent": user_agent,
                "source": "voice_call",
                "timestamp": time.time()
            }
        )
        
        created_time = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4()}"
        
        if not stream:
            return {
                "id": completion_id,
                "object": "chat.completion",
                "created": created_time,
                "model": body.get("model", "gpt-4o-mini"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(query) // 4,
                    "completion_tokens": len(response_text) // 4,
                    "total_tokens": (len(query) + len(response_text)) // 4
                }
            }
        else:
            async def sse_generator():
                chunk_size = 10
                words = response_text.split(" ")
                
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': body.get('model', 'gpt-4o-mini'), 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
                current_idx = 0
                while current_idx < len(words):
                    chunk_words = words[current_idx:current_idx + chunk_size]
                    chunk_text = " ".join(chunk_words) + (" " if current_idx + chunk_size < len(words) else "")
                    
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": body.get("model", "gpt-4o-mini"),
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk_text},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    current_idx += chunk_size
                    await asyncio.sleep(0.05)
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': body.get('model', 'gpt-4o-mini'), 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
                
            return StreamingResponse(sse_generator(), media_type="text/event-stream")
            
    except Exception as e:
        print(f"OpenAI Gateway Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.svg")
async def serve_favicon_svg():
    from fastapi.responses import FileResponse
    return FileResponse("static/favicon.svg")

@app.get("/favicon.ico")
async def serve_favicon_ico():
    from fastapi.responses import FileResponse
    return FileResponse("static/favicon.svg")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = "static/index.html"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(
                content=f.read(),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
            )
    return HTMLResponse(content="<h1>Frontend file static/index.html not found. Please compile or create it.</h1>")

@app.get("/calendar", response_class=HTMLResponse)
async def serve_calendar():
    calendar_path = "static/calendar.html"
    if os.path.exists(calendar_path):
        with open(calendar_path, "r", encoding="utf-8") as f:
            return HTMLResponse(
                content=f.read(),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
            )
    return HTMLResponse(content="<h1>Calendar page not found.</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
