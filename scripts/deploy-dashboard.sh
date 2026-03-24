#!/bin/bash
set -e

DEPLOY_DIR=/opt/sdr-agents
IMAGE_NAME=sdr-dashboard:latest
STACK_NAME=sdr-dashboard

echo "==> Atualizando código..."
cd "$DEPLOY_DIR"
git pull origin main

echo "==> Buildando imagem da dashboard..."
docker build -t "$IMAGE_NAME" .

echo "==> Fazendo deploy da stack da dashboard..."
docker stack deploy -c docker-stack.dashboard.yml "$STACK_NAME" --with-registry-auth

echo "==> Status dos serviços:"
docker stack ps "$STACK_NAME"

echo "==> Deploy da dashboard concluído."
