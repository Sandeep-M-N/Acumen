# app/tests/unit/routers/test_projects.py
import pytest
from fastapi import HTTPException, status
from unittest import mock
from unittest.mock import patch, MagicMock,call
from app.api.routers.projects import router
from fastapi.testclient import TestClient
from main import app
from datetime import datetime,date,timezone
from io import BytesIO
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause
from sqlalchemy import text
from typing import List,Optional
from app.db.session import get_db,get_files_db
from app.core.security import azure_ad_dependency
from azure.storage.blob import ContainerClient
from sqlalchemy.sql import text
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.exc import ProgrammingError, OperationalError
import json

client = TestClient(app)

class TestValidateProjectNumberEndpoint:
    @patch('app.api.routers.projects.get_project')
    @patch('app.core.security.verify_token')  # Patch the actual verification function
    def test_validate_project_number_available(self, mock_verify, mock_get_project):
        # Arrange
        mock_get_project.return_value = None
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }

        # Act
        response = client.get(
            "/api/Projects/ValidateProjectNumber",
            params={"ProjectNumber": "NEW001"},
            headers={"Authorization": "Bearer test-token"}  # Must include auth header
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "available": True,
            "message": "Project number is available"
        }
        mock_verify.assert_called_once_with("test-token")  # Verify token was checked
        mock_get_project.assert_called_once()  # Verify DB query was made

    @patch('app.api.routers.projects.get_project')
    @patch('app.core.security.verify_token') 
    def test_validate_project_number_exists(self,mock_verify, mock_get_project):
        # Arrange
        mock_get_project.return_value = MagicMock()  # Simulate existing project
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }

        
        # Act
        response = client.get(
            "/api/Projects/ValidateProjectNumber",
            params={"ProjectNumber": "EXIST001"},
            headers={"Authorization": "Bearer test-token"} 
        )
        
        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "detail": {
                "available": False,
                "message": "Project number already exists"
            }
        }
        mock_get_project.assert_called_once()

