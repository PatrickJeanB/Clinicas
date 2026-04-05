class KarenException(Exception):
    """Exceção base do domínio Karen."""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class PatientNotFoundError(KarenException):
    """Paciente não encontrado no banco de dados."""

    def __init__(self, identifier: str) -> None:
        super().__init__(
            message=f"Paciente não encontrado: {identifier}",
            code="PATIENT_NOT_FOUND",
        )


class AppointmentConflictError(KarenException):
    """Conflito de horário no agendamento."""

    def __init__(self, datetime_str: str) -> None:
        super().__init__(
            message=f"Já existe um agendamento no horário: {datetime_str}",
            code="APPOINTMENT_CONFLICT",
        )


class WhatsAppError(KarenException):
    """Erro na comunicação com a Meta Cloud API."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="WHATSAPP_ERROR")


class CalendarError(KarenException):
    """Erro na comunicação com o Google Calendar."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CALENDAR_ERROR")
