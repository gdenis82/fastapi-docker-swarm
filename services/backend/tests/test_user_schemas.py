
import pytest
from pydantic import ValidationError
from app.schemas.user import UserCreate, UserUpdate

def test_user_create_password_length():
    # Valid password (long)
    user_in = UserCreate(email="test@example.com", username="testuser", password="a" * 100)
    assert user_in.password == "a" * 100
    
    # Too short password
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(email="test@example.com", username="testuser", password="a" * 7)
    assert "String should have at least 8 characters" in str(excinfo.value)

def test_user_update_password_length():
    # Valid password (long)
    user_up = UserUpdate(password="a" * 100)
    assert user_up.password == "a" * 100
    
    # Too short password
    with pytest.raises(ValidationError) as excinfo:
        UserUpdate(password="a" * 7)
    assert "String should have at least 8 characters" in str(excinfo.value)
