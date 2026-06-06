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

        # Check if query requires calendar operations
        query_lower = query.lower()
        full_conversation = " ".join([h.get("content", "") for h in history]) + " " + query

        # Detect booking intent and handle with direct calendar integration
        needs_slots = any(word in query_lower for word in ["available", "slots", "when", "date", "schedule", "book"])
        has_name_email = "@" in full_conversation  # Has email mentioned

        # If asking for slots or scheduling, inject actual calendar data into context
        if needs_slots:
            from datetime import datetime, timedelta
            import re

            # Try to extract date from query
            today = datetime.now().date()
            target_date = None

            if "tomorrow" in query_lower:
                target_date = today + timedelta(days=1)
            elif "today" in query_lower:
                target_date = today
            elif re.search(r'monday|tuesday|wednesday|thursday|friday', query_lower):
                # Parse day of week
                days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                for i, day in enumerate(days):
                    if day in query_lower:
                        days_ahead = i - today.weekday()
                        if days_ahead <= 0:
                            days_ahead += 7
                        target_date = today + timedelta(days=days_ahead)
                        break

            # Get available slots
            date_str = target_date.isoformat() if target_date else None
            slots = calendar_service.get_available_slots(date_str)

            # Limit to 5 slots and format briefly
            slot_list = []
            for slot in slots[:5]:
                try:
                    dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
                    slot_list.append(dt.strftime("%I:%M %p"))
                except:
                    pass

            # Inject slot info into the query context for LLM
            if slot_list:
                slot_info = f"\n\n[SYSTEM: Available slots for {target_date or 'upcoming days'}: {', '.join(slot_list)}. Show these to user briefly.]"
                query = query + slot_info

        # Generate LLM response
        response_text = await llm_service.generate_response(query, history)

        # WORKAROUND: If response mentions booking confirmation but didn't actually book, extract details and book now
        if "confirmed" in response_text.lower() or "booked" in response_text.lower() or "interview" in response_text.lower():
            # Try to extract booking details from conversation history
            import re
            from datetime import datetime, timedelta

            # Look for name, email, date, time in history
            full_conversation = " ".join([h.get("content", "") for h in history]) + " " + query

            # Extract email - handle voice recognition patterns like "joe at g mail dot com"
            email = None

            # Pattern 1: "joe at gmail dot com" or "joe at g mail dot com" (voice recognition format)
            email_voice = re.search(r'(\w+)\s+(?:at|@)\s+(\w+(?:\s+\w+)?)\s+(?:dot|\.)\s+(\w+)', full_conversation, re.IGNORECASE)
            if email_voice:
                username = email_voice.group(1)
                domain = email_voice.group(2).replace(" ", "")  # "g mail" -> "gmail"
                tld = email_voice.group(3)
                email = f"{username}@{domain}.{tld}"
            else:
                # Fallback to standard email pattern
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', full_conversation)
                if email_match:
                    email = email_match.group(0)

            # Extract name - only from USER messages (not AI responses to avoid "Piyush's")
            # Get only user messages from history
            user_messages = " ".join([h.get("content", "") for h in history if h.get("role") == "user"]) + " " + query

            name_patterns = [
                r'(?:name is|my name is|I am|I\'m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "my name is Joe"
                r'(?:^|\s)([A-Z][a-z]+)\s*,\s*and',  # "Joe, and my email"
            ]

            name = None
            for pattern in name_patterns:
                name_match = re.search(pattern, user_messages, re.IGNORECASE)
                if name_match:
                    name = name_match.group(1)
                    # Don't accept "Piyush" or "Piyusha" as user's name
                    if "piyush" not in name.lower():
                        break

            print(f"[AUTO-BOOK] Extracted - Name: {name}, Email: {email}")
            print(f"[AUTO-BOOK] User messages only: {user_messages[:200]}")

            # Extract time from user's last message or response (like "two PM", "3 PM", "14:00")
            time_patterns = [
                r'(\d{1,2})\s*(?:PM|pm|p\.m\.)',  # 2 PM, 3PM
                r'(\d{1,2}):(\d{2})',  # 14:00
                r'(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:PM|pm|AM|am)'  # two PM
            ]

            time_str = None
            for pattern in time_patterns:
                match = re.search(pattern, query + " " + response_text, re.IGNORECASE)
                if match:
                    time_str = match.group(0)
                    break

            # If we have all details and LLM said it's confirmed, actually book it
            if email and name and time_str and ("confirmed" in response_text.lower() or "booked" in response_text.lower()):
                try:
                    # Convert time string to 24-hour format
                    time_lower = time_str.lower()
                    hour = None

                    # Handle word numbers
                    word_to_num = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
                    for word, num in word_to_num.items():
                        if word in time_lower:
                            hour = num
                            break

                    # Handle numeric
                    if hour is None:
                        num_match = re.search(r'(\d{1,2})', time_str)
                        if num_match:
                            hour = int(num_match.group(1))

                    # Adjust for PM
                    if hour and "pm" in time_lower and hour < 12:
                        hour += 12

                    if hour:
                        # Extract date from conversation (look for "tomorrow", "Monday", "June 8", "eighth June" etc.)
                        booking_date = None
                        conv_lower = full_conversation.lower()

                        if "tomorrow" in conv_lower:
                            booking_date = datetime.now() + timedelta(days=1)
                        elif "today" in conv_lower:
                            booking_date = datetime.now()
                        else:
                            # Try to find "June 8", "8th June", "eighth June" etc.
                            date_patterns = [
                                r'june\s*(\d{1,2})',  # June 8
                                r'(\d{1,2})(?:st|nd|rd|th)?\s*june',  # 8th June
                                r'(eighth|ninth|tenth|eleventh|twelfth)\s*june',  # eighth June
                            ]

                            day_num = None
                            for pattern in date_patterns:
                                date_match = re.search(pattern, conv_lower)
                                if date_match:
                                    day_str = date_match.group(1)
                                    # Convert word to number
                                    word_to_day = {"eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12}
                                    day_num = word_to_day.get(day_str, int(day_str) if day_str.isdigit() else None)
                                    break

                            if day_num:
                                # Use June 2026 (current year in logs)
                                booking_date = datetime(2026, 6, day_num)
                            else:
                                # Default to 2 days from now if not found
                                booking_date = datetime.now() + timedelta(days=2)

                        # Create timezone-aware datetime for IST
                        from datetime import timezone as tz
                        ist = tz(timedelta(hours=5, minutes=30))
                        start_time = booking_date.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=ist)
                        end_time = start_time + timedelta(hours=1)

                        print(f"[AUTO-BOOK] Booking details - Name: {name}, Email: {email}, Time: {start_time}")

                        # Actually book it - use ISO 8601 format with timezone
                        booking_result = await calendar_service.book_meeting(
                            name=name,
                            email=email,
                            start_time=start_time.isoformat(),  # Proper ISO format: 2026-06-08T15:00:00+05:30
                            end_time=end_time.isoformat(),
                            title="Interview with Piyush Joshi"
                        )
                        print(f"[WORKAROUND] Auto-booked meeting: {booking_result}")
                except Exception as booking_error:
                    print(f"[WORKAROUND] Failed to auto-book: {booking_error}")

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
        import traceback
        traceback.print_exc()
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
