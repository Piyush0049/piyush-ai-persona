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

# Function calling endpoints for Vapi
class GetSlotsRequest(BaseModel):
    date: Optional[str] = None  # Format: "YYYY-MM-DD" or natural like "tomorrow", "next monday"

@app.get("/functions/get_available_slots")
async def function_get_available_slots_get():
    """GET endpoint that asks for date"""
    from datetime import datetime, timedelta
    today = datetime.now()
    suggestions = []
    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() < 5:
            day_name = "today" if i == 0 else ("tomorrow" if i == 1 else day.strftime("%A"))
            suggestions.append(day_name)
    suggestion_text = ", ".join(suggestions[:5])
    return JSONResponse({
        "result": "What date works for you?"
    })

@app.post("/functions/get_available_slots")
async def function_get_available_slots(req: GetSlotsRequest):
    """Function for Vapi to get available calendar slots for a specific date"""
    try:
        from datetime import datetime, timedelta

        print(f"Get slots request: date={req.date}")

        # If no date provided, ask for it
        if not req.date:
            # Get next 7 days to suggest
            today = datetime.now()
            suggestions = []
            for i in range(7):
                day = today + timedelta(days=i)
                if day.weekday() < 5:  # Only weekdays
                    day_name = "today" if i == 0 else ("tomorrow" if i == 1 else day.strftime("%A"))
                    suggestions.append(day_name)

            suggestion_text = ", ".join(suggestions[:5])
            return JSONResponse({
                "result": "What date?"
            })

        # Parse the date request
        target_date = None
        req_date_lower = req.date.lower().strip()
        today = datetime.now().date()

        # Handle common date phrases
        if req_date_lower in ["today"]:
            target_date = today
        elif req_date_lower in ["tomorrow"]:
            target_date = today + timedelta(days=1)
        elif "next" in req_date_lower:
            # Try to parse "next monday", "next tuesday", etc.
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for i, day in enumerate(days):
                if day in req_date_lower:
                    days_ahead = i - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    target_date = today + timedelta(days=days_ahead)
                    break
        else:
            # Try to parse as ISO date format
            try:
                target_date = datetime.strptime(req.date, "%Y-%m-%d").date()
            except:
                pass

        if not target_date:
            return JSONResponse({
                "result": "Which day? Say 'tomorrow', 'Monday', or a date."
            })

        # Get slots for the specific date
        date_str = target_date.isoformat()
        slots = calendar_service.get_available_slots(date_str)

        if not slots:
            next_day = target_date + timedelta(days=1)
            return JSONResponse({
                "result": f"No slots on {target_date.strftime('%A')}. Try {next_day.strftime('%A')} instead?"
            })

        # Format slots for speaking - only times, limit to 5 slots
        slot_text = []
        max_slots = min(5, len(slots))  # Show max 5 slots
        for i in range(max_slots):
            slot = slots[i]
            start_iso = slot.get("start", "")
            try:
                dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                time_str = dt.strftime("%I:%M %p")
                slot_text.append(time_str)
            except:
                formatted_time = slot.get("formatted", "")
                slot_text.append(formatted_time)

        speakable_slots = ", ".join(slot_text)
        day_name = target_date.strftime("%A, %B %d")

        print(f"Returning {max_slots} slots for {day_name}")

        return JSONResponse({
            "result": f"{day_name}: {speakable_slots}. Which time?"
        })
    except Exception as e:
        print(f"Error fetching slots: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "result": "I'm having trouble accessing the calendar right now. Please try again in a moment."
        })

def find_next_available_slot(after_dt) -> Optional[Dict[str, Any]]:
    """Find the next available slot after the given datetime"""
    from datetime import datetime, timedelta

    date_str = after_dt.date().isoformat()
    slots = calendar_service.get_available_slots(date_str)

    # Filter slots that are after the requested time
    for slot in slots:
        try:
            slot_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            if slot_dt.replace(tzinfo=None) > after_dt:
                return slot
        except:
            continue

    # If no slots today, try next day
    next_day = (after_dt + timedelta(days=1)).date().isoformat()
    next_day_slots = calendar_service.get_available_slots(next_day)
    return next_day_slots[0] if next_day_slots else None

