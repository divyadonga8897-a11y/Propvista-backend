import json
import logging
from typing import Dict, Any, List
from app.services.ai.groq_service import groq_service

logger = logging.getLogger("app.prompt_manager")

class PromptManager:
    def get_filter_extraction_prompt(self, user_query: str) -> List[Dict[str, str]]:
        system_instruction = (
            "You are a helpful AI assistant that converts natural language queries looking for flats/apartments "
            "into a structured JSON payload for filtering the database. "
            "Respond ONLY with a valid JSON block containing these fields (or null if not mentioned):\n"
            "- flat_type (string, e.g., '2BHK', '3BHK', 'Studio')\n"
            "- facing_direction (string, e.g., 'East', 'West', 'North', 'South')\n"
            "- max_budget (number/float representing price value in INR)\n"
            "- listing_type (string, either 'RENT' or 'BUY')\n"
            "- has_parking (boolean)\n"
            "- floor_number (integer)\n"
            "Example query: 'I need a 2BHK east-facing flat under 50 lakh for rent.'\n"
            "Output: {\"flat_type\": \"2BHK\", \"facing_direction\": \"East\", \"max_budget\": 5000000, \"listing_type\": \"RENT\", \"has_parking\": null, \"floor_number\": null}\n"
            "Query: " + user_query
        )
        return [
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": system_instruction}
        ]

    def get_resident_assistant_prompt(self, user_query: str, resident_ctx: dict) -> List[Dict[str, str]]:
        system_instruction = (
            f"You are the resident AI assistant for PropVista. You have access to the user's real database records:\n"
            f"{json.dumps(resident_ctx)}\n"
            "Strictly answer the user's questions using ONLY this data. Never hallucinate or make up records. "
            "If the information is not in the context, politely state that you do not have that record in the database."
        )
        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_query}
        ]

    def get_complaint_classifier_prompt(self, description: str) -> List[Dict[str, str]]:
        system_instruction = (
            "Classify the following maintenance issue description into a category, a priority level, "
            "and suggest a short, professional title and a summary.\n"
            "Categories allowed: Plumbing, Electrical, Security, Lift, Cleaning, Parking, Water Supply, Internet, Other.\n"
            "Priority levels allowed: Low, Medium, High.\n"
            "Respond ONLY with a valid JSON block containing: category, priority, title, summary.\n"
            "Issue description: " + description
        )
        return [
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": system_instruction}
        ]

    def get_announcement_generator_prompt(self, topic: str) -> List[Dict[str, str]]:
        system_instruction = (
            "Write a professional society announcement notice based on this topic: " + topic + ".\n"
            "Provide a suitable short title and a detailed notice description/body.\n"
            "Respond ONLY with a valid JSON block containing: title, content, announcement_type (one of: General, Maintenance, Emergency, Event)."
        )
        return [
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": system_instruction}
        ]

    def get_admin_assistant_prompt(self, user_query: str, metrics: dict) -> List[Dict[str, str]]:
        system_instruction = (
            f"You are the PropVista Admin AI Assistant. You have access to these real-time database summary metrics:\n"
            f"{json.dumps(metrics)}\n"
            "Answer the admin's query using tables, summaries, or structured text as appropriate. Do not hallucinate."
        )
        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_query}
        ]

prompt_manager = PromptManager()
