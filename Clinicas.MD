Crie um projeto com a seguinte estrutura EXATA de arquivos e pastas. Crie todos os arquivos com o comentário indicado dentro de cada um:

backend/
  app/
    api/
      __init__.py
      webhook.py        # POST /webhook - recebe mensagens WhatsApp
      doctor.py         # Rotas do painel da Dra
      health.py         # GET /health
    services/
      __init__.py
      appointment_service.py   # Regras de negócio de agendamento
      patient_service.py       # Regras de negócio de paciente
      notification_service.py  # Envio de mensagens
      calendar_service.py      # Coordena Supabase + Google Calendar
    repositories/
      __init__.py
      patient_repo.py
      appointment_repo.py
      message_repo.py
      blocked_date_repo.py
    agent/
      __init__.py
      karen.py              # Agente principal - loop Claude API + tools
      context_builder.py    # Monta contexto por mensagem
      llm_router.py         # Roteia modelo por tarefa OpenRouter
      prompts.py            # System prompt dinâmico
      humanizer.py          # Divide resposta em blocos naturais
      buffer.py             # Buffer de 8 segundos com Redis
      skills/
        __init__.py
        base.py             # Classe base para todas as skills
        attendance.py       # Cadastro e atendimento
        scheduling.py       # Agendamento e horários
        confirmation.py     # Confirmação, cancelamento, notificação
        post_care.py        # Pós-consulta e feedback
        doctor_tools.py     # Ferramentas exclusivas da Dra
        knowledge.py        # Busca RAG - informações da clínica
    rag/
      __init__.py
      ingestor.py      # Processa documentos e gera embeddings
      retriever.py     # Busca por similaridade no Supabase
    gateway/
      __init__.py
      whatsapp.py      # Meta Cloud API - envio e parse de mensagens
      gcal.py          # Google Calendar Service Account
      media.py         # Whisper audio + Claude Vision imagem + PDF
    scheduler/
      __init__.py
      jobs.py          # APScheduler - todos os jobs automáticos
    core/
      __init__.py
      settings.py      # Pydantic Settings - variáveis de ambiente
      logging.py       # Loguru configurado
      exceptions.py    # Exceções do domínio
      dependencies.py  # FastAPI Depends() centralizados
    main.py            # Entrypoint FastAPI
  tests/
    integration/
      test_appointment_service.py
    prompts/
      test_scenarios.py
  requirements.txt     # Com todas as dependências do projeto
  .env.example         # Com todas as variáveis necessárias
  .gitignore           # Incluindo .env e credentials.json
  Dockerfile

frontend/
  (deixar vazio por enquanto)