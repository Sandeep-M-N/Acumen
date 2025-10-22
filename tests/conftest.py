# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from main import app
from app.db.session import get_db,get_files_db
from unittest.mock import patch, MagicMock
from app.core.security import azure_ad_dependency

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def mock_azure_auth():
    # Create a mock that returns test user data
    mock = MagicMock()
    mock.return_value = {
        "UserEmail": "test@example.com",
        "UserName": "Test User",
        "ObjectId": "test-object-id",
        "UserType": "Admin"
    }
    return mock

@pytest.fixture()
def client(db_session, mock_azure_auth):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    def override_get_files_db():
        try:
            yield db_session
        finally:
            db_session.close()

    # Patch the verify_token function to return our mock data
    with patch('app.core.security.verify_token', mock_azure_auth):
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_files_db] = override_get_files_db

        with TestClient(app) as test_client:
            yield test_client

        # Clean up overrides
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_files_db, None)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}