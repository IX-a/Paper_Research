import time
from openai import OpenAI, RateLimitError, APIError, AuthenticationError

from prompts import SUMMARIZE_PROMPT

MAX_TEXT_CHARS = 60000


def summarize(full_text: str, api_key: str, article_title: str = "", model: str = "deepseek-v4-flash", max_retries: int = 3) -> str:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    text = _truncate_text(full_text)
    messages = [{"role": "user", "content": SUMMARIZE_PROMPT.format(
        full_text=text, article_title=article_title or "未提供"
    )}]

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except RateLimitError:
            time.sleep(2**attempt)
            last_error = "DeepSeek API rate limited. All retries exhausted."
        except APIError as e:
            if e.status_code is not None and e.status_code >= 500:
                time.sleep(2**attempt)
                last_error = f"DeepSeek server error: {e}"
            else:
                raise
        except AuthenticationError:
            raise RuntimeError("DeepSeek API key is invalid.")

    raise RuntimeError(last_error or "DeepSeek API call failed after retries.")


def _truncate_text(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[文章已截断至60000字符]"
