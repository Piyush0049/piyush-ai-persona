import json
import re
import datetime
import httpx
from typing import List, Dict, Any, AsyncGenerator
from config import settings
from rag_service import rag_service
from calendar_service import calendar_service

SYSTEM_PROMPT = """You are the AI Representative of Piyush Joshi, a Software Engineer and Computer Science student at Netaji Subhas University of Technology (NSUT), Delhi (graduating in 2026).
Your goal is to answer questions about Piyush's background, education, experience, skills, and public GitHub repositories, and help the caller/chatter book an interview with him.

Here are your instructions:
1. Persona: You are Piyush's AI Representative. Be warm, professional, and concise. Avoid long walls of text. Speak in the third person about Piyush (e.g., "Piyush is a computer science student...", "He built a chat application...").
2. Core Skills & Experience:
   - Education: Bachelor of Science in Computer Science at NSUT Delhi (Nov 2022 - Present).
   - Experience: Software Engineer at CampusBid (Nov 2024 - Present), Full Stack Developer at Workved Spaces (Aug 2024 - Oct 2024).
   - Core Stack: MERN (MongoDB, Express, React, Node.js), Next.js, TypeScript, Python, C++, AWS, Docker, CI/CD.
3. RAG Grounding: You must answer questions based on the provided context (Resume and Github repos). Do not make up facts or projects. If the answer is not in the context, say: "I don't have that specific information in Piyush's records, but I can ask him to follow up with you on that."
4. Calendar Booking:
   - You can book an interview directly.
   - If the user wants to book a call, check availability first! You must have their Name and Email. If you don't have them, ask for them.
   - Once you have the name and email, you can check availability.
   - To check availability, you MUST call the availability tool using this exact format:
     [TOOL_CALL: check_availability()]
   - To book a slot, you MUST call the booking tool with the details:
     [TOOL_CALL: book_meeting(name="User Name", email="user@email.com", start_time="ISO_START", end_time="ISO_END")]
   - Important: When you output a tool call, output ONLY the tool call block and nothing else in that turn. The system will execute it and provide the results in the next turn.

Current Date and Time: {current_time}
"""

