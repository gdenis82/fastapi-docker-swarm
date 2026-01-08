#!/bin/bash
# post-deploy-checklist.sh
# Скрипт для быстрой проверки здоровья инфраструктуры после деплоя.

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Диагностика Docker Swarm Кластера ===${NC}"

# 1. Проверка нод
echo -n "Ноды в кластере: "
NODES_READY=$(docker node ls --format '{{.Status}}' | grep -c "Ready")
if [ "$NODES_READY" -ge 3 ]; then
    echo -e "${GREEN}OK ($NODES_READY/3)${NC}"
else
    echo -e "${RED}FAIL ($NODES_READY/3)${NC}"
fi

# 2. Проверка Registry
echo -n "Статус Registry: "
REG_STATUS=$(docker service ls --filter name=registry --format '{{.Replicas}}')
if [ "$REG_STATUS" == "1/1" ]; then
    echo -e "${GREEN}RUNNING${NC}"
else
    echo -e "${RED}DOWN ($REG_STATUS)${NC}"
fi

# 3. Проверка Приложения
echo -n "Статус FastAPI:  "
APP_STATUS=$(docker service ls --filter name=fastapi_stack_app --format '{{.Replicas}}')
if [ "$APP_STATUS" == "3/3" ]; then
    echo -e "${GREEN}HEALTHY${NC}"
else
    echo -e "${RED}DEGRADED ($APP_STATUS)${NC}"
fi

# 4. Проверка Portainer
echo -n "Статус Portainer: "
PORTAINER_STATUS=$(docker service ls --filter name=portainer_portainer --format '{{.Replicas}}')
if [ "$PORTAINER_STATUS" == "1/1" ]; then
    echo -e "${GREEN}UP${NC}"
else
    echo -e "${RED}DOWN ($PORTAINER_STATUS)${NC}"
fi

# 5. Проверка безопасности Registry (HTPASSWD)
echo -n "Защита Registry: "
if docker service inspect registry --format '{{json .Spec.TaskTemplate.ContainerSpec.Env}}' | grep -q "REGISTRY_AUTH=htpasswd"; then
    echo -e "${GREEN}ENABLED${NC}"
else
    echo -e "${RED}DISABLED (Critical!)${NC}"
fi

echo -e "${GREEN}=== Проверка завершена ===${NC}"
