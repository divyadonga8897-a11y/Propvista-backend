import os
import json
import logging
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("app.ai_service")

class GroqService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def get_chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Call Groq API using HTTP client and return JSON response or text reply."""
        if not self.api_key:
            logger.error("GROQ_API_KEY is not configured in environment variables.")
            return {"reply": "Groq API key is not configured. Please set GROQ_API_KEY in backend .env file.", "tokens": 0}
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        if response_format:
            payload["response_format"] = response_format

        try:
            # Increased timeout to 10.0s since LLM responses from Groq typically take longer than 1.0s
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Groq API error status={response.status_code} body={response.text}")
                    return {"reply": f"Groq API returned an error: {response.text}", "tokens": 0}
                
                res_data = response.json()
                reply = res_data["choices"][0]["message"]["content"]
                tokens = res_data.get("usage", {}).get("total_tokens", 0)
                return {"reply": reply, "tokens": tokens}
        except Exception as e:
            logger.exception("Exception occurred during Groq chat completion call.")
            return {"reply": f"An error occurred connecting to Groq AI: {str(e)}", "tokens": 0}

groq_service = GroqService()
