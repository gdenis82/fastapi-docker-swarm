import json
import subprocess
import os
import sys
import time
from datetime import datetime

def run_ssh(host_config, command, input_data=None, stream=False):
    """Выполняет команду на удаленном хосте через SSH."""
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no"]
    if host_config.get("key_path"):
        ssh_base += ["-i", host_config["key_path"]]
    connection_str = f"{host_config['user']}@{host_config['ip']}"
    full_command = ssh_base + [connection_str, command]
    
    if stream:
        process = subprocess.Popen(
            full_command, 
            stdin=subprocess.PIPE if input_data else None,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1
        )
        if input_data:
            process.stdin.write(input_data)
            process.stdin.close()
        
        output = []
        for line in process.stdout:
            print(line, end="")
            output.append(line)
        
        process.wait()
        if process.returncode != 0:
            return None
        return "".join(output).strip()

    # Обычный запуск через subprocess.run
    result = subprocess.run(full_command, input=input_data, capture_output=True, text=True)
    
    if result.returncode != 0:
        if result.stderr:
            print(f"Ошибка на {host_config['ip']}: {result.stderr.strip()}")
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
    
    # Версионирование конфига Nginx для принудительного обновления сервиса
    nginx_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    compose_content = compose_content.replace("${NGINX_CONFIG_VERSION:-v1}", nginx_version)
    
    remote_compose_path = "/tmp/deploy/services.yml"
    run_ssh(manager, f"cat > {remote_compose_path}", input_data=compose_content)
    
    # Копируем nginx config
    nginx_conf_file = "deploy/nginx/default.conf"
    with open(nginx_conf_file, "r") as f:
        nginx_conf_content = f.read()
    
    remote_nginx_conf_path = "/tmp/deploy/nginx/default.conf"
    run_ssh(manager, f"cat > {remote_nginx_conf_path}", input_data=nginx_conf_content)
    
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
    run_ssh(manager, deploy_cmd, stream=True)

    # 5. Запуск миграций БД
    print("\n--- Шаг 5: Запуск миграций БД ---")
    
    print("Проверка готовности базы данных...")
    # Ждем пока контейнер БД станет healthy
    wait_db_cmd = f"docker ps --filter name={stack_name}_db --filter health=healthy -q"
    for i in range(10):
        db_ready_id = run_ssh(manager, wait_db_cmd)
        if db_ready_id:
            print("База данных готова.")
            break
        print(f"Попытка {i+1}/10: база данных еще не готова (ждем статус healthy), ждем 5с...")
        time.sleep(5)

    print("Запуск временного контейнера для миграций на менеджере...")
    
    # Формируем переменные окружения для docker run
    # Нам нужно подключиться к БД. В Swarm БД доступна по имени сервиса 'db' в сети 'app_network'.
    # Поскольку мы запускаем контейнер через `docker run`, нам нужно подключить его к этой же сети.
    
    # Проверим, какой образ мы только что запушили
    # backend_image уже содержит полный путь с тегом timestamp или latest
    
    migration_cmd = (
        f"docker run --rm --network app_network "
        f"-e DB_HOST=db "
        f"-e DB_PORT=5432 "
        f"-e DB_USER='{config.get('db_user', 'postgres')}' "
        f"-e DB_PASSWORD='{config.get('db_password', 'postgres')}' "
        f"-e DB_NAME='{config.get('db_name', 'postgres')}' "
        f"-e REDIS_HOST=redis "
        f"-e SECRET_KEY='{config['app_secret']}' "
        f"{backend_image} alembic upgrade head"
    )
    
    migrate_out = run_ssh(manager, migration_cmd, stream=True)
    if migrate_out is None:
        print("ОШИБКА: Миграции не были применены!")
        sys.exit(1)
    
    print("Миграции успешно применены.")

    print("\n=== Обновление сервисов завершено ===")
    print(f"Приложение должно быть доступно по адресу: http://{manager['ip']}")
    print(f"API доступно по адресу: http://{manager['ip']}/api")
    print(f"Документация: http://{manager['ip']}/docs")

if __name__ == "__main__":
    main()
