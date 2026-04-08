# Processa documentos e gera embeddings
from __future__ import annotations

import asyncio
import pathlib
from typing import TypedDict

from app.agent.llm_router import llm_router
from app.core.dependencies import get_supabase
from app.core.logging import logger


class Document(TypedDict):
    id: str
    title: str
    content: str
    chunk_index: int
    created_at: str


def _chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """Divide o texto em chunks de `size` chars com sobreposição de `overlap`."""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


async def ingest_text(title: str, content: str, clinic_id: str) -> Document:
    """
    Divide o conteúdo em chunks, gera embeddings e salva na tabela `documents`.
    Retorna o primeiro Document criado.
    """
    chunks = _chunk_text(content)
    if not chunks:
        raise ValueError("Conteúdo vazio — nada a ingerir.")

    supabase = await get_supabase()

    # Gera todos os embeddings em paralelo
    embeddings = await asyncio.gather(*[llm_router.embed(chunk) for chunk in chunks])

    first_doc: Document | None = None

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        result = await (
            supabase.table("documents")
            .insert(
                {
                    "clinic_id": clinic_id,
                    "title": title,
                    "content": chunk,
                    "chunk_index": idx,
                    "embedding": embedding,
                }
            )
            .execute()
        )
        row = result.data[0]
        doc: Document = {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "chunk_index": row["chunk_index"],
            "created_at": row["created_at"],
        }
        if first_doc is None:
            first_doc = doc
        logger.info(f"[RAG] ingerido chunk {idx + 1}/{len(chunks)} — {title!r}")

    return first_doc  # type: ignore[return-value]


async def ingest_file(file_path: str, clinic_id: str) -> list[Document]:
    """
    Lê um arquivo .txt ou .pdf e ingere todos os chunks.
    Retorna a lista de Documents criados.
    """
    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".txt":
        content = path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        content = _read_pdf(path)
    else:
        raise ValueError(f"Formato não suportado: {suffix!r}. Use .txt ou .pdf")

    title = path.stem
    chunks = _chunk_text(content)
    if not chunks:
        raise ValueError(f"Arquivo vazio: {file_path}")

    supabase = await get_supabase()

    # Gera todos os embeddings em paralelo
    embeddings = await asyncio.gather(*[llm_router.embed(chunk) for chunk in chunks])

    docs: list[Document] = []

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        result = await (
            supabase.table("documents")
            .insert(
                {
                    "clinic_id": clinic_id,
                    "title": title,
                    "content": chunk,
                    "chunk_index": idx,
                    "embedding": embedding,
                }
            )
            .execute()
        )
        row = result.data[0]
        docs.append(
            {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "created_at": row["created_at"],
            }
        )
        logger.info(f"[RAG] ingerido chunk {idx + 1}/{len(chunks)} — {title!r}")

    return docs


def _read_pdf(path: pathlib.Path) -> str:
    """Extrai texto de um PDF usando pypdf."""
    try:
        import pypdf  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Instale 'pypdf' para suporte a PDF: pip install pypdf"
        ) from exc

    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
