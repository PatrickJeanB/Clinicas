# System prompt dinâmico
from datetime import datetime
from zoneinfo import ZoneInfo

_BR_TZ = ZoneInfo("America/Sao_Paulo")

_WEEKDAYS_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}

_WEEKDAY_LABELS: dict[str, str] = {
    "monday":    "segunda-feira",
    "tuesday":   "terça-feira",
    "wednesday": "quarta-feira",
    "thursday":  "quinta-feira",
    "friday":    "sexta-feira",
    "saturday":  "sábado",
    "sunday":    "domingo",
}


def system_prompt(
    patient: dict | None,
    upcoming_appointments: list[dict],
    ai_name: str = "Assistente",
    clinic_info: dict | None = None,
    clinic_settings: dict | None = None,
) -> str:
    now = datetime.now(_BR_TZ)
    weekday = _WEEKDAYS_PT[now.weekday()]
    date_str = now.strftime(f"{weekday}, %d/%m/%Y")
    time_str = now.strftime("%H:%M")

    patient_block = _build_patient_block(patient)
    appointments_block = _build_appointments_block(upcoming_appointments)
    clinic_block = _build_clinic_block(clinic_info)
    schedule_block = _build_schedule_block(clinic_settings)

    return f"""Você é {ai_name}, a secretária virtual da clínica de psicologia. Você atende exclusivamente pelo WhatsApp.

## Identidade
- Seu nome é {ai_name}
- Você é profissional, acolhedora e objetiva
- Fala sempre em português brasileiro
- Usa linguagem simples, sem jargões técnicos
- Nunca menciona que é uma IA ou robô — você é a secretária

## Limites importantes
- Você NÃO dá diagnósticos psicológicos
- Você NÃO oferece aconselhamento terapêutico
- Você NÃO substitui a psicóloga em nenhuma hipótese
- Para questões clínicas, sempre oriente o paciente a falar diretamente com a Dra. na consulta
- Em casos de crise ou emergência, oriente a ligar para o CVV (188) ou SAMU (192)

## Suas responsabilidades
- Agendar, remarcar e cancelar consultas
- Informar horários disponíveis
- Confirmar consultas agendadas
- Responder dúvidas sobre a clínica (localização, valores, formas de pagamento)
- Enviar lembretes e confirmações

{schedule_block}

{clinic_block}

## Data e hora atual
- {date_str}, {time_str}

{patient_block}

{appointments_block}

## Instruções de comportamento
- Responda de forma concisa — máximo 3 parágrafos por mensagem
- Confirme sempre os dados antes de agendar (data, horário, nome)
- Se o horário solicitado não estiver disponível, ofereça até 3 alternativas
- Após agendar, envie um resumo claro: data, hora e nome do paciente
- Não invente informações — se não souber, diga que vai verificar
- Evite emojis em excesso — use com moderação quando apropriado"""


def _build_patient_block(patient: dict | None) -> str:
    if not patient:
        return "## Paciente\n- Paciente ainda não cadastrado no sistema\n- Solicite o nome completo para cadastro"

    name = patient.get("name", "")
    notes = patient.get("notes", "")

    block = f"## Paciente\n- Nome: {name}"
    if notes:
        block += f"\n- Observações: {notes}"
    return block


def _build_appointments_block(appointments: list[dict]) -> str:
    if not appointments:
        return "## Próximas consultas\n- Nenhuma consulta agendada"

    _BR_TZ_local = ZoneInfo("America/Sao_Paulo")
    lines = ["## Próximas consultas"]
    for appt in appointments[:5]:  # Mostra no máximo 5
        try:
            dt = datetime.fromisoformat(appt["datetime"]).astimezone(_BR_TZ_local)
            weekday = _WEEKDAYS_PT[dt.weekday()]
            formatted = dt.strftime(f"{weekday}, %d/%m/%Y às %H:%M")
        except (ValueError, KeyError):
            formatted = appt.get("datetime", "data inválida")

        status = appt.get("status", "")
        status_label = {"scheduled": "agendada", "confirmed": "confirmada"}.get(status, status)
        lines.append(f"- {formatted} ({status_label})")

    return "\n".join(lines)


def _build_schedule_block(clinic_settings: dict | None) -> str:
    if not clinic_settings:
        return (
            "## Horário de funcionamento\n"
            "- Segunda a sexta: 8h às 18h\n"
            "- Sábado e domingo: fechado\n"
            "- Consultas com duração de 50 minutos\n"
            "- Intervalo de 10 minutos entre consultas"
        )

    working_days: list[str] = clinic_settings.get("working_days") or []
    working_start: str = clinic_settings.get("working_start") or "08:00"
    working_end: str = clinic_settings.get("working_end") or "18:00"
    duration: int = clinic_settings.get("appointment_duration") or 50

    if working_days:
        days_pt = [_WEEKDAY_LABELS.get(d, d) for d in working_days]
        days_str = ", ".join(days_pt[:-1]) + (" e " + days_pt[-1] if len(days_pt) > 1 else days_pt[0])
    else:
        days_str = "segunda a sexta"

    return (
        "## Horário de funcionamento\n"
        f"- Dias de atendimento: {days_str}\n"
        f"- Horário: {working_start} às {working_end}\n"
        f"- Consultas com duração de {duration} minutos\n"
        "- Intervalo de 10 minutos entre consultas"
    )


def _build_clinic_block(clinic_info: dict | None) -> str:
    if not clinic_info:
        return ""

    lines = ["## Informações da clínica"]
    for key, value in clinic_info.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)
