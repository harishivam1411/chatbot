from openai import OpenAI

from app.core.config import settings
from app.models.schemas import ChatData
from app.services.sql_service import SqlService
from app.services.chat_manager_service import ChatManage
from app.services.admission_service import AdmissionProcessor

class LLMService:
    def __init__(self):
        """Initialize the OpenAI client"""
        self.client = OpenAI(base_url=settings.BASE_URL, api_key=settings.OPENROUTER_API_KEY)
        self.model = settings.MODEL
        self.admission_processor = AdmissionProcessor()
        self.chat_manager = ChatManage()
        self.sql_service = SqlService()
        self.response_data = {
            "activate_processor": False,
            "conversational_response": ""
        }

    async def get_response(self, chat_data: ChatData, admission_status: str, chromadb_context: str) -> str:
        try:
            query = chat_data.query.strip()

            system_prompt = self.chat_manager.get_response_prompt(query, chromadb_context, admission_status)
            print(f"[MODEL] AI Assistant")

            self.chat_manager.add_user_message(query)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {"role": "user", "content": query}
            ],
                max_tokens=1000,
                temperature=0.2,
            )

            if response and response.choices and len(response.choices) > 0:
                ai_response = response.choices[0].message.content

                if ai_response == "start_admission":
                    self.response_data["activate_processor"] = True
                    self.response_data["conversational_response"] = ai_response
                    return self.response_data
                
                self.chat_manager.add_bot_message(ai_response)

                print(f"[LLM] Response received: {ai_response}")
                self.response_data["conversational_response"] = ai_response
                return self.response_data
            
            else:
                print("[ERROR] Invalid response structure from API")
                self.response_data["conversational_response"] = "I apologize, but I couldn't generate a response. Please try again."
                return self.response_data

        except Exception as e:
            print(f"[ERROR] Error in get_response: {str(e)}")
            self.response_data["conversational_response"] = "I apologize, but I encountered an error while processing your request. Please try again."
            return self.response_data