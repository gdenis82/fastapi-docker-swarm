from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logger import logger
from app.core.config import settings
from app.db.session import get_db
import os
import psycopg2

router = APIRouter(
    tags=["root"],
    responses={404: {"description": "Not found"}},
)

# Описание тега: Базовые операции, проверка состояния системы и отладочная информация.

@router.get(
    "/",
    summary="Приветствие",
    description="Возвращает приветственное сообщение с названием проекта.",
    response_description="JSON с приветствием."
)
async def read_root():
    logger.debug("Root endpoint called")
    return {"message": f"Hello from {settings.PROJECT_NAME}!"}

@router.get(
    "/health",
    summary="Проверка состояния",
    description="Простой эндпоинт для проверки того, что приложение запущено и отвечает на запросы. Используется Liveness и Readiness пробами.",
    response_description="Статус 'ok'."
)
async def health():
    return {"status": "ok"}

@router.get(
    "/db-check",
    summary="Проверка БД",
    description="Проверяет соединение с базой данных PostgreSQL и возвращает версию сервера.",
    response_description="Статус подключения и версия БД."
)
async def db_check(db: AsyncSession = Depends(get_db)):
    if not settings.DATABASE_URL:
        return {"status": "error", "message": "DATABASE_URL is not set"}
    
    try:
        # Check using SQLAlchemy session
        from sqlalchemy import text
        result = await db.execute(text("SELECT version();"))
        version = result.fetchone()
        return {"status": "ok", "db_version": version[0]}
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return {"status": "error", "message": str(e)}

@router.get(
    "/node",
    summary="Имя ноды",
    description="Возвращает имя текущей ноды Docker Swarm (из переменной окружения NODE_NAME). Полезно для отладки балансировки нагрузки.",
    response_description="Имя ноды или 'local-development'."
)
async def get_node_name():
    node_name = os.getenv("NODE_NAME", "local-development")
    logger.debug(f"Node name requested: {node_name}")
    return {"node_name": node_name}

@router.get(
    "/redis-check",
    summary="Проверка Redis",
    description="Проверяет доступность Redis, выполняя команду PING.",
    response_description="Результат PING или сообщение об ошибке."
)
async def redis_check():
    from app.core.redis import redis_client
    try:
        ping = await redis_client.ping()
        logger.debug(f"Redis ping result: {ping}")
        return {"status": "ok", "redis_ping": ping}
    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        return {"status": "error", "message": str(e)}
