from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.settings import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.answer_service import build_answer, is_model_failure_uncertainty
from app.services.chat_client import OpenAIChatClient
from app.services.embedder import MissingEmbeddingDependencyError, SentenceTransformerEmbedder
from app.services.retriever import Retriever
from app.services.vector_index import VECTOR_MAP_FILENAME
from app.services.vector_store import FAISS_INDEX_FILENAME, MissingVectorStoreDependencyError


KEYWORD_DB_FILENAME = "retrieval.db"
INDEX_NOT_READY_DETAIL = "尚未完成建库"

router = APIRouter(
    prefix="/api",
    tags=["chat"],
    responses={
        502: {"description": "模型调用失败"},
        503: {"description": "索引未完成或检索后端不可用"},
    },
)


RetrieverFactory = Callable[..., Retriever]
ChatClientFactory = Callable[..., OpenAIChatClient]


async def get_retriever(settings: Annotated[Settings, Depends(get_settings)]) -> Retriever:
    keyword_db_path = settings.index_dir / KEYWORD_DB_FILENAME
    vector_index_path = settings.index_dir / FAISS_INDEX_FILENAME
    vector_map_path = settings.index_dir / VECTOR_MAP_FILENAME
    _ensure_index_files_exist([keyword_db_path, vector_index_path, vector_map_path])

    if not settings.embedding_model_name or settings.embedding_model_name == "replace-me":
        raise HTTPException(status_code=503, detail="未配置 EMBEDDING_MODEL_NAME，无法执行在线检索。")

    return _build_retriever(
        keyword_db_path=keyword_db_path,
        vector_index_path=vector_index_path,
        vector_map_path=vector_map_path,
        embedding_model_name=settings.embedding_model_name,
        embedding_device=settings.embedding_device,
        embedding_batch_size=settings.embedding_batch_size,
        embedding_max_seq_length=settings.embedding_max_seq_length,
    )


async def get_chat_client(settings: Annotated[Settings, Depends(get_settings)]) -> OpenAIChatClient:
    return _build_chat_client(
        api_key=settings.chat_api_key,
        base_url=settings.chat_base_url,
        model=settings.chat_model,
        timeout=settings.chat_timeout_seconds,
        temperature=settings.chat_temperature,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    retriever: Annotated[Retriever, Depends(get_retriever)],
    client: Annotated[OpenAIChatClient, Depends(get_chat_client)],
) -> ChatResponse:
    try:
        evidence = retriever.search(payload.message, top_k=payload.top_k)
    except (MissingEmbeddingDependencyError, MissingVectorStoreDependencyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = build_answer(evidence, client=client, question=payload.message)
    if is_model_failure_uncertainty(result["uncertainty"]):
        raise HTTPException(status_code=502, detail=result["uncertainty"])

    return ChatResponse.model_validate(result)


def _ensure_index_files_exist(paths: list[Path]) -> None:
    if all(path.exists() for path in paths):
        return
    raise HTTPException(status_code=503, detail=INDEX_NOT_READY_DETAIL)


@lru_cache
def _build_retriever(
    *,
    keyword_db_path: Path,
    vector_index_path: Path,
    vector_map_path: Path,
    embedding_model_name: str,
    embedding_device: str,
    embedding_batch_size: int,
    embedding_max_seq_length: int | None,
    retriever_factory: RetrieverFactory = Retriever.from_disk,
) -> Retriever:
    embedder = SentenceTransformerEmbedder(
        model_name_or_path=embedding_model_name,
        device=embedding_device,
        batch_size=embedding_batch_size,
        max_seq_length=embedding_max_seq_length,
    )
    # Warm the embedder before loading FAISS. In the current fire environment,
    # loading the FAISS index first can trigger a native crash on the first query encode.
    _prime_embedder(embedder)
    return retriever_factory(
        keyword_db_path=keyword_db_path,
        vector_index_path=vector_index_path,
        vector_map_path=vector_map_path,
        embedder=embedder,
    )


@lru_cache
def _build_chat_client(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
    temperature: float,
    chat_client_factory: ChatClientFactory = OpenAIChatClient,
) -> OpenAIChatClient:
    return chat_client_factory(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        temperature=temperature,
    )


def _prime_embedder(embedder: SentenceTransformerEmbedder) -> None:
    embedder.encode_queries(["warmup"])
