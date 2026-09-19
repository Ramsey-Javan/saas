.PHONY: help build up down restart logs ps shell bash migrate makemigrations createsuperuser test setup-demo setup_demo seed-staff seed_staff frontend-install frontend-dev frontend-build frontend-preview frontend-lint clean

COMPOSE := docker compose
BACKEND := $(COMPOSE) exec backend python manage.py
FRONTEND_DIR := frontend

help:
	@echo "Available commands:"
	@echo "  make build              Build Docker images"
	@echo "  make up                 Start all Docker services in the background"
	@echo "  make down               Stop Docker services"
	@echo "  make restart            Restart Docker services"
	@echo "  make ps                 Show Docker service status"
	@echo "  make logs               Follow logs for all services"
	@echo "  make shell              Open Django shell"
	@echo "  make bash               Open a shell inside the backend container"
	@echo "  make migrate            Run Django migrations"
	@echo "  make makemigrations     Create Django migrations"
	@echo "  make createsuperuser    Create a Django superuser"
	@echo "  make test               Run Django tests"
	@echo "  make setup-demo         Load demo data"
	@echo "  make setup_demo         Load demo data (alias)"
	@echo "  make seed-staff         Seed generated staff (interactive, or T/N/S/P args)"
	@echo "  make seed_staff         Seed generated staff (alias)"
	@echo "  make frontend-install   Install frontend dependencies"
	@echo "  make frontend-dev       Start Vite dev server"
	@echo "  make frontend-build     Build frontend assets"
	@echo "  make frontend-preview   Preview frontend production build"
	@echo "  make frontend-lint      Run frontend lint"
	@echo "  make clean              Stop services and remove volumes"

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart: down up

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

shell:
	$(BACKEND) shell

bash:
	$(COMPOSE) exec backend sh

migrate:
	$(BACKEND) migrate

makemigrations:
	$(BACKEND) makemigrations

createsuperuser:
	$(BACKEND) createsuperuser

test:
	$(BACKEND) test

setup-demo:
	$(BACKEND) setup_demo

setup_demo: setup-demo

# Interactive by default; or: make seed-staff T="School Name" N=45 S=5
seed-staff:
	$(BACKEND) seed_staff $(if $(T),--tenant "$(T)") $(if $(N),--teachers $(N)) $(if $(S),--support $(S)) $(if $(P),--password "$(P)")

seed_staff: seed-staff

frontend-install:
	npm --prefix $(FRONTEND_DIR) install

frontend-dev:
	npm --prefix $(FRONTEND_DIR) run dev

frontend-build:
	npm --prefix $(FRONTEND_DIR) run build

frontend-preview:
	npm --prefix $(FRONTEND_DIR) run preview

frontend-lint:
	npm --prefix $(FRONTEND_DIR) run lint

clean:
	$(COMPOSE) down -v
