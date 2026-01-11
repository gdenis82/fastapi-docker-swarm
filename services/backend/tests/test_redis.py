import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)

@patch("app.core.redis.redis_client.ping", new_callable=AsyncMock)
def test_redis_check_success(mock_ping):
    # Настраиваем мок на успешный ответ
    mock_ping.return_value = True
    
    response = client.get("/api/redis-check")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["redis_ping"] is True
    mock_ping.assert_called_once()

@patch("app.core.redis.redis_client.ping", new_callable=AsyncMock)
def test_redis_check_failure(mock_ping):
    # Настраиваем мок на ошибку соединения
    mock_ping.side_effect = Exception("Connection error")
    
    response = client.get("/api/redis-check")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "Connection error" in data["message"]
    mock_ping.assert_called_once()
