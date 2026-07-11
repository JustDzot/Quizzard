import asyncio
import httpx
import json
import logging
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from src.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    _lock = None

    def __init__(self):
        if LLMClient._lock is None:
            LLMClient._lock = asyncio.Lock()
        self.client = AsyncOpenAI(
            api_key=settings.gonkagate_api_key,
            base_url=settings.gonkagate_base_url,
            timeout=120.0,
            max_retries=0
        )
        self.model = settings.llm_model

    async def generate_questions(
        self,
        topic: str,
        difficulty: str = "medium",
        count: int = 5,
        on_chunk = None
    ) -> list[dict] | None:
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

        diff_prompts = {
            "easy": "простой (лёгкий) уровень сложности. Вопросы должны быть базовыми и понятными для новичков.",
            "medium": "средний уровень сложности. Вопросы должны требовать хорошего понимания темы.",
            "hard": "высокий (сложный) уровень сложности. Вопросы должны быть глубокими, детальными и рассчитаны на экспертов."
        }
        diff_desc = diff_prompts.get(difficulty, "средний уровень сложности")
        user_prompt = f"Generate {count} questions for the topic: \"{topic}\". Уровень сложности вопросов: {diff_desc}."

        max_retries = 3
        retry_delay = 5.0
        content = ""

        async with self._lock:
            for attempt in range(max_retries):
                try:
                    if on_chunk:
                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.7,
                            stream=True
                        )
                        collected_chunks = []
                        current_text = ""

                        async def telegram_updater():
                            last_sent_text = ""
                            while True:
                                try:
                                    await asyncio.sleep(1.5)
                                    if current_text == last_sent_text:
                                        continue
                                    last_sent_text = current_text
                                    if last_sent_text:
                                        await on_chunk(last_sent_text)
                                except asyncio.CancelledError:
                                    if current_text != last_sent_text:
                                        try:
                                            await on_chunk(current_text)
                                        except Exception:
                                            pass
                                    break
                                except Exception:
                                    pass

                        updater_task = asyncio.create_task(telegram_updater())
                        try:
                            async def read_stream():
                                nonlocal current_text
                                async for chunk in response:
                                    chunk_text = chunk.choices[0].delta.content or ""
                                    collected_chunks.append(chunk_text)
                                    current_text = "".join(collected_chunks)
                            
                            await asyncio.wait_for(read_stream(), timeout=90.0)
                        finally:
                            updater_task.cancel()
                            await asyncio.gather(updater_task, return_exceptions=True)
                        content = current_text.strip()
                    else:
                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.7,
                        )
                        content = response.choices[0].message.content.strip()
                    
                    break  # Success, exit retry loop
                    
                except (RateLimitError, APITimeoutError, APIConnectionError, httpx.TimeoutException, asyncio.TimeoutError) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Transient LLM API error on final attempt: {e}")
                        return None
                    logger.warning(f"Transient LLM API error: {e}. Retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2.0
                except Exception as e:
                    logger.error(f"Fatal error calling LLM API: {e}")
                    return None

        try:
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
            logger.error(f"Error parsing questions from LLM response: {e}")
            return None
