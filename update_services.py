import json
import subprocess
import os
import sys
import time
from datetime import datetime

def run_ssh(host_config, command, input_data=None):
    """Выполняет команду на удаленном хосте через SSH."""
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no"]
    if host_config.get("key_path"):
        ssh_base += ["-i", host_config["key_path"]]
    connection_str = f"{host_config['user']}@{host_config['ip']}"
    full_command = ssh_base + [connection_str, command]
    
    # print(f"[{host_config['ip']}] Выполнение: {command}")
    result = subprocess.run(full_command, input=input_data, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Ошибка на {host_config['ip']}: {result.stderr}")
        return None
    return result.stdout.strip()

def build_and_push(service_name, context_path, registry, image_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_tag = f"{registry}/{image_name}:{timestamp}"
    latest_tag = f"{registry}/{image_name}:latest"
    
    print(f"\n--- Сборка {service_name} ---")
    print(f"Контекст: {context_path}")
    print(f"Тег: {image_tag}")
    
    # Сборка
    subprocess.run(["docker", "build", "-t", image_tag, "-t", latest_tag, context_path], check=True)
    
    # Push
    print(f"Push: {image_tag}")
    subprocess.run(["docker", "push", image_tag], check=True)
    subprocess.run(["docker", "push", latest_tag], check=True)
    
    return image_tag

def main():
    # Поиск inventory.json в текущей директории или в директории infrastructure
    inventory_path = "infrastructure/inventory.json"
    if not os.path.exists(inventory_path):
        inventory_path = "inventory.json"
        
    if not os.path.exists(inventory_path):
        print(f"Ошибка: inventory.json не найден")
        sys.exit(1)
        
    with open(inventory_path, "r") as f:
        config = json.load(f)
    
    manager = config["manager"]
    registry = config["registry"]
    stack_name = config["stack_name"]
    
    # 1. Сборка и Push Бэкенда
    backend_image = build_and_push("Backend", "services/backend", registry, "backend")
    
    # 2. Сборка и Push Фронтенда
    frontend_image = build_and_push("Frontend", "services/frontend", registry, "frontend")
    
    # 3. Подготовка конфигураций для удаленного деплоя
    print("\n--- Шаг 3: Подготовка конфигураций ---")
    
    # Создаем структуру папок на менеджере
    run_ssh(manager, "mkdir -p /tmp/deploy/nginx")
    
    # Копируем services.yml
    deploy_file = "deploy/services.yml"
    with open(deploy_file, "r") as f:
        compose_content = f.read()
    
    remote_compose_path = "/tmp/deploy/services.yml"
    run_ssh(manager, f"cat <<'EOF' > {remote_compose_path}\n{compose_content}\nEOF")
    
    # Копируем nginx config
    nginx_conf_file = "deploy/nginx/default.conf"
    with open(nginx_conf_file, "r") as f:
        nginx_conf_content = f.read()
    
    remote_nginx_conf_path = "/tmp/deploy/nginx/default.conf"
    run_ssh(manager, f"cat <<'EOF' > {remote_nginx_conf_path}\n{nginx_conf_content}\nEOF")
    
    # 4. Деплой или Обновление сервисов
    print("\n--- Шаг 4: Деплой сервисов в Swarm ---")
    
    env_vars = (
        f"export REGISTRY_URL={registry} && "
        f"export APP_SECRET='{config['app_secret']}' && "
        f"export DB_USER='{config.get('db_user', 'postgres')}' && "
        f"export DB_PASSWORD='{config.get('db_password', 'postgres')}' && "
        f"export DB_NAME='{config.get('db_name', 'postgres')}'"
    )
    
    # Переходим в /tmp/deploy чтобы docker stack deploy нашел файл конфигурации по относительному пути
    deploy_cmd = f"cd /tmp/deploy && {env_vars} && docker stack deploy --with-registry-auth -c services.yml {stack_name}"
    
    print("Запуск docker stack deploy...")
    out = run_ssh(manager, deploy_cmd)
    if out:
        print(out)

    print("\n=== Обновление сервисов завершено ===")
    print(f"Приложение должно быть доступно по адресу: http://{manager['ip']}")
    print(f"API доступно по адресу: http://{manager['ip']}/api")
    print(f"Документация: http://{manager['ip']}/docs")

if __name__ == "__main__":
    main()
