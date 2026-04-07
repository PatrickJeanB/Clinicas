#!/usr/bin/env python3
"""Ingere informações da Clínica Bem Estar na base de conhecimento RAG."""
import asyncio
import sys
from pathlib import Path

# Coloca backend/ no path para que os imports de app.* funcionem
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.ingestor import ingest_text  # noqa: E402

CLINIC_INFO = """\
Clínica Bem Estar

Especialidade: Psicologia

Horário de Funcionamento:
Segunda a Sexta, das 8h às 18h.
Não atendemos aos finais de semana.

Endereço:
Rua das Flores, 123, Cuiabá-MT

Planos de Saúde Aceitos:
- Unimed
- Bradesco Saúde
- Particular

Consulta Particular:
Valor: R$ 150,00
Duração: 50 minutos
"""


async def main() -> None:
    print("Ingerindo informações da Clínica Bem Estar...")
    doc = await ingest_text(title="Clínica Bem Estar", content=CLINIC_INFO)
    print(f"Concluído! Primeiro chunk ID: {doc['id']}")


if __name__ == "__main__":
    asyncio.run(main())