class TestGetProjectList:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        
        # Override get_db dependency for all tests
        def override_get_db():
            return self.mock_db
            
        app.dependency_overrides[get_db] = override_get_db
        yield
        # Cleanup
        app.dependency_overrides.pop(get_db, None)

    @patch('app.api.routers.projects.get_all_projects')
    @patch('app.api.routers.projects.get_username_from_user_id')
    @patch('app.api.routers.projects.get_or_create_user')
    @patch('app.core.security.verify_token')
    def test_get_project_list_success(
        self,
        mock_verify,
        mock_get_user,
        mock_get_username,
        mock_get_projects
    ):
        # Arrange - Mock authentication
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }

        # Mock database responses
        mock_get_user.return_value = MagicMock(UserId=1)

        test_project = MagicMock(
            ProjectNumber="TEST001",
            StudyNumber="STUDY001",
            CustomerName="Test Customer",
            CutDate=date(2025, 1, 1),
            ExtractionDate=date(2025, 2, 1),
            IsDatasetUploaded=False,
            CreatedBy=1,
            ModifiedBy=2,
            ModifiedAt=None,
            ProjectStatus="Active",
            CreatedAt=date(2025, 1, 1)
        )
        mock_get_projects.return_value = [test_project]
        mock_get_username.side_effect = ["Creator Name", "Modifier Name"]

        # Act
        response = client.get(
            "/api/Projects/GetProjectList",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["ProjectNumber"] == "TEST001"
        assert data[0]["CreatedByUsername"] == "Creator Name"
        assert data[0]["ModifiedByUsername"] == "Modifier Name"
        
        # Verify mocks were called correctly
        mock_verify.assert_called_once_with("test-token")
        mock_get_user.assert_called_once()
        mock_get_projects.assert_called_once_with(self.mock_db)
        mock_get_username.assert_has_calls([
            call(1, self.mock_db),
            call(2, self.mock_db)
        ])

    @patch('app.api.routers.projects.get_all_projects')
    @patch('app.core.security.verify_token')
    def test_get_project_list_empty(self, mock_verify, mock_get_projects):
        # Arrange
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        mock_get_projects.return_value = []

        # Act
        response = client.get(
            "/api/Projects/GetProjectList",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        mock_get_projects.assert_called_once_with(self.mock_db)

    @patch('app.api.routers.projects.get_all_projects')
    @patch('app.core.security.verify_token')
    def test_get_project_list_error(self, mock_verify, mock_get_projects):
        # Arrange
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        mock_db = MagicMock(spec=Session)
        mock_get_projects.side_effect = Exception("Database error")

        # Act
        response = client.get(
            "/api/Projects/GetProjectList",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": "Error retrieving projects"}

class TestCreateProject:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        self.mock_verify = MagicMock()
        self.mock_user = MagicMock(UserId=1)
        
        # Override dependencies
        def override_get_db():
            return self.mock_db
            
        def override_auth():
            return {
                "UserEmail": "test@example.com",
                "UserName": "Test User",
                "ObjectId": "test-object-id",
                "UserType": "Admin"
            }
            
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[azure_ad_dependency] = override_auth
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()


    @patch('app.api.routers.projects.get_project')
    @patch('app.api.routers.projects.create_project')
    @patch('app.api.routers.projects.process_uploaded_file')
    def test_create_project_success(self, mock_process_file, mock_create_project, mock_get_project):
        # Arrange
        mock_get_project.return_value = None
        mock_process_file.return_value = False
         
        # Create a proper mock response that matches your ProjectCreate model
        project_mock = MagicMock()
        project_mock.ProjectNumber = "NEW001"
        project_mock.StudyNumber = "STUDY001"
        project_mock.CustomerName = "New Customer"
        project_mock.CutDate = date(2025, 1, 1)
        project_mock.ExtractionDate = date(2025, 1, 2)
        project_mock.CreatedBy = 1
        project_mock.ProjectStatus = "Active"  # Add this required field
        project_mock.IsDatasetUploaded = False  # Add this field if needed
        project_mock.UploadedBy = None  # Add this field if needed
        project_mock.UploadedAt = None  # Add this field if needed
        
        mock_create_project.return_value = project_mock

        project_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "STUDY001",
            "CustomerName": "New Customer",
            "CutDate": date(2025, 1, 1).isoformat(),
            "ExtractionDate": date(2025, 1, 2).isoformat(),
        }

        # Act
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["ProjectNumber"] == "NEW001"
        mock_get_project.assert_called_once_with(self.mock_db, "NEW001")
        mock_create_project.assert_called_once()

    @patch('app.api.routers.projects.get_project')
    def test_create_project_invalid_project_number(self, mock_get_project):
        # Arrange
        invalid_data = {
            "ProjectNumber": "TEST&001",
            "StudyNumber": "STUDY001",
            "CustomerName": "Valid Customer",
        }

        # Act
        response = client.post(
            "/api/Projects/CreateProject",
            data=invalid_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 422
        assert "Only underscores (_)" in response.json()["detail"]
        mock_get_project.assert_not_called()

    @patch('app.api.routers.projects.get_project')
    def test_create_project_invalid_customer_name(self, mock_get_project):
        # Arrange
        invalid_data = {
            "ProjectNumber": "VALID_001",
            "StudyNumber": "STUDY001",
            "CustomerName": "John^Doe",
        }

        # Act
        response = client.post(
            "/api/Projects/CreateProject",
            data=invalid_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 422
        assert "Hyphens (-), underscores (_), dots (.), ampersands (&)" in response.json()["detail"]
        mock_get_project.assert_not_called()

    @patch('app.api.routers.projects.get_project')
    def test_create_project_invalid_study_number(self, mock_get_project):
        # Arrange
        invalid_data = {
            "ProjectNumber": "VALID_001",
            "StudyNumber": "STD00.1",
            "CustomerName": "Valid Customer",
        }

        # Act
        response = client.post(
            "/api/Projects/CreateProject",
            data=invalid_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 422
        assert "Only hyphens (-) and underscores (_)" in response.json()["detail"]
        mock_get_project.assert_not_called()

    @patch('app.api.routers.projects.get_project')
    def test_create_project_conflict(self, mock_get_project):
        # Arrange
        mock_get_project.return_value = MagicMock()  # Simulate existing project
        project_data = {
            "ProjectNumber": "EXIST001",
            "StudyNumber": "STUDY001",
            "CustomerName": "New Customer",
            "CutDate": date(2025, 1, 1).isoformat(),
            "ExtractionDate": date(2025, 1, 2).isoformat(),
        }

        # Act
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]
        mock_get_project.assert_called_once_with(self.mock_db, "EXIST001")

    @patch('app.api.routers.projects.get_project')
    @patch('app.api.routers.projects.create_project')
    @patch('app.api.routers.projects.process_uploaded_file')
    def test_create_project_with_files(self, mock_process_file, mock_create_project, mock_get_project):
        # Arrange
        mock_get_project.return_value = None
        mock_process_file.return_value = True
        # Create a properly configured mock that matches your ProjectCreate model
        project_mock = MagicMock()
        project_mock.ProjectNumber = "FILE001"
        project_mock.StudyNumber = "STUDY001"
        project_mock.CustomerName = "File Customer"
        project_mock.CreatedBy = 1
        project_mock.UploadedBy = 1
        project_mock.UploadedAt = datetime.now(timezone.utc)
        project_mock.IsDatasetUploaded = True
        project_mock.ProjectStatus = "Active"  # Required field
        project_mock.CutDate = date(2025, 1, 1)  # Must be date, not datetime
        project_mock.ExtractionDate = date(2025, 1, 2)  # Must be date, not datetime
        
        mock_create_project.return_value = project_mock

        project_data = {
            "ProjectNumber": "FILE001",
            "StudyNumber": "STUDY001",
            "CustomerName": "File Customer",
        }

        # Mock file upload
        files = [("uploaded_files", ("test.txt", b"test content", "text/plain"))]

        # Act
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["IsDatasetUploaded"] == True
        mock_process_file.assert_called_once()

class TestEditProject:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        self.mock_verify = MagicMock()
        self.mock_user = MagicMock(UserId=1)
        
        # Override dependencies
        def override_get_db():
            return self.mock_db
            
        def override_auth():
            return {
                "UserEmail": "test@example.com",
                "UserName": "Test User",
                "ObjectId": "test-object-id",
                "UserType": "Admin"
            }
            
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[azure_ad_dependency] = override_auth
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('app.api.routers.projects.get_project_active')
    @patch('app.api.routers.projects.process_uploaded_file')
    def test_edit_project_success(self, mock_process_file, mock_get_project):
        # Arrange
        project_mock = MagicMock()
        
        # Configure all required fields with proper types
        project_mock.ProjectNumber = "NEW001"
        project_mock.StudyNumber = "STUDY001"
        project_mock.CustomerName = "Old Customer"
        project_mock.CutDate = date(2025, 1, 1)  # Must be date (not datetime)
        project_mock.ExtractionDate = date(2025, 1, 2)  # Must be date (not datetime)
        project_mock.ProjectStatus = "Active"  # String value
        project_mock.CreatedByUsername = "creator"  # String value
        project_mock.ModifiedByUsername = None # String value
        project_mock.DeleteByUsername = None  # String or None
        project_mock.ModifiedBy = None
        project_mock.ModifiedAt = None
        project_mock.IsDatasetUploaded = False

        # Mock the user that will be assigned to ModifiedBy
        user_mock = MagicMock()
        user_mock.UserId = 1  # Set the expected UserId
        
        mock_get_project.return_value = project_mock
        mock_process_file.return_value = True
        with patch('app.api.routers.projects.get_or_create_user') as mock_get_user:
            mock_get_user.return_value = user_mock


            # Proper multipart form data
            data = {
                "ProjectNumber":"NEW001",
                "StudyNumber":"UPDATED001",
                "CustomerName":"New Customer"
            }

            # Act
            response = client.put(
                "/api/Projects/EditProject?ProjectNumber=NEW001",
                data=data,
                headers={"Authorization": "Bearer test-token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["StudyNumber"] == "UPDATED001"
        assert response_data["CustomerName"] == "New Customer"
        mock_get_project.assert_called_once_with(self.mock_db, "NEW001")
        # assert project_mock.ModifiedBy == user_mock.UserId
        # assert isinstance(project_mock.ModifiedAt, datetime)

    @patch('app.api.routers.projects.get_project_active')
    def test_edit_project_invalid_customer_name(self, mock_get_project):
        # Arrange
        mock_get_project.return_value = MagicMock()  # Any project will do for validation test

        invalid_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "STUDY001",
            "CustomerName": "John^Doe",
        }

        # Act
        response = client.put(
            "/api/Projects/EditProject?ProjectNumber=NEW001",
            data=invalid_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 422
        assert "Hyphens (-), underscores (_), dots (.), ampersands (&)" in response.json()["detail"]
        mock_get_project.assert_not_called()  # Validation happens before DB call

    @patch('app.api.routers.projects.get_project_active')
    def test_edit_project_invalid_study_number(self, mock_get_project):
        # Arrange
        mock_get_project.return_value = MagicMock()

        invalid_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "STD00.1",
            "CustomerName": "Valid Customer",
        }

        # Act
        response = client.put(
            "/api/Projects/EditProject?ProjectNumber=NEW001",
            data=invalid_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 422
        assert "Only hyphens (-) and underscores (_)" in response.json()["detail"]
        mock_get_project.assert_not_called()

    @patch('app.api.routers.projects.get_project_active')
    def test_edit_project_not_found(self, mock_get_project):
        # Arrange
        mock_get_project.return_value = None

        update_data = {
            "ProjectNumber": "NONEXISTENT",
            "StudyNumber": "UPDATED_STUDY",
            "CustomerName": "Old_customer"
        }

        # Act
        response = client.put(
            "/api/Projects/EditProject?ProjectNumber=NONEXISTENT",
            data=update_data,
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
        mock_get_project.assert_called_once_with(self.mock_db, "NONEXISTENT")

    @patch('app.api.routers.projects.get_project_active')
    @patch('app.api.routers.projects.process_uploaded_file')
    def test_edit_project_with_files(self, mock_process_file, mock_get_project):
        # Arrange
        # Create a properly configured project mock
        project_mock = MagicMock()
        project_mock.ProjectNumber = "FILE001"
        project_mock.StudyNumber = "STUDY001"
        project_mock.CustomerName = "File Customer"
        project_mock.CutDate = date(2025, 1, 1)
        project_mock.ExtractionDate = date(2025, 1, 2)
        project_mock.ProjectStatus = "Active"
        project_mock.CreatedByUsername = "creator"
        project_mock.ModifiedByUsername = None
        project_mock.DeleteByUsername = None
        project_mock.IsDatasetUploaded = False
        project_mock.UploadedBy = None
        project_mock.UploadedAt = None
        project_mock.ModifiedBy = None
        project_mock.ModifiedAt = None

        mock_get_project.return_value = project_mock
        mock_process_file.return_value = True

        # Prepare form data - must separate regular fields and files
        data = {
            "ProjectNumber": "FILE001",
            "StudyNumber": "STUDY001",
            "CustomerName": "File Customer"
        }
        
        # Prepare file upload
        files = {
            "uploaded_files": ("test.txt", b"test content", "text/plain")
        }

        # Act - Use both data and files parameters
        response = client.put(
            "/api/Projects/EditProject",
            params={"ProjectNumber": "FILE001"},  # Query parameter
            data=data,  # Regular form fields
            files=files,  # File uploads
            headers={"Authorization": "Bearer test-token"}
        )

        # Debug: Print response if needed
        print(response.json())

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert project_mock.IsDatasetUploaded is True
        assert project_mock.UploadedBy is not None
        assert isinstance(project_mock.UploadedAt, datetime)
        mock_process_file.assert_called_once()

class TestDeleteProject:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        self.mock_verify = MagicMock()
        
        # Override dependencies
        def override_get_db():
            return self.mock_db
            
        def override_auth():
            return {
                "UserEmail": "test@example.com",
                "UserName": "Test User",
                "ObjectId": "test-object-id",
                "UserType": "Admin"
            }
            
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[azure_ad_dependency] = override_auth
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('app.api.routers.projects.get_project')
    def test_delete_project_success(self, mock_get_project):
        # Arrange
        # Create a mock project that is active (not deleted)
        project_mock = MagicMock()
        project_mock.RecordStatus = 'A'
        project_mock.DeletedBy = None
        project_mock.DeletedAt = None
        
        # Create a mock user
        user_mock = MagicMock()
        user_mock.UserId = 1
        
        mock_get_project.return_value = project_mock
        
        # Mock the user query
        with patch('app.api.routers.projects.get_or_create_user') as mock_get_user:
            mock_get_user.return_value = user_mock

            # Act
            response = client.request(
                "DELETE",
                "/api/Projects/DeleteProject",
                json={"project_numbers": ["DELETE001"]},
                headers={"Authorization": "Bearer test-token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Projects deleted successfully"
        assert project_mock.RecordStatus == 'D'
        # assert project_mock.DeletedBy == user_mock.UserId
        # assert isinstance(project_mock.DeletedAt, datetime)
        self.mock_db.commit.assert_called_once()

    @patch('app.api.routers.projects.get_project')
    def test_delete_project_not_found(self, mock_get_project):
        # Arrange
        mock_get_project.return_value = None
        # Create a fresh mock for the database session
        mock_db = MagicMock(spec=Session)

        # Override the get_db dependency for this test
        def override_get_db():
            return mock_db
        app.dependency_overrides[get_db] = override_get_db
        # Act
        response = client.request(
            "DELETE",
            "/api/Projects/DeleteProject",
            json={"project_numbers": ["DELETE002"]},
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "project numbers were not found" in response.json()["detail"]["message"]
        # Verify no commit was called
        commit_calls = [call for call in self.mock_db.method_calls if call[0] == 'commit']
        assert len(commit_calls) == 0, f"Expected no commit, but found {len(commit_calls)} commit calls"

        # Clean up the override
        app.dependency_overrides.pop(get_db, None)

    @patch('app.api.routers.projects.get_project')
    def test_delete_project_already_deleted(self, mock_get_project):
        # Arrange
        # Create a mock project that is already deleted
        project_mock = MagicMock()
        project_mock.RecordStatus = 'D'
        project_mock.DeletedBy = 1
        project_mock.DeletedAt = datetime.now(timezone.utc)
        
        mock_get_project.return_value = project_mock

         # Create a fresh mock for the database session
        mock_db = MagicMock(spec=Session)

        # Override the get_db dependency for this test
        def override_get_db():
            return mock_db
        app.dependency_overrides[get_db] = override_get_db
        
        # Act
        response = client.request(
            "DELETE",
            "/api/Projects/DeleteProject",
            json={"project_numbers": ["DELETE001"]},
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already deleted" in response.json()["detail"]["message"]
        # Verify no commit was called
        commit_calls = [call for call in self.mock_db.method_calls if call[0] == 'commit']
        assert len(commit_calls) == 0, f"Expected no commit, but found {len(commit_calls)} commit calls"

    @patch('app.api.routers.projects.get_project')
    def test_delete_multiple_projects_mixed_status(self, mock_get_project):
        # Arrange
        # Setup different project states
        active_project = MagicMock()
        active_project.RecordStatus = 'A'
        active_project.DeletedBy = None
        active_project.DeletedAt = None
        
        deleted_project = MagicMock()
        deleted_project.RecordStatus = 'D'
        deleted_project.DeletedBy = 1
        deleted_project.DeletedAt = datetime.now(timezone.utc)
        
        # Mock get_project to return different values
        def get_project_side_effect(db, ProjectNumber):
            if ProjectNumber == "ACTIVE001":
                return active_project
            elif ProjectNumber == "DELETED001":
                return deleted_project
            else:
                return None
                
        mock_get_project.side_effect = get_project_side_effect
        
        # Mock user
        user_mock = MagicMock()
        user_mock.UserId = 1
        
        with patch('app.api.routers.projects.get_or_create_user') as mock_get_user:
            mock_get_user.return_value = user_mock

            # Act
            response = client.request(
                "DELETE",
                "/api/Projects/DeleteProject",
                json={"project_numbers": ["ACTIVE001", "DELETED001", "MISSING001"]},
                headers={"Authorization": "Bearer test-token"}
            )

        # Assert - Should prioritize 404 over 409
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "project numbers were not found" in response.json()["detail"]["message"]
        assert "MISSING001" in response.json()["detail"]["not_found"]
        self.mock_db.commit.assert_called_once()

class TestGetDeletedProjectList:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        self.mock_verify = MagicMock()
        
        # Override dependencies
        def override_get_db():
            return self.mock_db
            
        def override_auth():
            return {
                "UserEmail": "test@example.com",
                "UserName": "Test User",
                "ObjectId": "test-object-id",
                "UserType": "Admin"
            }
            
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[azure_ad_dependency] = override_auth
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('app.api.routers.projects.get_deleted_projects')
    @patch('app.api.routers.projects.get_username_from_user_id')
    def test_get_deleted_project_list_success(self, mock_get_username, mock_get_deleted_projects):
        # Arrange
        # Create a mock deleted project
        project_mock = MagicMock()
        project_mock.ProjectNumber = "DELETED001"
        project_mock.StudyNumber = "STUDY001"
        project_mock.CustomerName = "Deleted Customer"
        project_mock.CutDate = date(2025, 1, 1)
        project_mock.ExtractionDate = date(2025, 1, 2)
        project_mock.IsDatasetUploaded = False
        project_mock.CreatedBy = 1
        project_mock.ModifiedBy = 1
        project_mock.ProjectStatus = "Deleted"
        project_mock.CreatedAt = datetime.now(timezone.utc)
        project_mock.ModifiedAt = datetime.now(timezone.utc)
        project_mock.DeletedBy = 1
        project_mock.DeletedAt = datetime.now(timezone.utc)
        project_mock.RecordStatus = "D"

        mock_get_deleted_projects.return_value = [project_mock]
        mock_get_username.side_effect = ["Test User", "Test User", "Test User"]  # For created/modified/deleted usernames

        # Act
        response = client.get(
            "/api/Projects/GetDeletedProjectList",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["ProjectNumber"] == "DELETED001"
        assert data[0]["DeleteByUsername"] == "Test User"
        mock_get_deleted_projects.assert_called_once_with(self.mock_db)
        assert mock_get_username.call_count == 3  # Called for created, modified, deleted usernames

    @patch('app.api.routers.projects.get_deleted_projects')
    def test_get_deleted_project_list_empty(self, mock_get_deleted_projects):
        # Arrange
        mock_get_deleted_projects.return_value = []

        # Act
        response = client.get(
            "/api/Projects/GetDeletedProjectList",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        mock_get_deleted_projects.assert_called_once_with(self.mock_db)

class TestGetProjectInfo:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        
        # Override get_db dependency
        def override_get_db():
            return self.mock_db
            
        app.dependency_overrides[get_db] = override_get_db
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('app.api.routers.projects.get_project_active')
    @patch('app.api.routers.projects.get_username_from_user_id')
    @patch('app.core.security.verify_token')
    def test_get_project_info_success(self, mock_verify, mock_get_username, mock_get_project):
        # Arrange
        # Mock authentication to return valid user data
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }

        # Create a mock project
        project_mock = MagicMock()
        project_mock.ProjectNumber = "INFO001"
        project_mock.StudyNumber = "STUDY001"
        project_mock.CustomerName = "Test Customer"
        project_mock.CutDate = date(2025, 1, 1)
        project_mock.ExtractionDate = date(2025, 1, 2)
        project_mock.CreatedBy = 1
        project_mock.CreatedAt = datetime.now(timezone.utc)
        project_mock.ModifiedBy = 1
        project_mock.ModifiedAt = datetime.now(timezone.utc)

        mock_get_project.return_value = project_mock
        mock_get_username.side_effect = ["Test User", "Test User"]  # For created/modified usernames

        # Act
        response = client.get(
            "/api/Projects/GetProjectInfo?ProjectNumber=INFO001",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ProjectNumber"] == "INFO001"
        assert data["CreatedByUsername"] == "Test User"
        mock_get_project.assert_called_once_with(self.mock_db, ProjectNumber="INFO001")
        assert mock_get_username.call_count == 2
        mock_verify.assert_called_once_with("test-token")

    @patch('app.api.routers.projects.get_project_active')
    @patch('app.core.security.verify_token')
    def test_get_project_info_not_found(self,mock_verify, mock_get_project):
        # Mock authentication to return valid user data
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        # Arrange
        mock_get_project.return_value = None

        # Act
        response = client.get(
            "/api/Projects/GetProjectInfo?ProjectNumber=NONEXISTENT",
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
        mock_get_project.assert_called_once_with(self.mock_db, ProjectNumber="NONEXISTENT")
        mock_verify.assert_called_once_with("test-token")

class TestGetProjectFolderFiles:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        self.mock_verify = MagicMock()
        
        # Override dependencies
        def override_get_db():
            return self.mock_db
            
        def override_auth():
            return {
                "UserEmail": "test@example.com",
                "UserName": "Test User",
                "ObjectId": "test-object-id",
                "UserType": "Admin"
            }
            
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[azure_ad_dependency] = override_auth
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('app.api.routers.projects.ContainerClient')
    @patch('app.api.routers.projects.get_project_active')
    @patch('app.api.routers.projects.get_username_from_user_id')
    def test_get_project_files_success(self, mock_get_username, mock_get_project, mock_container):
        # Arrange
        # Mock project
        project_mock = MagicMock()
        project_mock.UploadedBy = 1
        project_mock.UploadedAt = datetime.now(timezone.utc)
        mock_get_project.return_value = project_mock
        mock_get_username.return_value = "Test User"

        # Mock Azure Blob
        mock_blob = MagicMock()
        mock_blob.name = "base_path/TEST001/SDTM/test_file.sas7bdat"
        mock_blob.size = 1024
        
        mock_client = MagicMock()
        mock_client.list_blobs.return_value = [mock_blob]
        mock_container.from_connection_string.return_value = mock_client

        # Mock settings
        with patch('app.api.routers.projects.settings') as mock_settings:
            mock_settings.BASE_BLOB_PATH = "base_path"
            mock_settings.AZURE_STORAGE_CONTAINER_NAME = "test-container"
            mock_settings.AZURE_STORAGE_CONNECTION_STRING = "test-conn-str"

            # Act
            response = client.get(
                "/api/Projects/GetProjectFolderFiles",
                params={"ProjectNumber": "TEST001", "folder": "SDTM"},
                headers={"Authorization": "Bearer test-token"}
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "SDTM" in data
        assert len(data["SDTM"]) == 1
        assert data["SDTM"][0]["name"] == "test_file"
        assert data["SDTM"][0]["type"] == "sas7bdat"
        mock_container.from_connection_string.assert_called_once_with(
            conn_str="test-conn-str",
            container_name="test-container"
        )

    @patch('app.api.routers.projects.get_project_active')
    def test_get_files_project_not_found(self, mock_get_project):
        # Arrange
        mock_get_project.return_value = None

        # Act
        response = client.get(
            "/api/Projects/GetProjectFolderFiles",
            params={"ProjectNumber": "NONEXISTENT", "folder": "SDTM"},
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @patch('app.api.routers.projects.ContainerClient')
    @patch('app.api.routers.projects.get_project_active')
    def test_get_files_no_files_found(self, mock_get_project, mock_container):
        # Arrange
        project_mock = MagicMock()
        mock_get_project.return_value = project_mock
        
        mock_client = MagicMock()
        mock_client.list_blobs.return_value = []
        mock_container.from_connection_string.return_value = mock_client

        # Act
        response = client.get(
            "/api/Projects/GetProjectFolderFiles",
            params={"ProjectNumber": "TEST001", "folder": "SDTM"},
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "No files found for project 'TEST001' in folder 'SDTM'"
        }

    @patch('app.api.routers.projects.ContainerClient')
    @patch('app.api.routers.projects.get_project_active')
    def test_get_files_azure_error(self, mock_get_project, mock_container):
        # Arrange
        project_mock = MagicMock()
        mock_get_project.return_value = project_mock
        mock_container.from_connection_string.side_effect = Exception("Azure connection failed")

        # Act
        response = client.get(
            "/api/Projects/GetProjectFolderFiles",
            params={"ProjectNumber": "TEST001", "folder": "SDTM"},
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Azure Blob" in response.json()["detail"]

class TestDownloadExcelFromDB:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        self.mock_db = MagicMock(spec=Session)
        self.mock_verify = MagicMock()
        
        # Override dependencies
        def override_get_db():
            return self.mock_db
            
        def override_auth():
            return {
                "UserEmail": "test@example.com",
                "UserName": "Test User", 
                "ObjectId": "test-object-id",
                "UserType": "Admin"
            }
            
        app.dependency_overrides[get_files_db] = override_get_db
        app.dependency_overrides[azure_ad_dependency] = override_auth
        
        yield
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('app.api.routers.projects.pd.read_sql')
    @patch('app.api.routers.projects.time.time')
    def test_download_excel_success(self, mock_time, mock_read_sql):
        # Arrange
        # Create a generator that will keep returning increasing values
        def time_generator():
            t = 1000
            while True:
                yield t
                t += 1
        mock_time.side_effect = time_generator()

        # Mock DataFrame
        test_data = pd.DataFrame({
            'subject_id': [101, 102, 103],
            'gender': ['M', 'F', 'M'],
            'age': [25, 32, 41]
        })
        mock_read_sql.return_value = test_data

        # Mock database execute (table exists check)
        mock_execute = MagicMock()
        mock_execute.fetchone.return_value = [1]
        self.mock_db.execute.return_value = mock_execute

        # Mock the database engine/bind
        mock_engine = MagicMock()
        self.mock_db.bind = mock_engine

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM", 
                "filename": "dm"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment; filename=dm.xlsx" in response.headers["content-disposition"]
        assert "X-Processing-Time" in response.headers

        # Verify Excel content
        content = b"".join(response.iter_bytes())
        with BytesIO(content) as excel_file:
            df = pd.read_excel(excel_file)
            assert df.shape == (3, 3)
            assert list(df['subject_id']) == [101, 102, 103]

        # Verify database calls - use assert_called_once() and check the SQL text separately
        assert self.mock_db.execute.call_count == 1
        call_args = self.mock_db.execute.call_args[0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], TextClause)
        assert str(call_args[0]) == "SELECT 1 FROM [test001_sdtm].[dm] WHERE 1=0"
    def test_download_nonexistent_table(self):
        # Arrange
        self.mock_db.execute.side_effect = Exception("Table not found")

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "MISSING",
                "foldername": "SDTM",
                "filename": "nonexistent"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Table 'missing_sdtm.nonexistent' not found" in response.json()["detail"]

    @patch('app.api.routers.projects.pd.read_sql')
    def test_download_empty_table(self, mock_read_sql):
        # Arrange
        mock_read_sql.return_value = pd.DataFrame()
        mock_execute = MagicMock()
        mock_execute.fetchone.return_value = [1]
        
        # Mock the database session with bind attribute
        self.mock_db.execute.return_value = mock_execute
        self.mock_db.bind = MagicMock()  # Add this line to mock the bind attribute

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "empty"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 200
        content = b"".join(response.iter_bytes())  # Proper way to read streaming response
        with BytesIO(content) as excel_file:
            df = pd.read_excel(excel_file)
            assert df.empty
        
        # Verify database calls
        assert self.mock_db.execute.call_count == 1
        called_sql = str(self.mock_db.execute.call_args[0][0])
        expected_sql = "SELECT 1 FROM [test001_sdtm].[empty] WHERE 1=0"
        assert called_sql.lower().replace(" ", "") == expected_sql.lower().replace(" ", "")

    @patch('app.api.routers.projects.pd.read_sql')
    def test_download_large_table(self, mock_read_sql):
        # Arrange
        test_data = pd.DataFrame({
            'col1': range(1000),
            'col2': ['value'] * 1000
        })
        mock_read_sql.return_value = test_data
        mock_execute = MagicMock()
        mock_execute.fetchone.return_value = [1]
        
        # Mock the complete database session with bind attribute
        self.mock_db.execute.return_value = mock_execute
        self.mock_db.bind = MagicMock()  # This is the critical missing piece

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "large"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 200
        content_length = int(response.headers.get("content-length", 0))
        assert content_length > 10000  # Verify the file isn't empty
        
        # Additional verification
        content = b"".join(response.iter_bytes())
        with BytesIO(content) as excel_file:
            df = pd.read_excel(excel_file)
            assert df.shape == (1000, 2)  # Verify all data was included
            assert list(df.columns) == ['col1', 'col2']
        
        # Verify database calls
        assert self.mock_db.execute.call_count == 1
        called_sql = str(self.mock_db.execute.call_args[0][0])
        expected_sql = "SELECT 1 FROM [test001_sdtm].[large] WHERE 1=0"
        assert called_sql.lower().replace(" ", "") == expected_sql.lower().replace(" ", "")

    @patch('app.api.routers.projects.pd.read_sql')
    def test_download_special_chars(self, mock_read_sql):
        # Arrange
        test_data = pd.DataFrame({
            'col1': [1, 2],
            'col2': ['áéíóú', '©®™']
        })
        mock_read_sql.return_value = test_data
        
        # Mock database execute (table exists check)
        mock_execute = MagicMock()
        mock_execute.fetchone.return_value = [1]
        self.mock_db.execute.return_value = mock_execute
        
        # Mock the database engine/bind - THIS IS THE CRITICAL FIX
        self.mock_db.bind = MagicMock()

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM", 
                "filename": "special"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 200
        
        # Properly handle streaming response
        content = b"".join(response.iter_bytes())
        with BytesIO(content) as excel_file:
            df = pd.read_excel(excel_file)
            
            # Verify special characters are preserved
            assert 'áéíóú' in df['col2'].values
            assert '©®™' in df['col2'].values
        
        # Verify database calls
        assert self.mock_db.execute.call_count == 1
        called_sql = str(self.mock_db.execute.call_args[0][0])
        expected_sql = "SELECT 1 FROM [test001_sdtm].[special] WHERE 1=0"
        assert called_sql.lower().replace(" ", "") == expected_sql.lower().replace(" ", "")

    @patch('app.api.routers.projects.pd.read_sql')
    def test_download_with_nan_values(self, mock_read_sql):
        # Arrange
        test_data = pd.DataFrame({
            'col1': [1, None, 3],
            'col2': ['a', None, 'c']
        })
        mock_read_sql.return_value = test_data
        
        # Mock database execute (table exists check)
        mock_execute = MagicMock()
        mock_execute.fetchone.return_value = [1]
        self.mock_db.execute.return_value = mock_execute
        
        # Mock the database engine/bind - THIS IS THE CRITICAL FIX
        self.mock_db.bind = MagicMock()

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM", 
                "filename": "nan"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 200
        
        # Properly handle streaming response
        content = b"".join(response.iter_bytes())
        with BytesIO(content) as excel_file:
            df = pd.read_excel(excel_file)
            
            # Verify NaN values are preserved
            assert df.isna().sum().sum() == 2  # Total NaN values
            assert pd.isna(df.at[1, 'col1'])  # Verify specific NaN
            assert pd.isna(df.at[1, 'col2'])  # Verify specific NaN
        
        # Verify database calls
        assert self.mock_db.execute.call_count == 1
        called_sql = str(self.mock_db.execute.call_args[0][0])
        expected_sql = "SELECT 1 FROM [test001_sdtm].[nan] WHERE 1=0"
        assert called_sql.lower().replace(" ", "") == expected_sql.lower().replace(" ", "")

    @patch('app.api.routers.projects.pd.read_sql', side_effect=Exception("Database error"))
    def test_database_error(self, mock_read_sql):
        # Arrange
        mock_execute = MagicMock()
        mock_execute.fetchone.return_value = [1]
        self.mock_db.execute.return_value = mock_execute

        # Act
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "error"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Assert
        assert response.status_code == 500
        assert "Excel generation failed" in response.json()["detail"]

    def test_missing_parameters(self):
        # Test missing project_number
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "foldername": "SDTM",
                "filename": "test"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test missing foldername
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "filename": "test"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test missing filename
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestDeleteBlobFiles:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup common mocks for all tests"""
        # Azure Blob Storage
        self.mock_container = MagicMock()
        self.mock_blob_service = MagicMock()
        self.mock_blob_service.get_container_client.return_value = self.mock_container

        # Database
        self.mock_db = MagicMock(spec=Session)
        self.mock_db_session = self.mock_db  # for inner patch

        # Patch blob client
        self.blob_patcher = patch(
            "azure.storage.blob.BlobServiceClient.from_connection_string",
            return_value=self.mock_blob_service
        )
        self.blob_patcher.start()

        # Override FastAPI dependency
        def override_get_db():
            return self.mock_db
        app.dependency_overrides[get_files_db] = override_get_db

        yield

        # Cleanup
        self.blob_patcher.stop()
        app.dependency_overrides.clear()

    def test_delete_blob_files_success(self, client, auth_headers):
        # Arrange
        self.mock_container.delete_blob.return_value = None

        # Mock DB execution result
        mock_result = mock.MagicMock()
        mock_result.rowcount = 1  # Simulate successful table drop

        # We need to patch both the database dependency and the text() function
        with mock.patch('app.api.routers.projects.get_files_db', return_value=self.mock_db_session), \
             mock.patch('app.api.routers.projects.text') as mock_text:

            # Set up the mock text object with a valid SQL statement
            mock_text.return_value = text("DROP TABLE IF EXISTS test001_sdtm_dm")

            # Configure the mock session
            self.mock_db_session.execute.return_value = mock_result
            self.mock_db_session.commit.return_value = None

            # Act
            response = client.request(
                method="DELETE",
                url="/api/Projects/DeleteBlobFiles",
                headers={
                    **auth_headers,
                    "Content-Type": "application/json"
                },
                content=json.dumps([{
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "name": "dm",
                    "type": "xpt"
                }])
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        print("Response body:", body)  # Optional debug

        assert len(body["deleted_blobs"]) == 1
        assert body["not_found_blobs"] == []
        assert len(body["dropped_tables"]) == 1
        assert "test001_sdtm.dm" in body["dropped_tables"][0]
        assert body["failed_to_drop_tables"] == []

    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_blob_not_found_but_table_dropped(self, mock_blob_client_factory, client, db_session, auth_headers):
        # Mock Azure blob delete failure
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_blob_service.get_container_client.return_value = mock_container
        mock_container.delete_blob.side_effect = Exception("Blob not found")
        mock_blob_client_factory.return_value = mock_blob_service

        # Mock DB drop success
        with patch.object(db_session, "execute") as mock_execute, patch.object(db_session, "commit") as mock_commit:
            mock_execute.return_value = None

            # --- Act ---
            response = client.request(
                method="DELETE",
                url="/api/Projects/DeleteBlobFiles",
                headers={
                    **auth_headers,
                    "Content-Type": "application/json"
                },
                content=json.dumps([{
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "name": "dm",
                    "type": "xpt"
                }])
            )

            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert len(body["not_found_blobs"]) == 1
            assert len(body["dropped_tables"]) == 1
            assert body["failed_to_drop_tables"] == []
            assert body["deleted_blobs"] == []
            assert "error_message" in body["not_found_blobs"][0]
            assert "File not found or deletion failed" in body["not_found_blobs"][0]["error_message"]

    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_blob_deleted_but_table_drop_fails(self, mock_blob_client_factory, client, db_session, auth_headers):
        # Mock Azure blob delete success
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_blob_service.get_container_client.return_value = mock_container
        mock_container.delete_blob.return_value = None
        mock_blob_client_factory.return_value = mock_blob_service

        # Mock DB drop failure
        with patch.object(db_session, "execute") as mock_execute, patch.object(db_session, "commit") as mock_commit:
            mock_execute.side_effect = Exception("DB drop error")

            # --- Act ---
            response = client.request(
                method="DELETE",
                url="/api/Projects/DeleteBlobFiles",
                headers={
                    **auth_headers,
                    "Content-Type": "application/json"
                },
                content=json.dumps([{
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "name": "dm",
                    "type": "xpt"
                }])
            )

            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert len(body["deleted_blobs"]) == 1
            assert body["not_found_blobs"] == []
            assert len(body["failed_to_drop_tables"]) == 1
            assert body["dropped_tables"] == []
            assert "error" in body["failed_to_drop_tables"][0]
            assert "DB drop error" in body["failed_to_drop_tables"][0]["error"]

    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_both_blob_and_table_fail(self, mock_blob_client_factory, client, db_session, auth_headers):
        # Both blob delete and db drop fail
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_blob_service.get_container_client.return_value = mock_container
        mock_container.delete_blob.side_effect = Exception("Blob not found")
        mock_blob_client_factory.return_value = mock_blob_service

        with patch.object(db_session, "execute") as mock_execute, patch.object(db_session, "commit") as mock_commit:
            mock_execute.side_effect = Exception("Drop failed")

            # --- Act ---
            response = client.request(
                method="DELETE",
                url="/api/Projects/DeleteBlobFiles",
                headers={
                    **auth_headers,
                    "Content-Type": "application/json"
                },
                content=json.dumps([{
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "name": "dm",
                    "type": "xpt"
                }])
            )

            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert len(body["not_found_blobs"]) == 1
            assert len(body["failed_to_drop_tables"]) == 1
            assert body["deleted_blobs"] == []
            assert body["dropped_tables"] == []
            assert "error" in body["failed_to_drop_tables"][0]
            assert "error_message" in body["not_found_blobs"][0]

    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_multiple_files_mixed_results(self, mock_blob_client_factory, client, db_session, auth_headers):
        # Test with multiple files with mixed results
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_blob_service.get_container_client.return_value = mock_container
        mock_blob_client_factory.return_value = mock_blob_service
        
        # First call succeeds, second fails
        mock_container.delete_blob.side_effect = [None, Exception("Blob not found")]

        # First drop succeeds, second fails
        with patch.object(db_session, "execute") as mock_execute, patch.object(db_session, "commit") as mock_commit:
            mock_execute.side_effect = [None, Exception("Drop failed")]

            # --- Act ---
            response = client.request(
                method="DELETE",
                url="/api/Projects/DeleteBlobFiles",
                headers={
                    **auth_headers,
                    "Content-Type": "application/json"
                },
                content=json.dumps([
                    {
                        "project_number": "TEST001",
                        "foldername": "SDTM",
                        "name": "dm",
                        "type": "xpt"
                    },
                    {
                        "project_number": "TEST001",
                        "foldername": "ADAM",
                        "name": "adae",
                        "type": "xpt"
                    }
                ])
            )

            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert len(body["deleted_blobs"]) == 1
            assert len(body["not_found_blobs"]) == 1
            assert len(body["dropped_tables"]) == 1
            assert len(body["failed_to_drop_tables"]) == 1

    def test_invalid_input_format(self, client, auth_headers):
        # Test with invalid input format
        response = client.request(
            method="DELETE",
            url="/api/Projects/DeleteBlobFiles",
            headers={
                **auth_headers,
                "Content-Type": "application/json"
            },
            content=json.dumps({"invalid": "format"})  # Not a list
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_fields(self, client, auth_headers):
        # Test with missing required fields
        response = client.request(
            method="DELETE",
            url="/api/Projects/DeleteBlobFiles",
            headers={
                **auth_headers,
                "Content-Type": "application/json"
            },
            content=json.dumps([{
                "foldername": "SDTM",
                "name": "dm"
                # Missing project_number and type
            }])
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

# Mock DB session
class MockSession:
    def bind(self):
        return "mock_engine"

# Setup the app client
client = TestClient(app)

class TestViewSasDatasets:
    def setup_method(self):
        """Setup common mocks for all tests"""
        self.mock_db_session = MockSession()
        self.db_patcher = patch("app.api.routers.projects.get_files_db", return_value=self.mock_db_session)
        self.db_patcher.start()

    def teardown_method(self):
        """Cleanup after each test"""
        self.db_patcher.stop()

    @pytest.mark.parametrize("page, page_size, expected_page, expected_page_size", [
        (1, 2, 1, 2),
        (2, 5, 2, 5),
    ])
    @patch("pandas.read_sql")
    @patch('app.core.security.verify_token')
    def test_view_sas_datasets_success(
        self,
        mock_verify,
        mock_read_sql,
        page,
        page_size,
        expected_page,
        expected_page_size
    ):
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        # Mock data
        sample_data = pd.DataFrame([
            {"subject_id": 1, "gender": "M"},
            {"subject_id": 2, "gender": "F"}
        ])
        sample_total = pd.DataFrame([{"total": 2}])

        # Return different values for the two calls to `read_sql`
        mock_read_sql.side_effect = [sample_data, sample_total]

        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "dm",
                "page": page,
                "page_size": page_size
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == expected_page
        assert data["page_size"] == expected_page_size
        assert data["total"] == 2
        assert data["data"] == [
            {"subject_id": 1, "gender": "M"},
            {"subject_id": 2, "gender": "F"}
        ]

    @patch("pandas.read_sql", side_effect=ProgrammingError("SELECT", {}, None))
    @patch('app.core.security.verify_token')
    def test_view_sas_datasets_table_not_found(self,mock_verify, mock_read_sql):
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "missing_table"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]

    @patch("pandas.read_sql", side_effect=OperationalError("SELECT", {}, None))
    @patch('app.core.security.verify_token')
    def test_view_sas_datasets_operational_error(self,mock_verify, mock_read_sql):
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "dm"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]

    @patch("pandas.read_sql", side_effect=Exception("Something went wrong"))
    @patch('app.core.security.verify_token')
    def test_view_sas_datasets_internal_error(self,mock_verify, mock_read_sql):
        mock_verify.return_value = {
            "UserEmail": "test@example.com",
            "UserName": "Test User",
            "ObjectId": "test-object-id",
            "UserType": "Admin"
        }
        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "dm"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 500
        assert "Unexpected error" in response.json()["detail"]