# Busca RAG - informações da clínica
from app.core.logging import logger
from app.rag import retriever


def get_tools() -> list[dict]:
    """Retorna definições de ferramentas (formato OpenAI) para o agente."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_clinic_info",
                "description": (
                    "Busca informações sobre a clínica na base de conhecimento: "
                    "horários, endereço, planos aceitos, valores de consulta, etc."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Tema ou pergunta a buscar na base de conhecimento",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]


async def search_clinic_info(query: str) -> str:
    """
    Busca informações da clínica via RAG e retorna texto formatado
    para o agente usar na resposta.
    """
    docs = await retriever.search(query, limit=3)

    if not docs:
        logger.warning(f"[Knowledge] nenhum resultado para: {query!r}")
        return "Nenhuma informação encontrada sobre este tema na base de conhecimento."

    parts: list[str] = []
    for doc in docs:
        score = doc.get("similarity", 0)
        parts.append(f"[{doc['title']} — relevância {score:.0%}]\n{doc['content']}")

    return "\n\n---\n\n".join(parts)
