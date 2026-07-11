import json
import logging
from openai import AsyncOpenAI
from src.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.gonkagate_api_key,
            base_url=settings.gonkagate_base_url
        )
        self.model = settings.llm_model

    async def generate_questions(self, topic: str, count: int = 5) -> list[dict] | None:
        """
        Generates structured questions on a topic in JSON format.
        Each question has:
        - question_text (str)
        - options (list of 4 strings)
        - correct_option_index (int, 0-3)
        - explanation (str)
        """
        system_prompt = (
            "You are a professional quiz generator. Generate a quiz containing multiple-choice questions "
            "based on the topic provided by the user. You MUST respond ONLY with a raw JSON array of objects. "
            "Do not include any markdown formatting like ```json or ```, just the JSON string.\n"
            "Each object in the array must contain the following fields exactly:\n"
            "- \"question_text\": a string, the text of the question.\n"
            "- \"options\": a list of exactly 4 strings representing the answer choices.\n"
            "- \"correct_option_index\": an integer (0, 1, 2, or 3) representing the index of the correct answer in the options list.\n"
            "- \"explanation\": a string explaining why the answer is correct.\n\n"
            "Ensure the questions are interesting, clear, and written in Russian."
        )

        user_prompt = f"Generate {count} questions for the topic: \"{topic}\"."

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
            )
            content = response.choices[0].message.content.strip()
            
            # Clean possible markdown wrapping
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            questions = json.loads(content)
            if not isinstance(questions, list):
                logger.error(f"LLM returned invalid format (not a list): {content}")
                return None
                
            # Basic validation
            validated_questions = []
            for q in questions:
                if (
                    isinstance(q, dict)
                    and "question_text" in q
                    and "options" in q
                    and "correct_option_index" in q
                    and isinstance(q["options"], list)
                    and len(q["options"]) == 4
                    and isinstance(q["correct_option_index"], int)
                    and 0 <= q["correct_option_index"] < 4
                ):
                    validated_questions.append(q)
                    
            if not validated_questions:
                logger.error(f"No valid questions parsed from LLM response: {content}")
                return None
                
            return validated_questions
            
        except Exception as e:
            logger.error(f"Error generating questions from LLM: {e}")
            return None
