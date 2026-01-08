#!/bin/bash

# Скрипт для настройки инфраструктуры Docker Swarm на основе статьи

# Цвета для вывода
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}===> Шаг 1: Настройка Firewall <===${NC}"

# Функция для настройки портов (предполагается наличие firewall-cmd)
setup_firewall_manager() {
    echo "Настройка портов для Manager ноды..."
    sudo firewall-cmd --add-port=2376/tcp --permanent
    sudo firewall-cmd --add-port=2377/tcp --permanent
    sudo firewall-cmd --add-port=7946/tcp --permanent
    sudo firewall-cmd --add-port=7946/udp --permanent
    sudo firewall-cmd --add-port=4789/udp --permanent
    sudo firewall-cmd --add-port=8080/tcp --permanent
    sudo firewall-cmd --add-port=9000/tcp --permanent
    sudo firewall-cmd --add-port=5000/tcp --permanent
    sudo firewall-cmd --reload
    sudo systemctl restart docker
}

setup_firewall_worker() {
    echo "Настройка портов для Worker ноды..."
    sudo firewall-cmd --add-port=2376/tcp --permanent
    sudo firewall-cmd --add-port=7946/tcp --permanent
    sudo firewall-cmd --add-port=7946/udp --permanent
    sudo firewall-cmd --add-port=4789/udp --permanent
    sudo firewall-cmd --add-port=8080/tcp --permanent
    sudo firewall-cmd --reload
    sudo systemctl restart docker
}

echo -e "${GREEN}===> Шаг 2: Инициализация кластера <===${NC}"
# Команда для запуска на manager:
# docker swarm init --advertise-addr <MANAGER_IP>

echo -e "${GREEN}===> Шаг 3: Добавление меток (Labels) <===${NC}"
# После присоединения воркеров (docker swarm join ...), выполните на manager:
# docker node update --label-add type=worker worker-1
# docker node update --label-add type=worker worker-2

echo -e "${GREEN}===> Шаг 4: Создание секретов <===${NC}"
# echo "my_secret_value" | docker secret create app_secret -

echo -e "${GREEN}===> Шаг 5: Деплой стэка <===${NC}"
# docker stack deploy -c docker-compose.yml fastapi_stack

echo -e "${GREEN}===> Шаг 6: Установка Portainer (опционально) <===${NC}"
# curl -L https://raw.githubusercontent.com/portainer/portainer-compose/master/docker-stack.yml -o portainer-agent-stack.yml
# docker stack deploy -c portainer-agent-stack.yml portainer
