# Busca por similaridade no Supabase
from app.agent.llm_router import llm_router
from app.core.dependencies import get_supabase
from app.core.logging import logger


async def search(query: str, limit: int = 5) -> list[dict]:
    """
    Gera embedding da query e realiza busca por similaridade no Supabase
    via pgvector (função RPC `match_documents`).

    Retorna lista de dicts com: id, title, content, chunk_index, similarity.
    """
    embedding = await llm_router.embed(query)
    supabase = await get_supabase()

    result = await supabase.rpc(
        "match_documents",
        {"query_embedding": embedding, "match_count": limit},
    ).execute()

    docs: list[dict] = result.data or []
    logger.info(f"[RAG] busca {query!r:.50} → {len(docs)} resultado(s)")
    return docs
