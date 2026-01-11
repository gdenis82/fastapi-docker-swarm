import json
import subprocess
import os
import sys
import time

def run_ssh(host_config, command, ignore_errors=False):
    """Выполняет команду на удаленном хосте через SSH."""
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no"]
    
    if host_config.get("key_path"):
        ssh_base += ["-i", host_config["key_path"]]
    
    connection_str = f"{host_config['user']}@{host_config['ip']}"
    full_command = ssh_base + [connection_str, command]
    
    # print(f"[{host_config['ip']}] Выполнение: {command}")
    result = subprocess.run(full_command, capture_output=True, text=True)
    
    if result.returncode != 0:
        if not ignore_errors:
            print(f"Ошибка на {host_config['ip']}: {result.stderr.strip()}")
        return None
    return result.stdout.strip()

def cleanup_node(host_config, is_manager=False, full_reset=False):
    print(f"\n--- Очистка ноды {host_config['ip']} ---")
    
    # Проверяем статус ноды в Swarm
    swarm_status = run_ssh(host_config, "docker info --format '{{.Swarm.LocalNodeState}}'", ignore_errors=True)
    in_swarm = swarm_status == "active"
    
    # Проверяем, является ли нода менеджером на самом деле
    actual_manager = False
    if in_swarm:
        role = run_ssh(host_config, "docker info --format '{{.Swarm.ControlAvailable}}'", ignore_errors=True)
        actual_manager = (role == "true")

    if actual_manager and is_manager:
        # Удаление стеков
        stacks = run_ssh(host_config, "docker stack ls --format '{{.Name}}'", ignore_errors=True)
        if stacks:
            for stack in stacks.split('\n'):
                if stack:
                    print(f"Удаление стека: {stack}")
                    run_ssh(host_config, f"docker stack rm {stack}", ignore_errors=True)
            
            print("Ожидание удаления ресурсов стека (10с)...")
            time.sleep(10)
        
        # Удаление секретов
        secrets = run_ssh(host_config, "docker secret ls --format '{{.Name}}'", ignore_errors=True)
        if secrets:
            for secret in secrets.split('\n'):
                if secret:
                    print(f"Удаление секрета: {secret}")
                    run_ssh(host_config, f"docker secret rm {secret}", ignore_errors=True)

        # Удаление конфигов
        configs = run_ssh(host_config, "docker config ls --format '{{.Name}}'", ignore_errors=True)
        if configs:
            for cfg in configs.split('\n'):
                if cfg:
                    print(f"Удаление конфига: {cfg}")
                    run_ssh(host_config, f"docker config rm {cfg}", ignore_errors=True)
    elif is_manager and not actual_manager:
        if in_swarm:
            print("Нода числится как менеджер в конфиге, но в Swarm она является воркером.")
        else:
            print("Нода не в Swarm, пропуск удаления ресурсов Swarm.")

    # Очистка системы (удаление остановленных контейнеров, неиспользуемых сетей)
    if full_reset:
        print("Запуск полной очистки Docker (system prune -af)...")
        run_ssh(host_config, "docker system prune -af --volumes", ignore_errors=True)
        print("Очистка builder cache...")
        run_ssh(host_config, "docker builder prune -af", ignore_errors=True)
    else:
        print("Запуск легкой очистки Docker (system prune -f)...")
        run_ssh(host_config, "docker system prune -f", ignore_errors=True)

    if full_reset:
        if is_manager:
            print("Удаление временных папок и файлов (/tmp/deploy, /tmp/infra, /tmp/portainer.yml)...")
            run_ssh(host_config, "rm -rf /tmp/deploy /tmp/infra /tmp/portainer.yml", ignore_errors=True)
            
        if in_swarm:
            print("Выход из Docker Swarm...")
            if actual_manager:
                run_ssh(host_config, "docker swarm leave --force", ignore_errors=True)
            else:
                run_ssh(host_config, "docker swarm leave", ignore_errors=True)
        else:
            print("Нода уже не в Swarm.")

def main():
    # Поиск inventory.json в текущей директории или в директории скрипта
    inventory_path = "inventory.json"
    if not os.path.exists(inventory_path):
        inventory_path = os.path.join(os.path.dirname(__file__), "inventory.json")
        
    if not os.path.exists(inventory_path):
        print(f"Ошибка: inventory.json не найден (проверено в . и {os.path.dirname(__file__)})")
        sys.exit(1)
        
    with open(inventory_path, "r") as f:
        config = json.load(f)
    
    manager = config["manager"]
    workers = config["workers"]
    
    full_reset = "--full" in sys.argv

    # Сначала чистим менеджер (удаляем стеки)
    cleanup_node(manager, is_manager=True, full_reset=full_reset)
    
    # Затем чистим воркеры
    for worker in workers:
        cleanup_node(worker, is_manager=False, full_reset=full_reset)
        
    print("\n=== Очистка завершена! ===")
    if full_reset:
        print("Кластер Swarm был полностью расформирован.")

if __name__ == "__main__":
    main()
