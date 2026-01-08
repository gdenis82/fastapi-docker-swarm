import json
import subprocess
import os
import sys
import time
from datetime import datetime

def run_ssh(host_config, command):
    """Выполняет команду на удаленном хосте через SSH."""
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no"]
    if host_config.get("key_path"):
        ssh_base += ["-i", host_config["key_path"]]
    connection_str = f"{host_config['user']}@{host_config['ip']}"
    full_command = ssh_base + [connection_str, command]
    
    print(f"[{host_config['ip']}] Выполнение: {command}")
    result = subprocess.run(full_command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Ошибка на {host_config['ip']}: {result.stderr}")
        return None
    return result.stdout.strip()

def main():
    if not os.path.exists("inventory.json"):
        print("Ошибка: inventory.json не найден")
        sys.exit(1)
        
    with open("inventory.json", "r") as f:
        config = json.load(f)
    
    manager = config["manager"]
    registry = config["registry"]
    stack_name = config["stack_name"]
    service_name = f"{stack_name}_app"
    
    # 1. Сборка образа с уникальным тегом
    print("\n--- Шаг 1: Сборка нового образа ---")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_tag = f"{registry}/fastapi-app:{timestamp}"
    
    print(f"Сборка: {image_tag}")
    subprocess.run(["docker", "build", "-t", image_tag, "."], check=True)
    
    # 2. Push в реестр
    print("\n--- Шаг 2: Push образа в реестр ---")
    try:
        subprocess.run(["docker", "push", image_tag], check=True)
    except subprocess.CalledProcessError:
        print("Ошибка при push. Проверьте настройки insecure-registries в Docker Desktop.")
        sys.exit(1)
        
    # 3. Обновление только сервиса
    print("\n--- Шаг 3: Обновление сервиса в Swarm ---")
    # Мы обновляем только образ у конкретного сервиса. 
    # Это гораздо быстрее, чем docker stack deploy, так как не пересчитывается весь стек.
    update_cmd = f"docker service update --image {image_tag} --with-registry-auth {service_name}"
    
    result = run_ssh(manager, update_cmd)
    if result:
        print("Команда на обновление отправлена успешно.")
        
        print("\nОжидание начала обновления...")
        time.sleep(3)
        # Показываем статус задач
        run_ssh(manager, f"docker service ps {service_name}")
        
        print(f"\nПриложение обновляется. Проверьте: http://{manager['ip']}:8080/node")
    else:
        print("Не удалось обновить сервис. Возможно, стек еще не задеплоен основным скриптом.")

if __name__ == "__main__":
    main()
