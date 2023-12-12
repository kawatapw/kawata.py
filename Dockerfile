FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install --no-install-recommends -y \
    git curl build-essential=12.9 \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock ./
RUN pip install -U pip poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-root

RUN apt update && \
    apt install -y default-mysql-client redis-tools

# Copy Nginx configuration file
#COPY nginx.conf /etc/nginx/nginx.conf

# Copy your service files to the appropriate location
COPY . .

ENTRYPOINT [ "scripts/start_server.sh" ]
