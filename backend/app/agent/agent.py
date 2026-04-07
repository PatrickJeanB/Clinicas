# Agente principal - loop Claude API + tools
import asyncio
import json
from typing import Any

from app.agent.buffer import message_buffer
from app.agent.context_builder import context_builder
from app.agent.humanizer import add_delay, split_response
from app.agent.llm_router import llm_router
from app.agent.prompts import system_prompt
from app.core.exceptions import AppointmentConflictError, PatientNotFoundError
from app.core.logging import logger
from app.gateway.whatsapp import whatsapp_gateway
from app.repositories.message_repo import message_repo
from app.services.appointment_service import appointment_service
from app.services.patient_service import patient_service

_MAX_TOOL_ROUNDS = 5  # evita loop infinito de tools

# ------------------------------------------------------------------
# Definição das ferramentas (formato OpenAI function calling)
# ------------------------------------------------------------------

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Verifica se um horário está disponível para agendamento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {
                        "type": "string",
                        "description": "Data e hora no formato 'YYYY-MM-DD HH:MM'",
                    }
                },
                "required": ["datetime_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Agenda uma consulta para o paciente atual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {
                        "type": "string",
                        "description": "Data e hora no formato 'YYYY-MM-DD HH:MM'",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Observações opcionais sobre a consulta",
                    },
                },
                "required": ["datetime_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Remarca uma consulta existente para outro horário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "ID da consulta a remarcar",
                    },
                    "new_datetime_str": {
                        "type": "string",
                        "description": "Novo horário no formato 'YYYY-MM-DD HH:MM'",
                    },
                },
                "required": ["appointment_id", "new_datetime_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancela uma consulta agendada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "ID da consulta a cancelar",
                    }
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_upcoming_appointments",
            "description": "Lista as próximas consultas agendadas do paciente.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_patient",
            "description": "Cadastra um novo paciente no sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nome completo do paciente",
                    },
                    "email": {
                        "type": "string",
                        "description": "E-mail do paciente (opcional)",
                    },
                },
                "required": ["name"],
            },
        },
    },
]


# ------------------------------------------------------------------
# Agente principal
# ------------------------------------------------------------------


