FROM python:3.12-slim

# Version-Info wird beim Build eingebrannt (optional)
ARG GIT_COMMIT=""
ARG GIT_DATE=""
ARG GIT_MESSAGE=""
ENV GIT_COMMIT=$GIT_COMMIT \
    GIT_DATE=$GIT_DATE \
    GIT_MESSAGE=$GIT_MESSAGE

# System-Abhängigkeiten für lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Abhängigkeiten zuerst (besseres Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code
COPY . .

# Daten-Volume (SQLite-DB, Facebook-Session)
VOLUME ["/data"]

EXPOSE 5000

# Gunicorn als WSGI-Server (stabiler als Flask-Dev-Server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "run:app"]
