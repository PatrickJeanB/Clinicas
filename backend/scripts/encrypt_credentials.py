"""
Criptografa credenciais em texto puro e atualiza no banco.

Uso:
    python -m scripts.encrypt_credentials \
        --clinic-id <UUID> \
        --field whatsapp_app_secret \
        --value <valor_em_texto_puro>

Campos suportados:
    whatsapp_app_secret
    whatsapp_token

O valor NUNCA deve ser passado via variável de ambiente ou hardcoded aqui.
Passe diretamente como argumento — o shell history pode ser limpo depois
com: history -d $(history 1) ou usando um password manager para pipe.
"""
import argparse
import asyncio
import sys

# Garante que o módulo app seja encontrado quando rodado da raiz do projeto
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.encryption import encrypt
from app.core.settings import settings
from supabase._async.client import create_client

_ALLOWED_FIELDS = {"whatsapp_app_secret", "whatsapp_token"}


async def main(clinic_id: str, field: str, value: str) -> None:
    if field not in _ALLOWED_FIELDS:
        print(f"[ERRO] Campo '{field}' não suportado. Use: {', '.join(_ALLOWED_FIELDS)}")
        sys.exit(1)

    if not value.strip():
        print("[ERRO] O valor não pode ser vazio.")
        sys.exit(1)

    encrypted = encrypt(value)

    client = await create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )

    response = (
        await client.table("clinic_settings")
        .update({field: encrypted})
        .eq("clinic_id", clinic_id)
        .execute()
    )

    if not response.data:
        print(f"[ERRO] clinic_id '{clinic_id}' não encontrado ou nenhuma linha atualizada.")
        sys.exit(1)

    # Exibe apenas o prefixo — nunca o valor completo
    print(f"[OK] {field} criptografado e salvo para clinic_id={clinic_id}")
    print(f"     Prefixo do valor cifrado: {encrypted[:20]}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Criptografa credencial e salva no banco.")
    parser.add_argument("--clinic-id", required=True, help="UUID da clínica")
    parser.add_argument(
        "--field",
        required=True,
        choices=list(_ALLOWED_FIELDS),
        help="Campo a atualizar",
    )
    parser.add_argument("--value", required=True, help="Valor em texto puro a criptografar")

    args = parser.parse_args()
    asyncio.run(main(clinic_id=args.clinic_id, field=args.field, value=args.value))
