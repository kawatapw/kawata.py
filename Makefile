#!/usr/bin/env make

build:
	if [ -d ".dbdata" ]; then sudo chmod -R 755 .dbdata; fi
	docker build -t bancho:latest .

run:
	docker compose up bancho mysql redis

run-bg:
	docker compose up -d bancho mysql redis

run-cfd:
	docker compose -f docker-compose.cloudflared.yml up

run-cfd-bg:
	docker compose -f docker-compose.cloudflared.yml up -d

run-caddy:
	caddy run --envfile .env --config ext/Caddyfile

last?=1
logs:
	docker compose logs -f bancho mysql redis --tail ${last}

shell:
	uv run python

test:
	@bash -c 'set -e; trap "docker compose -f docker-compose.test.yml down --volumes --remove-orphans" EXIT; \
	docker compose -f docker-compose.test.yml up -d bancho-test mysql-test redis-test; \
	docker compose -f docker-compose.test.yml exec -T bancho-test /srv/root/scripts/run-tests.sh'

# Run ruff linter (read-only; use `make format` for autofix)
lint:
	uv run ruff check .

# Format code with black and ruff
format:
	uv run black .
	uv run ruff check . --fix

# Check formatting without modifying
format-check:
	uv run black . --check
	uv run ruff check .

# Run ty type checker (primary)
type-check:
	uv run ty check . --exclude .venv --exclude tools --exclude tests

# Run mypy type checker (fallback)
type-check2:
	uv run mypy .

# Run pyright type checker (alternative)
type-check3:
	uv run pyright .

# Run bandit security scanner
security-check:
	uv run bandit -r . -ll --exclude ".venv,venv,tests,testing,migrations,tools,__pycache__"

install:
	uv sync --all-extras --dev

uninstall:
	# uv doesn't have a direct uninstall command, but you can remove the virtual environment
	rm -rf .venv

# To bump the version number run `make bump version=<major/minor/patch>`
# (DO NOT USE IF YOU DON'T KNOW WHAT YOU'RE DOING)
# https://python-poetry.org/docs/cli/#version
bump:
	uv run bump2version $(version)
