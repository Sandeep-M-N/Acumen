# app/tests/unit/conftest.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from fastapi import Depends
from main import app
from app.db.session import get_db
from app.core.security import azure_ad_dependency

@pytest.fixture
def mock_db_session():
    return MagicMock(spec=Session)

@pytest.fixture
def mock_auth():
    with patch('app.core.security.azure_ad_dependency') as mock_auth:
        mock_auth.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        yield

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}