FROM python:3.13-slim

# Empêche Python d'écrire des fichiers .pyc et force les logs non bufferisés
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances système minimales
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copie du projet
COPY . .

# Par défaut, lance le client MCP interactif.
# Le fichier client.py démarre automatiquement server.py en stdio.
CMD ["python", "client.py"]
