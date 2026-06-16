from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GeminiLLMClient:
    """Google Gemini LLM via LangChain (free tier available via Google AI Studio)."""

    def __init__(self) -> None:
        self._chat = ChatGoogleGenerativeAI(
            model=settings.gemini_chat_model,
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.google_api_key,
        )

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
        logger.info("gemini_chat_request", model=settings.gemini_chat_model)
        response = await self._chat.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        logger.info("gemini_embed_request", count=len(texts), model=settings.gemini_embedding_model)
        return await self._embeddings.aembed_documents(texts)
