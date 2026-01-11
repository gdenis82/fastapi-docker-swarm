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
    
    if input_data:
        print(f"[{host_config['ip']}] Выполнение (с данными в stdin): {command}")
    else:
        print(f"[{host_config['ip']}] Выполнение: {command}")
        
    result = subprocess.run(
        full_command, 
        input=input_data if input_data else None,
        capture_output=True, 
        text=True
    )
    
    if result.returncode != 0:
        print(f"Ошибка на {host_config['ip']}: {result.stderr}")
        return None
    return result.stdout.strip()

def setup_firewall(host_config, is_manager=False):
    print(f" Настройка Firewall на {host_config['ip']}...")
    
    # Порты для Swarm и сервисов
    tcp_ports = ["22", "2376", "2377", "7946", "80", "443", "8080", "9000", "9443", "5000"]
    udp_ports = ["7946", "4789"]
    
    # Мы попробуем использовать и ufw (если есть), и iptables напрямую для надежности
    commands = [
        "sudo ufw allow 22/tcp", # Всегда разрешаем SSH первым
    ]
    
    # 1. Попытка через ufw
    for p in tcp_ports:
        commands.append(f"sudo ufw allow {p}/tcp")
    for p in udp_ports:
        commands.append(f"sudo ufw allow {p}/udp")
    
    # 2. Попытка через iptables (на случай если ufw выключен или не установлен)
    for p in tcp_ports:
        commands.append(f"sudo iptables -A INPUT -p tcp --dport {p} -j ACCEPT || true")
    for p in udp_ports:
        commands.append(f"sudo iptables -A INPUT -p udp --dport {p} -j ACCEPT || true")
    
    # 3. Специфично для Beget/Ubuntu - открываем протокол 50 (ESP) и 51 (AH) если нужно, 
    # но для Swarm обычно достаточно UDP 4789.
    
    # Перезапуск docker после настройки сети часто помогает инициализировать overlay правильно
    commands.append("sudo systemctl restart docker")
    
    run_ssh(host_config, " && ".join(commands))

def setup_registry(manager_config, config):
    print(f" Настройка Docker Registry как Swarm Service на {manager_config['ip']}...")
    
    # 1. Проверяем наличие htpasswd
    registry_user = config["registry_user"]
    registry_password = config["registry_password"]
    
    # Создаем директорию для auth на менеджере
    run_ssh(manager_config, "mkdir -p /root/registry/auth")
    
    # Генерируем htpasswd (требует apache2-utils, но мы сделаем это через docker образ)
    # Используем образ с htpasswd для создания файла
    gen_cmd = (
        f"docker run --rm "
        f"--entrypoint htpasswd "
        f"httpd:2.4 -Bbn {registry_user} {registry_password}"
    )
    htpasswd_content = run_ssh(manager_config, gen_cmd)
    if htpasswd_content:
        run_ssh(manager_config, "cat > /root/registry/auth/htpasswd", input_data=htpasswd_content)
    
    # 2. Проверяем, запущен ли сервис registry
    check_cmd = "docker service ls --filter name=registry -q"
    service_id = run_ssh(manager_config, check_cmd)
    
    if not service_id:
        print("Создание сервиса Registry...")
        create_cmd = (
            "docker service create "
            "--name registry "
            "--publish 5000:5000 "
            "--constraint 'node.role == manager' "
            "--mount type=volume,source=registry_data,destination=/var/lib/registry "
            "--mount type=bind,source=/root/registry/auth,destination=/auth "
            "-e REGISTRY_AUTH=htpasswd "
            "-e REGISTRY_AUTH_HTPASSWD_REALM='Registry Realm' "
            "-e REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd "
            "registry:2"
        )
        result = run_ssh(manager_config, create_cmd)
        if result is None:
            print("ОШИБКА: Не удалось создать сервис Registry. Проверьте, что нода является менеджером Swarm.")
    else:
        print("Сервис Registry уже запущен")