class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        print(f"LLM Provider Selected: {self.provider}")

    async def call_openai(self, messages: List[Dict[str, str]]) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.3
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                raise Exception(f"OpenAI API failed: {resp.text}")

    async def call_gemini(self, messages: List[Dict[str, str]]) -> str:
        # Translate OpenAI format to Gemini format
        contents = []
        system_instruction = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}]
                })
            elif msg["role"] == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, timeout=30.0)
            if resp.status_code == 200:
                try:
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                except KeyError:
                    return "I'm sorry, I encountered an issue parsing the response."
            else:
                raise Exception(f"Gemini API failed: {resp.text}")

    async def call_ollama(self, messages: List[Dict[str, str]]) -> str:
        url = f"{settings.OLLAMA_URL}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "temperature": 0.3
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                raise Exception(f"Ollama API failed: {resp.text}")

    async def call_bedrock(self, messages: List[Dict[str, str]]) -> str:
        import boto3
        
        # Initialize Bedrock client
        kwargs = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
            
        try:
            client = boto3.client("bedrock-runtime", **kwargs)
            
            # Format system instructions and conversation messages for Converse API
            system_prompts = []
            converse_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompts.append({"text": msg["content"]})
                else:
                    role = msg["role"]
                    if role not in ("user", "assistant"):
                        role = "user"
                    
                    # Bedrock Converse API requires the first message to be from 'user'
                    if not converse_messages and role == "assistant":
                        continue
                        
                    # Bedrock Converse API requires strictly alternating roles.
                    # Merge consecutive messages with the same role.
                    if converse_messages and converse_messages[-1]["role"] == role:
                        converse_messages[-1]["content"][0]["text"] += "\n\n" + msg["content"]
                    else:
                        converse_messages.append({
                            "role": role,
                            "content": [{"text": msg["content"]}]
                        })
            
            # Synchronous call executed inside an executor if async is needed, 
            # but directly calling it is safe here since we are in an async route.
            # To avoid blocking the event loop, we can run it in a thread pool.
            import asyncio
            loop = asyncio.get_event_loop()
            
            def invoke():
                return client.converse(
                    modelId=settings.AWS_BEDROCK_MODEL,
                    messages=converse_messages,
                    system=system_prompts,
                    inferenceConfig={
                        "temperature": 0.3,
                        "maxTokens": 2048
                    }
                )
                
            response = await loop.run_in_executor(None, invoke)
            return response["output"]["message"]["content"][0]["text"]
        except Exception as e:
            raise Exception(f"AWS Bedrock API failed: {e}")

    async def run_llm(self, messages: List[Dict[str, str]]) -> str:
        # Dynamic check of self.provider in case env changes during runtime
        provider = settings.LLM_PROVIDER
        if provider == "bedrock":
            return await self.call_bedrock(messages)
        elif provider == "openai":
            return await self.call_openai(messages)
        elif provider == "gemini":
            return await self.call_gemini(messages)
        else:
            return await self.call_ollama(messages)

    async def generate_response(self, query: str, history: List[Dict[str, str]] = None) -> str:
        if history is None:
            history = []

        # 1. Search RAG context
        context_chunks = rag_service.search(query, limit=4)
        context_str = ""
        for chunk in context_chunks:
            context_str += f"Source: {chunk['source']} ({chunk['url']})\nTitle: {chunk['title']}\nContent: {chunk['content']}\n---\n"

        # 2. Build system prompt
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys_prompt = SYSTEM_PROMPT.format(current_time=now_str)
        sys_prompt += f"\n\nHere is relevant RAG Context about Piyush:\n{context_str}\n"

        # 3. Setup conversation messages
        messages = [{"role": "system", "content": sys_prompt}]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": query})

        # 4. Agent Loop for Tool Executions (max 3 turns to prevent loops)
        for turn in range(3):
            print(f"LLM Turn {turn + 1}...")
            response_text = await self.run_llm(messages)
            print(f"LLM Output: {response_text.strip()}")

            # Check if there is a tool call in response
            # Format: [TOOL_CALL: check_availability()]
            # Format: [TOOL_CALL: book_meeting(name="Name", email="email@email.com", start_time="...", end_time="...")]
            tool_match = re.search(r'\[TOOL_CALL:\s*(\w+)\((.*?)\)\]', response_text)
            if not tool_match:
                # No tool call, return final answer
                return response_text

            tool_name = tool_match.group(1)
            tool_args_str = tool_match.group(2)
            
            # Execute tool
            tool_result = ""
            if tool_name == "check_availability":
                slots = calendar_service.get_available_slots()
                if slots:
                    tool_result = "Here are the available slots:\n"
                    for idx, s in enumerate(slots):
                        tool_result += f"{idx + 1}. {s['formatted']} (Start: {s['start']}, End: {s['end']})\n"
                else:
                    tool_result = "No slots are currently available on the calendar."
            
            elif tool_name == "book_meeting":
                # Parse args
                args = {}
                # Extract args using regex name="val" or email="val"
                for pair in re.finditer(r'(\w+)\s*=\s*["\'](.*?)["\']', tool_args_str):
                    args[pair.group(1)] = pair.group(2)
                
                name = args.get("name", "")
                email = args.get("email", "")
                start = args.get("start_time", "")
                end = args.get("end_time", "")
                
                if name and email and start and end:
                    res = await calendar_service.book_meeting(name, email, start, end)
                    if res["success"]:
                        tool_result = f"SUCCESS! Meeting booked for {name} ({email}) on {res['formatted_time']}. Booking ID: {res['booking_id']}."
                    else:
                        tool_result = "Booking failed due to an internal error."
                else:
                    tool_result = "Booking failed: Missing name, email, start_time, or end_time in argument parameters."

            print(f"Tool Result: {tool_result}")
            
            # Add assistant's tool request and tool outcome to messages
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"SYSTEM TOOL OUTPUT:\n{tool_result}\nNow present this result to the user naturally."})

        # Return final fallback
        return response_text

# Global LLM Service
llm_service = LLMService()