class ClinicAgent:
    async def process(self, phone: str, messages: list[dict]) -> None:
        """
        Ponto de entrada chamado pelo MessageBuffer.
        messages: lista de parsed dicts vindos do WhatsApp.
        """
        logger.info(f"[Agent] processando {len(messages)} mensagem(ns) de {phone}")

        # 1. Contexto
        ctx = await context_builder.build(phone)

        # 2. Se paciente novo, tenta extrair nome da primeira mensagem
        patient = ctx["patient"]
        if patient is None:
            name = _extract_name_hint(messages)
            patient, created = await patient_service.get_or_create(phone, name)
            if created:
                logger.info(f"[Agent] novo paciente cadastrado: {phone}")
            ctx["patient"] = patient

        # 3. Salva mensagens inbound no banco
        for msg in messages:
            await _save_inbound(patient["id"], msg)

        # 4. Monta histórico para o LLM
        conversation = _build_conversation(ctx, messages)
        sys_prompt = system_prompt(
            patient=ctx["patient"],
            upcoming_appointments=ctx["upcoming_appointments"],
        )

        # 5. Loop de tool use
        reply_text = await self._agent_loop(sys_prompt, conversation, phone, patient)

        # 6. Humaniza e envia
        if reply_text:
            await self._send_humanized(phone, patient["id"], reply_text)

    # ------------------------------------------------------------------
    # Loop de ferramentas
    # ------------------------------------------------------------------

    async def _agent_loop(
        self,
        sys_prompt: str,
        conversation: list[dict],
        phone: str,
        patient: dict,
    ) -> str:
        messages: list[dict] = [{"role": "system", "content": sys_prompt}] + conversation

        for round_n in range(_MAX_TOOL_ROUNDS):
            result = await llm_router.complete(
                task="respond",
                messages=messages,
                tools=_TOOLS,
            )

            # Resposta final em texto
            if isinstance(result, str):
                logger.debug(f"[Agent] resposta final obtida (round {round_n + 1})")
                return result

            # Tool calls — executa e continua o loop
            tool_result_msgs = await self._execute_tool_calls(
                result["tool_calls"], phone, patient
            )

            # Adiciona a mensagem do assistente com tool_calls
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in result["tool_calls"]
                    ],
                }
            )
            messages.extend(tool_result_msgs)

        logger.warning(f"[Agent] limite de {_MAX_TOOL_ROUNDS} rounds de tools atingido")
        return "Desculpe, tive um problema para processar sua solicitação. Pode repetir?"

    # ------------------------------------------------------------------
    # Execução de ferramentas
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self, tool_calls: list[dict], phone: str, patient: dict
    ) -> list[dict]:
        tasks = [
            self._execute_single_tool(tc["id"], tc["name"], tc["arguments"], phone, patient)
            for tc in tool_calls
        ]
        return await asyncio.gather(*tasks)

    async def _execute_single_tool(
        self,
        call_id: str,
        name: str,
        args: dict,
        phone: str,
        patient: dict,
    ) -> dict:
        logger.info(f"[Agent] tool={name} args={args}")
        try:
            output = await self._dispatch(name, args, phone, patient)
        except (PatientNotFoundError, AppointmentConflictError) as exc:
            output = {"error": exc.message}
        except Exception as exc:
            logger.exception(f"[Agent] erro na tool {name}: {exc}")
            output = {"error": str(exc)}

        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(output, ensure_ascii=False, default=str),
        }

    async def _dispatch(
        self, name: str, args: dict, phone: str, patient: dict
    ) -> Any:
        if name == "check_availability":
            available = await appointment_service.check_availability(args["datetime_str"])
            return {"available": available, "datetime": args["datetime_str"]}

        if name == "book_appointment":
            appt = await appointment_service.book(
                patient_phone=phone,
                datetime_str=args["datetime_str"],
                notes=args.get("notes"),
            )
            return {"success": True, "appointment": appt}

        if name == "reschedule_appointment":
            appt = await appointment_service.reschedule(
                appointment_id=args["appointment_id"],
                new_datetime_str=args["new_datetime_str"],
            )
            return {"success": True, "appointment": appt}

        if name == "cancel_appointment":
            appt = await appointment_service.cancel(args["appointment_id"])
            return {"success": True, "appointment": appt}

        if name == "list_upcoming_appointments":
            appointments = await appointment_service.list_upcoming(phone)
            return {"appointments": appointments}

        if name == "register_patient":
            updated = await patient_service.update_profile(
                phone,
                name=args["name"],
                email=args.get("email"),
            )
            return {"success": True, "patient": updated}

        return {"error": f"Ferramenta desconhecida: {name}"}

    # ------------------------------------------------------------------
    # Envio humanizado
    # ------------------------------------------------------------------

    async def _send_humanized(
        self, phone: str, patient_id: str, text: str
    ) -> None:
        blocks = split_response(text)
        timed = add_delay(blocks)

        for message, delay in timed:
            if delay > 0:
                await asyncio.sleep(delay)
            await whatsapp_gateway.send_text(phone, message)
            await message_repo.save(
                patient_id=patient_id,
                direction="outbound",
                content=message,
                message_type="text",
            )
            logger.debug(f"[Agent] bloco enviado → {phone} ({len(message)} chars)")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_name_hint(messages: list[dict]) -> str:
    """Usa o nome do perfil WhatsApp como hint, se disponível."""
    for msg in messages:
        name = msg.get("from_name", "").strip()
        if name:
            return name
    return "Paciente"


def _build_conversation(ctx: dict, new_messages: list[dict]) -> list[dict]:
    """Monta histórico: mensagens salvas + novas mensagens do buffer."""
    history: list[dict] = []

    for msg in ctx["recent_messages"]:
        role = "user" if msg["direction"] == "inbound" else "assistant"
        history.append({"role": role, "content": msg["content"]})

    for msg in new_messages:
        content = msg.get("content", "")
        if msg.get("message_type") == "audio":
            content = f"[Áudio recebido — ID: {content}]"
        elif msg.get("message_type") == "image":
            content = f"[Imagem recebida — ID: {content}]"
        elif msg.get("message_type") == "document":
            content = f"[Documento recebido — ID: {content}]"

        if content:
            history.append({"role": "user", "content": content})

    return history


async def _save_inbound(patient_id: str, msg: dict) -> None:
    try:
        await message_repo.save(
            patient_id=patient_id,
            direction="inbound",
            content=msg.get("content", ""),
            message_type=msg.get("message_type", "text"),
            whatsapp_message_id=msg.get("message_id"),
        )
    except Exception as exc:
        logger.warning(f"[Agent] falha ao salvar mensagem inbound: {exc}")


# ------------------------------------------------------------------
# Singleton + registro no buffer
# ------------------------------------------------------------------

clinic_agent = ClinicAgent()
message_buffer.set_handler(clinic_agent.process)
