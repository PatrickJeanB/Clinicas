#!/bin/bash
# ════════════════════════════════════════════════════════
#  Karen — Script de inicialização do backend
# ════════════════════════════════════════════════════════
set -e

# Carrega variáveis do .env (ignora comentários e linhas vazias)
if [ -f .env ]; then
    export $(grep -v '^\s*#' .env | grep -v '^\s*$' | xargs)
    echo "✓ .env carregado"
else
    echo "⚠ Arquivo .env não encontrado — usando variáveis do ambiente"
fi

# Instala dependências
echo "→ Instalando dependências..."
pip install -r requirements.txt --quiet

# Cria pasta de logs
mkdir -p logs
echo "✓ Pasta logs/ pronta"

# Porta padrão caso APP_PORT não esteja definida
PORT="${APP_PORT:-8000}"

echo "→ Iniciando Karen na porta $PORT..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --reload \
    --log-level warning
