#!/usr/bin/env bash
set -e

export COMPOSE_INTERACTIVE_NO_CLI=1

echo 'Changing directory to project repository...'
cd ./backend

echo 'Setting environment variables...'
source ./.envs/.prod/.do

echo 'Pulling latest source code...'
git pull

echo 'Tagging latest backend image with `old` tag...'
docker tag registry.gitlab.com/mineralogy.rocks/api:latest registry.gitlab.com/mineralogy.rocks/api:old

echo 'Setting cronjobs...'
sudo cp ./.services/crontab/config /etc/cron.d/backend

echo 'Building latest nginx image...'
docker compose -f docker-compose.prod.yaml build nginx datadog

echo 'Pulling latest backend image...'
docker pull registry.gitlab.com/mineralogy.rocks/api:latest

echo 'Removing dangling images...'
docker image prune -f

echo 'Restarting containers...'
docker compose -f docker-compose.prod.yaml up -d --no-deps backend datadog

echo 'Restarting nginx...'
docker compose -f docker-compose.prod.yaml restart nginx

export COMPOSE_INTERACTIVE_NO_CLI=0
