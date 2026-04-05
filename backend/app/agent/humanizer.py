# Divide resposta em blocos naturais
import re
import random

_MAX_BLOCKS = 3
_MIN_DELAY = 1.0   # segundos
_MAX_DELAY = 4.0   # segundos
_CHARS_PER_SEC_MIN = 30
_CHARS_PER_SEC_MAX = 60


def split_response(text: str) -> list[str]:
    """
    Divide o texto em até 3 blocos naturais para simular envio humano.

    Estratégia (ordem de prioridade):
      1. Parágrafos (linha dupla)
      2. Frases (. ! ?)
      3. Texto inteiro como bloco único
    """
    text = text.strip()
    if not text:
        return []

    # Tenta dividir por parágrafos primeiro
    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]

    if len(blocks) == 1:
        # Sem parágrafos — divide por sentenças
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        blocks = _merge_into_chunks(sentences, _MAX_BLOCKS)

    # Garante no máximo MAX_BLOCKS
    if len(blocks) > _MAX_BLOCKS:
        # Mescla os excedentes no último bloco
        head = blocks[: _MAX_BLOCKS - 1]
        tail = " ".join(blocks[_MAX_BLOCKS - 1 :])
        blocks = head + [tail]

    return blocks


def add_delay(messages: list[str]) -> list[tuple[str, float]]:
    """
    Retorna [(mensagem, delay_antes_de_enviar_em_segundos), ...].
    O primeiro item tem delay 0 (envio imediato).
    Os seguintes simulam tempo de digitação proporcional ao tamanho.
    """
    result: list[tuple[str, float]] = []
    for i, msg in enumerate(messages):
        if i == 0:
            delay = 0.0
        else:
            chars_per_sec = random.uniform(_CHARS_PER_SEC_MIN, _CHARS_PER_SEC_MAX)
            delay = len(msg) / chars_per_sec
            delay = max(_MIN_DELAY, min(_MAX_DELAY, delay))
        result.append((msg, round(delay, 2)))
    return result


def _merge_into_chunks(sentences: list[str], max_chunks: int) -> list[str]:
    """Distribui sentenças em grupos equilibrados."""
    if not sentences:
        return []
    if len(sentences) <= max_chunks:
        return sentences

    # Divide em max_chunks grupos de tamanho aproximadamente igual
    size = len(sentences) / max_chunks
    chunks: list[str] = []
    for i in range(max_chunks):
        start = round(i * size)
        end = round((i + 1) * size)
        chunk = " ".join(sentences[start:end])
        if chunk:
            chunks.append(chunk)
    return chunks
