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
	docker compose -f docker-compose.test.yml up -d bancho-test mysql-test redis-test
	docker compose -f docker-compose.test.yml exec -T bancho-test /srv/root/scripts/run-tests.sh

lint:
	uv run pre-commit run --all-files

type-check:
	uv run mypy .

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