class FunctionBookMeetingRequest(BaseModel):
    name: str
    email: str
    slot: str  # Format: "2026-06-10 14:00"

@app.post("/functions/book_meeting")
async def function_book_meeting(req: FunctionBookMeetingRequest):
    """Function for Vapi to book a meeting - books directly on the call"""
    try:
        from datetime import datetime, timedelta

        print(f"Booking request: name={req.name}, email={req.email}, slot={req.slot}")

        # Parse the slot time - handle both formats
        try:
            # Try parsing with timezone info first
            start_dt = datetime.fromisoformat(req.slot.replace("Z", "+00:00"))
            if start_dt.tzinfo:
                start_dt = start_dt.replace(tzinfo=None)
        except:
            # Fallback to simple format
            start_dt = datetime.strptime(req.slot, "%Y-%m-%d %H:%M")

        end_dt = start_dt + timedelta(hours=1)

        # Book the meeting directly (calendar_service already checks availability)
        booking_result = await calendar_service.book_meeting(
            name=req.name,
            email=req.email,
            start_time=start_dt.strftime("%Y-%m-%d %H:%M"),
            end_time=end_dt.strftime("%Y-%m-%d %H:%M"),
            title="Interview with Piyush Joshi"
        )

        print(f"Booking successful: {booking_result}")

        # Format the time in a speakable way
        formatted_time = start_dt.strftime("%A, %B %d at %I:%M %p")

        return JSONResponse({
            "result": f"Done. Confirmed for {formatted_time} IST."
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Booking error: {error_msg}")

        # Check if it's a double-booking error
        if "already booked" in error_msg.lower() or "time slot" in error_msg.lower():
            # Try to find next available slot after the requested time
            try:
                next_slot = find_next_available_slot(start_dt)
                if next_slot:
                    next_time = datetime.fromisoformat(next_slot["start"].replace("Z", "+00:00")).strftime("%I:%M %p")
                    return JSONResponse({
                        "result": f"That slot's taken. Next available is {next_time}. Book it?"
                    })
            except:
                pass
            return JSONResponse({
                "result": "That slot's taken. Checking other times."
            })

        return JSONResponse({
            "result": "Booking failed. Please repeat your name and email."
        })


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def openai_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        tools = body.get("tools", [])
        tool_choice = body.get("tool_choice", "auto")

        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        last_message = messages[-1]

        # Handle function call results
        if last_message.get("role") == "tool":
            # Tool response - continue conversation
            query = "Continue based on the function result"
        else:
            query = last_message.get("content", "")

        history = []
        for msg in messages[:-1]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})

        print(f"OpenAI Gateway Query: {query}")

        # Check if query requires function calling
        query_lower = query.lower()
        needs_calendar = any(word in query_lower for word in ["book", "schedule", "available", "slots", "calendar", "meeting", "interview", "availability"])

        # If tools are available and query needs calendar, return function call
        if tools and needs_calendar:
            # Check if asking for availability
            if any(word in query_lower for word in ["available", "slots", "when", "calendar", "check"]):
                created_time = int(time.time())
                completion_id = f"chatcmpl-{uuid.uuid4()}"
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created_time,
                    "model": body.get("model", "gpt-4o-mini"),
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": f"call_{uuid.uuid4().hex[:24]}",
                                "type": "function",
                                "function": {
                                    "name": "get_available_slots",
                                    "arguments": "{}"
                                }
                            }]
                        },
                        "finish_reason": "tool_calls"
                    }],
                    "usage": {
                        "prompt_tokens": len(query) // 4,
                        "completion_tokens": 20,
                        "total_tokens": (len(query) // 4) + 20
                    }
                }

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
