import os

from openai import AuthenticationError, OpenAI


client = OpenAI(timeout=30, max_retries=1)
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1024


def generate_text(prompt):
    try:
        return client.responses.create(model=CHAT_MODEL, input=prompt).output_text
    except AuthenticationError:
        raise ValueError("OPENAI_API_KEY không hợp lệ. Kiểm tra khóa trong .env và khởi động lại ứng dụng.") from None


def embed_texts(texts):
    if isinstance(texts, str):
        texts = [texts]
    if not texts:
        return []
    vectors = []
    for start in range(0, len(texts), 50):
        batch = texts[start:start + 50]
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL, input=batch, dimensions=VECTOR_SIZE
            )
        except AuthenticationError:
            raise ValueError("OPENAI_API_KEY không hợp lệ. Kiểm tra khóa trong .env và khởi động lại ứng dụng.") from None
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda item: item.index))
    return vectors
