from openai import OpenAI
from app.core.config import settings

# Correct way with new SDK
_client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_reply(message: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": message})

    resp = _client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.6,
        max_tokens=256,
    )
    return resp.choices[0].message.content.strip()

async def embed_text(text: str) -> list[float]:
    emb = _client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text
    )
    return emb.data[0].embedding
