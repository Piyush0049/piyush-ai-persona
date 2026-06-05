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

app = FastAPI(title=settings.PROJECT_NAME)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request and Response schemas for Chat UI
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

class BookingRequest(BaseModel):
    name: str
    email: str
    start_time: str
    end_time: str

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    try:
        query = req.message
        history = req.history or []
        print(f"API Chat query: {query}")
        
        response_text = await llm_service.generate_response(query, history)
        
        return JSONResponse({
            "success": True,
            "response": response_text
        })
    except Exception as e:
        print(f"API Chat Error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.get("/api/slots")
async def api_slots():
    try:
        slots = calendar_service.get_available_slots()
        return JSONResponse({"success": True, "slots": slots})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/book")
async def api_book(req: BookingRequest):
    try:
        res = await calendar_service.book_meeting(
            name=req.name,
            email=req.email,
            start_time=req.start_time,
            end_time=req.end_time
        )
        return JSONResponse({"success": True, "booking": res})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# OpenAI-compatible /v1/chat/completions and /chat/completions endpoint for Vapi / Retell
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
        
        # Translate history
        history = []
        for msg in messages[:-1]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})
                
        print(f"OpenAI Gateway Query: {query}")
        
        # Get AI representative response
        response_text = await llm_service.generate_response(query, history)
        
        created_time = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4()}"
        
        if not stream:
            # Return single non-streaming JSON response
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
            # Return OpenAI streaming response using Server-Sent Events (SSE)
            async def sse_generator():
                # We yield the answer in small chunks to simulate streaming
                chunk_size = 10
                words = response_text.split(" ")
                
                # First chunk (role specification)
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': body.get('model', 'gpt-4o-mini'), 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
                
                # Loop through words and yield
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
                    await asyncio.sleep(0.05) # Tiny pause for realistic streaming feel
                
                # Final chunk
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': body.get('model', 'gpt-4o-mini'), 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
                
            return StreamingResponse(sse_generator(), media_type="text/event-stream")
            
    except Exception as e:
        print(f"OpenAI Gateway Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# Serve Frontend Web App
# Create static directory if it does not exist
if not os.path.exists("static"):
    os.makedirs("static")

# Mount static directory for JS and CSS files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root url
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = "static/index.html"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Frontend file static/index.html not found. Please compile or create it.</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
