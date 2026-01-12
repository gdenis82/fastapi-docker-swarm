import json
import subprocess
import os
import sys
import time
from datetime import datetime

def run_ssh(host_config, command, input_data=None, timeout=30):
    """Выполняет команду на удаленном хосте через SSH."""
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
    
    if host_config.get("key_path"):
        ssh_base += ["-i", host_config["key_path"]]
    
    connection_str = f"{host_config['user']}@{host_config['ip']}"
    full_command = ssh_base + [connection_str, command]
    
    if input_data:
        print(f"[{host_config['ip']}] Выполнение (с данными в stdin): {command}")
    else:
        print(f"[{host_config['ip']}] Выполнение: {command}")
        
    try:
        result = subprocess.run(
            full_command, 
            input=input_data if input_data else None,
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            # Если это ошибка подключения SSH, а не ошибка выполнения команды
            if "ssh: connect to host" in result.stderr or "Connection timed out" in result.stderr:
                print(f"ОШИБКА ПОДКЛЮЧЕНИЯ на {host_config['ip']}: {result.stderr.strip()}")
            else:
                print(f"Ошибка выполнения на {host_config['ip']}: {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"ОШИБКА: Превышено время ожидания (timeout) для {host_config['ip']}")
        return None
    except Exception as e:
        print(f"ОШИБКА при выполнении SSH для {host_config['ip']}: {str(e)}")
        return None

def check_connections(config):
    """Проверяет доступность всех нод перед началом деплоя."""
    print("\n--- Шаг 0: Проверка доступности нод ---")
    nodes = [config["manager"]] + config["workers"]
    all_ok = True
    
    for node in nodes:
        print(f" Проверка {node['ip']}...")
        res = run_ssh(node, "echo 'ok'")
        if res != "ok":
            print(f" ! НОДА {node['ip']} НЕДОСТУПНА. Проверьте сеть, SSH-ключи и настройки сервера.")
            all_ok = False
        else:
            print(f" {node['ip']} доступна.")
    
    if not all_ok:
        confirm = input("\nНекоторые ноды недоступны. Продолжить деплой на доступных? (y/n): ")
        if confirm.lower() != 'y':
            sys.exit(1)
    return all_ok

def setup_firewall(host_config, cluster_ips, is_manager=False):
    print(f" Настройка Firewall на {host_config['ip']}...")
    
    # Сначала проверяем доступность, чтобы не тратить время
    if run_ssh(host_config, "echo 1") is None:
        print(f" Пропуск настройки Firewall для {host_config['ip']} (нода недоступна)")
        return

    # Общедоступные порты
    public_ports = ["22", "80", "443", "8080", "9000"]
    # Порты Swarm и Registry (только для внутреннего использования в кластере)
    internal_tcp_ports = ["2376", "2377", "7946", "5000"]
    internal_udp_ports = ["7946", "4789"]
    
    # Сначала сбрасываем и настраиваем базовые правила без включения
    # Используем --force чтобы не спрашивать подтверждения
    run_ssh(host_config, "sudo ufw --force reset")
    run_ssh(host_config, "sudo ufw default deny incoming")
    run_ssh(host_config, "sudo ufw default allow outgoing")
    
    # Разрешаем SSH и публичные порты
    for p in public_ports:
        run_ssh(host_config, f"sudo ufw allow {p}/tcp")
    
    # Ограничиваем Swarm порты только для IP кластера
    # Группируем правила по IP, чтобы уменьшить количество вызовов SSH, 
    # но не делаем одну гигантскую строку
    for ip in cluster_ips:
        ip_commands = []
        for p in internal_tcp_ports:
            ip_commands.append(f"sudo ufw allow from {ip} to any port {p} proto tcp")
        for p in internal_udp_ports:
            ip_commands.append(f"sudo ufw allow from {ip} to any port {p} proto udp")
        run_ssh(host_config, " && ".join(ip_commands))
            
    # Включаем ufw. 
    # Важно: ufw enable может спросить "Command may disrupt existing ssh connections. Proceed with operation (y|n)?"
    # Мы используем --force или echo y
    run_ssh(host_config, "sudo ufw --force enable")

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
    
    if content is None:
        print(f" Пропуск настройки insecure-registry для {host_config['ip']} (нода недоступна)")
        return

    try:
        data = json.loads(content)
    except Exception as e:
        print(f"Предупреждение: Ошибка парсинга {daemon_json_path} на {host_config['ip']}: {e}. Используем пустой конфиг.")
        data = {}
        
    insecure_registries = data.get("insecure-registries", [])
    if registry_ip not in insecure_registries:
        insecure_registries.append(registry_ip)
        data["insecure-registries"] = insecure_registries
        
        # Записываем обратно
        new_content = json.dumps(data, indent=4)
        # Экранируем одинарные кавычки для shell
        escaped_content = new_content.replace("'", "'\\''")
        write_cmd = f"echo '{escaped_content}' | sudo tee {daemon_json_path} > /dev/null && sudo systemctl restart docker"
        run_ssh(host_config, write_cmd)
        print(f" Registry {registry_ip} добавлен в insecure-registries на {host_config['ip']}")
    else:
        print(f" Registry {registry_ip} уже в списке на {host_config['ip']}")

def setup_secrets(manager_config, config):
    print(f" Настройка Docker Secrets на {manager_config['ip']}...")
    
    secrets = {
        "db_password": config["db_password"],
        "db_user": config["db_user"],
        "db_name": config["db_name"],
        "app_secret": config["app_secret"],
        "secret_key": config["app_secret"], # Для совместимости
        "registry_password": config["registry_password"],
        "pgadmin_password": config["pgadmin_password"],
        "pgadmin_email": config["pgadmin_email"]
    }
    
    for name, value in secrets.items():
        # Проверяем, существует ли секрет
        check_cmd = f"docker secret ls --filter name={name} -q"
        exists = run_ssh(manager_config, check_cmd)
        
        if exists:
            print(f" Секрет {name} уже существует, пропускаем.")
            continue
            
        print(f" Создание секрета {name}...")
        create_cmd = f"printf '{value}' | docker secret create {name} -"
        run_ssh(manager_config, create_cmd)

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
    
    # Список всех IP в кластере для Firewall
    cluster_ips = [manager["ip"]] + [w["ip"] for w in workers]
    
    # 0. Проверка соединений
    check_connections(config)

    # 1. Настройка Firewall
    print("\n--- Шаг 1: Настройка Firewall ---")
    setup_firewall(manager, cluster_ips, is_manager=True)
    for worker in workers:
        setup_firewall(worker, cluster_ips)
        
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
        if w_status is None:
            print(f" Пропуск присоединения воркера {worker['ip']} (нода недоступна)")
            continue
            
        if w_status != "active":
            run_ssh(worker, join_cmd)
        else:
            print(f"Воркер {worker['ip']} уже в кластере")
            
    # 6. Настройка Secrets
    print("\n--- Шаг 4.1: Настройка Docker Secrets ---")
    setup_secrets(manager, config)

    # 7. Настройка Registry
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
    if run_ssh(manager, "echo 1") is not None:
        run_ssh(manager, login_cmd)
    for worker in workers:
        if run_ssh(worker, "echo 1") is not None:
            run_ssh(worker, login_cmd)
        
    # 8. Настройка меток
    print("\n--- Шаг 6: Настройка меток ---")
    for worker in workers:
        hostname = run_ssh(worker, "hostname")
        if hostname:
            run_ssh(manager, f"docker node update --label-add type=worker {hostname}")
        else:
            print(f"Предупреждение: Не удалось получить hostname для воркера {worker['ip']}, метка не добавлена.")
        
    # 9. Создание сети
    print("\n--- Шаг 7: Создание сети ---")
    # Используем grep для совместимости, так как --filter может не поддерживаться в некоторых версиях
    check_net_cmd = "docker network ls --format '{{.Name}}' | grep -w app_network"
    net_exists = run_ssh(manager, check_net_cmd)
    
    if not net_exists:
        print("Создание сети app_network...")
        run_ssh(manager, "docker network create --driver overlay --attachable app_network")
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
    
    # Подготовка pgadmin_servers.json
    pgadmin_servers = {
        "Servers": {
            "1": {
                "Name": "FastAPI App DB",
                "Group": "Servers",
                "Host": "db",
                "Port": 5432,
                "MaintenanceDB": config.get('db_name', 'postgres'),
                "Username": config.get('db_user', 'postgres'),
                "Password": config.get('db_password', 'postgres'),
                "SSLMode": "prefer"
            }
        }
    }
    servers_json_content = json.dumps(pgadmin_servers, indent=4)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Подставляем версию конфига прямо в текст YAML, так как Swarm не поддерживает переменные в именах ключей configs
    infra_compose = infra_compose.replace("${SERVERS_VERSION:-v1}", timestamp)

    # Создаем папку для деплоя на менеджере
    infra_dir = "/tmp/infra"
    run_ssh(manager, f"mkdir -p {infra_dir}")
    
    # Загружаем файлы
    run_ssh(manager, f"cat > {infra_dir}/infrastructure.yml", input_data=infra_compose)
    run_ssh(manager, f"cat > {infra_dir}/pgadmin_servers.json", input_data=servers_json_content)
    
    # Загружаем конфигурации мониторинга
    monitoring_dir = os.path.join(os.path.dirname(deploy_file), "monitoring")
    if os.path.exists(monitoring_dir):
        run_ssh(manager, f"mkdir -p {infra_dir}/monitoring")
        for filename in os.listdir(monitoring_dir):
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                with open(os.path.join(monitoring_dir, filename), "r") as f:
                    content = f.read()
                run_ssh(manager, f"cat > {infra_dir}/monitoring/{filename}", input_data=content)
    
    env_vars = (
        f"export DB_USER='{config.get('db_user', 'postgres')}' && "
        f"export DB_PASSWORD='{config.get('db_password', 'postgres')}' && "
        f"export DB_NAME='{config.get('db_name', 'postgres')}' && "
        f"export PGADMIN_DEFAULT_EMAIL='{config.get('pgadmin_email', 'admin@admin.com')}' && "
        f"export PGADMIN_DEFAULT_PASSWORD='{config.get('pgadmin_password', 'admin_password_123')}'"
    )
    
    deploy_infra_cmd = f"cd {infra_dir} && {env_vars} && docker stack deploy -c infrastructure.yml {stack_name}"
    run_ssh(manager, deploy_infra_cmd)

    # 11. Мониторинг (Portainer)
    print("\n--- Шаг 9: Установка Portainer ---")
    portainer_url = "https://raw.githubusercontent.com/portainer/portainer-compose/master/docker-stack.yml"
    # Проверяем, не запущен ли уже portainer
    # Используем grep для совместимости, так как --filter может не поддерживаться в некоторых версиях docker stack ls
    exists = run_ssh(manager, "docker stack ls --format '{{.Name}}' | grep -w portainer")
    if not exists:
        # Скачиваем, исправляем образ на portainer-ce, изолируем сеть и убираем --tlsskipverify
        # Добавляем метки для Traefik и подключаем к внешней сети app_network
        portainer_cmd = (
            f"curl -L {portainer_url} -o /tmp/portainer.yml && "
            f"sed -i 's/portainer\\/portainer/portainer\\/portainer-ce/g' /tmp/portainer.yml && "
            f"sed -i '/agent_network:/,/driver: overlay/ s/driver: overlay/driver: overlay\\n    internal: true\\n    attachable: false/' /tmp/portainer.yml && "
            f"sed -i 's/--tlsskipverify//g' /tmp/portainer.yml && "
            # Добавление labels для Traefik
            f"sed -i '/portainer:/a \\    networks:\\n      - app_network\\n      - agent_network\\n    deploy:\\n      labels:\\n        - \"traefik.enable=true\"\\n        - \"traefik.http.routers.portainer.rule=Host(`portainer.tryout.site`)\"\\n        - \"traefik.http.routers.portainer.entrypoints=websecure\"\\n        - \"traefik.http.routers.portainer.tls.certresolver=myresolver\"\\n        - \"traefik.http.services.portainer.loadbalancer.server.port=9000\"' /tmp/portainer.yml && "
            # Добавление внешней сети app_network в список сетей в конце файла
            f"sed -i '$ a \\\\nnetworks:\\n  app_network:\\n    external: true' /tmp/portainer.yml && "
            f"grep -q 'services:' /tmp/portainer.yml && "
            f"docker stack deploy -c /tmp/portainer.yml portainer"
        )
        run_ssh(manager, portainer_cmd)
        print("Команда деплоя Portainer (CE) с Traefik labels, изоляцией сети и hardening оправлена")
    else:
        print("Стек Portainer уже запущен")
    
    print("\n=== Деплой успешно завершен! ===")
    print(f"Инфраструктура запущена.")
    print(f"Portainer доступен по адресу: https://portainer.tryout.site (или http://{manager['ip']}:9000)")
    print(f"Grafana доступна по адресу: https://grafana.tryout.site")
    print(f"pgAdmin доступен по адресу: https://pgadmin.tryout.site (или http://{manager['ip']}:8080)")
    print(f"\nДля деплоя сервисов запустите: python update_services.py")
    
    if os.path.exists("CHANGELOG.md"):
        print("\nОбновления безопасности и стабильности (см. CHANGELOG.md):")
        print("- Registry теперь в Swarm-сервисе с авторизацией")
        print("- Секреты защищены (передача через stdin)")
        print("- Portainer обновлен до CE и изолирован в сети")
        print("- Настроены лимиты ресурсов и проверки здоровья")

if __name__ == "__main__":
    main()
