FROM python:3.11-slim

# Instalar dependências essenciais de teste
RUN pip install --no-cache-dir pytest==8.3.2

# Criar usuário não-root seguro
RUN useradd -m -s /bin/bash sandboxuser
WORKDIR /sandbox
USER sandboxuser