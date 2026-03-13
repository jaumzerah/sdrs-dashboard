#!/bin/bash
set -e

DEPLOY_DIR=/opt/sdr-agents

echo "==> Atualizando código..."
cd $DEPLOY_DIR
git pull origin main

echo "==> Rebuilding imagens..."
docker compose -f docker-compose.prod.yml build --no-cache

echo "==> Reiniciando serviços..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "==> Status dos serviços:"
docker compose -f docker-compose.prod.yml ps

echo "==> Deploy concluído."