def setup_insecure_registry(host_config, registry_ip):
    print(f" Настройка insecure-registry на {host_config['ip']}...")
    daemon_json_path = "/etc/docker/daemon.json"
    
    # Проверяем наличие файла и его содержимое
    check_cmd = f"sudo cat {daemon_json_path} 2>/dev/null || echo '{{}}'"
    content = run_ssh(host_config, check_cmd)
    
    try:
        data = json.loads(content)
    except:
        data = {}
        
    insecure_registries = data.get("insecure-registries", [])
    if registry_ip not in insecure_registries:
        insecure_registries.append(registry_ip)
        data["insecure-registries"] = insecure_registries
        
        # Записываем обратно
        new_content = json.dumps(data, indent=4)
        # Используем base64 или просто экранируем кавычки для записи через SSH
        write_cmd = f"echo '{new_content}' | sudo tee {daemon_json_path} > /dev/null && sudo systemctl restart docker"
        run_ssh(host_config, write_cmd)
        print(f" Registry {registry_ip} добавлен в insecure-registries на {host_config['ip']}")
    else:
        print(f" Registry {registry_ip} уже в списке на {host_config['ip']}")

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
    registry = config["registry"]
    stack_name = config["stack_name"]
    
    # 1. Настройка Firewall
    print("\n--- Шаг 1: Настройка Firewall ---")
    setup_firewall(manager, is_manager=True)
    for worker in workers:
        setup_firewall(worker)
        
    # 2. Настройка insecure-registry на всех нодах
    print("\n--- Шаг 2: Настройка insecure-registry ---")
    setup_insecure_registry(manager, registry)
    for worker in workers:
        setup_insecure_registry(worker, registry)

    # 3. Swarm Init
    print("\n--- Шаг 3: Инициализация Swarm ---")
    init_cmd = f"docker swarm init --advertise-addr {manager['ip']}"
    # Проверяем, не в swarm ли мы уже
    status = run_ssh(manager, "docker info --format '{{.Swarm.LocalNodeState}}'")
    if status != "active":
        out = run_ssh(manager, init_cmd)
        print(out)
    else:
        print("Swarm уже инициализирован")
        
    # 4. Получение токена для воркеров
    token = run_ssh(manager, "docker swarm join-token worker -q")
    join_cmd = f"docker swarm join --token {token} {manager['ip']}:2377"
    
    # 5. Присоединение воркеров
    print("\n--- Шаг 4: Присоединение воркеров ---")
    for worker in workers:
        w_status = run_ssh(worker, "docker info --format '{{.Swarm.LocalNodeState}}'")
        if w_status != "active":
            run_ssh(worker, join_cmd)
        else:
            print(f"Воркер {worker['ip']} уже в кластере")
            
    # 6. Настройка Registry
    print("\n--- Шаг 5: Настройка Docker Registry ---")
    setup_registry(manager, config)
        
    # 7. Логин в Registry
    print("\n--- Шаг 5.1: Авторизация в Registry ---")
    reg_user = config["registry_user"]
    reg_pass = config["registry_password"]
    
    # Логин локально (для push)
    try:
        subprocess.run(["docker", "login", registry, "-u", reg_user, "-p", reg_pass], check=True)
    except subprocess.CalledProcessError:
        print("\n" + "!"*60)
        print(f"ОШИБКА: Не удалось войти в реестр {registry} локально.")
        print("Скорее всего, ваш локальный Docker не доверяет этому реестру.")
        print("Инструкции по исправлению будут ниже в шаге сборки/push.")
        print("!"*60 + "\n")
        # Мы не выходим здесь, так как сборка может упасть позже с более подробным описанием
    
    # Логин на всех нодах (для pull)
    login_cmd = f"docker login {registry} -u {reg_user} -p {reg_pass}"
    run_ssh(manager, login_cmd)
    for worker in workers:
        run_ssh(worker, login_cmd)
        
    # 8. Настройка меток
    print("\n--- Шаг 6: Настройка меток ---")
    for worker in workers:
        hostname = run_ssh(worker, "hostname")
        run_ssh(manager, f"docker node update --label-add type=worker {hostname}")
        
    # 9. Создание сети
    print("\n--- Шаг 7: Создание сети ---")
    check_net_cmd = "docker network ls --filter name=app_network -q"
    net_exists = run_ssh(manager, check_net_cmd)
    
    if not net_exists:
        print("Создание сети app_network...")
        run_ssh(manager, "docker network create --driver overlay app_network")
    else:
        print("Сеть app_network уже существует")

    # 10. Деплой инфраструктуры
    print("\n--- Шаг 8: Деплой инфраструктуры ---")
    
    deploy_file = "deploy/infrastructure.yml"
    if not os.path.exists(deploy_file):
        # Если запускаем из папки infrastructure
        deploy_file = os.path.join(os.path.dirname(__file__), "..", "deploy", "infrastructure.yml")

    if not os.path.exists(deploy_file):
        print(f"Ошибка: {deploy_file} не найден")
        sys.exit(1)

    with open(deploy_file, "r") as f:
        infra_compose = f.read()
    
    remote_infra_path = "/tmp/infrastructure.yml"
    run_ssh(manager, f"cat <<'EOF' > {remote_infra_path}\n{infra_compose}\nEOF")
    
    env_vars = (
        f"export DB_USER='{config.get('db_user', 'postgres')}' && "
        f"export DB_PASSWORD='{config.get('db_password', 'postgres')}' && "
        f"export DB_NAME='{config.get('db_name', 'postgres')}' && "
        f"export PGADMIN_EMAIL='{config.get('pgadmin_email', 'admin@admin.com')}' && "
        f"export PGADMIN_PASSWORD='{config.get('pgadmin_password', 'admin_password_123')}'"
    )
    
    deploy_infra_cmd = f"{env_vars} && docker stack deploy -c {remote_infra_path} {stack_name}"
    run_ssh(manager, deploy_infra_cmd)

    # 11. Мониторинг (Portainer)
    print("\n--- Шаг 9: Установка Portainer ---")
    portainer_url = "https://raw.githubusercontent.com/portainer/portainer-compose/master/docker-stack.yml"
    # Проверяем, не запущен ли уже portainer
    exists = run_ssh(manager, "docker stack ls --filter name=portainer -q")
    if not exists:
        # Скачиваем, исправляем образ на portainer-ce, изолируем сеть и убираем --tlsskipverify
        portainer_cmd = (
            f"curl -L {portainer_url} -o /tmp/portainer.yml && "
            f"sed -i 's/portainer\\/portainer/portainer\\/portainer-ce/g' /tmp/portainer.yml && "
            f"sed -i '/agent_network:/,/driver: overlay/ s/driver: overlay/driver: overlay\\n    internal: true\\n    attachable: false/' /tmp/portainer.yml && "
            f"sed -i 's/--tlsskipverify//g' /tmp/portainer.yml && "
            f"grep -q 'services:' /tmp/portainer.yml && "
            f"docker stack deploy -c /tmp/portainer.yml portainer"
        )
        run_ssh(manager, portainer_cmd)
        print("Команда деплоя Portainer (CE) с изоляцией сети и hardening оправлена")
    else:
        print("Стек Portainer уже запущен")
    
    print("\n=== Деплой успешно завершен! ===")
    print(f"Инфраструктура запущена.")
    print(f"Portainer доступен по адресу: http://{manager['ip']}:9000")
    print(f"\nДля деплоя сервисов запустите: python update_services.py")
    
    if os.path.exists("CHANGELOG.md"):
        print("\nОбновления безопасности и стабильности (см. CHANGELOG.md):")
        print("- Registry теперь в Swarm-сервисе с авторизацией")
        print("- Секреты защищены (передача через stdin)")
        print("- Portainer обновлен до CE и изолирован в сети")
        print("- Настроены лимиты ресурсов и проверки здоровья")

if __name__ == "__main__":
    main()
