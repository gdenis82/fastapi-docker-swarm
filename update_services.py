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

def scan_image(image_tag):
    """Сканирует образ на уязвимости с помощью trivy."""
    print(f"\n--- Сканирование образа {image_tag} ---")
    try:
        # Проверяем, установлен ли trivy
        subprocess.run(["trivy", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ПРЕДУПРЕЖДЕНИЕ: trivy не найден. Пропуск сканирования.")
        return True

    # Запуск сканирования
    # --severity HIGH,CRITICAL: только критические и высокие уязвимости
    # --exit-code 1: вернуть ненулевой код при обнаружении уязвимостей
    result = subprocess.run([
        "trivy", "image", 
        "--severity", "HIGH,CRITICAL",
        "--exit-code", "1",
        "--no-progress",
        image_tag
    ])
    
    if result.returncode != 0:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: В образе {image_tag} найдены опасные уязвимости!")
        # В реальном CI/CD мы бы здесь вышли с ошибкой, 
        # но для скрипта дадим пользователю шанс решить.
        confirm = input("Продолжить деплой, несмотря на уязвимости? (y/n): ")
        return confirm.lower() == 'y'
    
    print("Сканирование завершено, критических уязвимостей не обнаружено.")
    return True

def build_and_push(service_name, context_path, registry, image_name, build_args=None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_tag = f"{registry}/{image_name}:{timestamp}"
    latest_tag = f"{registry}/{image_name}:latest"
    
    print(f"\n--- Сборка {service_name} ---")
    print(f"Контекст: {context_path}")
    print(f"Тег: {image_tag}")
    
    # Формируем команду сборки
    build_cmd = ["docker", "build", "-t", image_tag, "-t", latest_tag]
    if build_args:
        for key, value in build_args.items():
            build_cmd.extend(["--build-arg", f"{key}={value}"])
    build_cmd.append(context_path)
    
    # Сборка
    subprocess.run(build_cmd, check=True)
    
    # Сканирование
    if not scan_image(image_tag):
        print(f"Сборка {service_name} отменена из-за уязвимостей.")
        sys.exit(1)
    
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
    # Передаем NEXT_PUBLIC_API_URL=/api так как nginx проксирует запросы
    frontend_image = build_and_push(
        "Frontend", 
        "services/frontend", 
        registry, 
        "frontend",
        build_args={"NEXT_PUBLIC_API_URL": "/api"}
    )
    
    # 3. Подготовка конфигураций для удаленного деплоя
    print("\n--- Шаг 3: Подготовка конфигураций ---")
    
    # Создаем структуру папок на менеджере
    run_ssh(manager, "mkdir -p /tmp/deploy")
    
    # Копируем services.yml
    deploy_file = "deploy/services.yml"
    with open(deploy_file, "r") as f:
        compose_content = f.read()
    
    remote_compose_path = "/tmp/deploy/services.yml"
    run_ssh(manager, f"cat > {remote_compose_path}", input_data=compose_content)
    
    # 4. Деплой или Обновление сервисов
    print("\n--- Шаг 4: Деплой сервисов в Swarm ---")
    
    # ВАЖНО: Внутри Swarm бэкенд должен подключаться к БД и Redis 
    # по именам сервисов, а не по внешнему IP.
    # Секреты теперь передаются через Docker Secrets, поэтому здесь только не-секретные переменные.
    env_vars = (
        f"export REGISTRY_URL={registry} && "
        f"export DB_HOST='db' && "
        f"export REDIS_HOST='redis'"
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
    # Для миграций через `docker run` секреты Docker не доступны автоматически как файлы, 
    # поэтому здесь мы все еще передаем их через ENV, но это временный контейнер.
    
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
    print(f"Приложение должно быть доступно по адресу: https://tryout.site")
    print(f"API доступно по адресу: https://tryout.site/api")
    print(f"Документация: https://tryout.site/docs")

if __name__ == "__main__":
    main()
