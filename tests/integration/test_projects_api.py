# tests/integration/test_projects.py
import pytest
from fastapi import status
from io import BytesIO
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone
from app.models.user import User, Project
from app.models.user import User,UserLLMConfig, LLMProvider, LLMModel
from tests.utils.test_data import create_test_user, create_test_project
from azure.storage.blob import BlobProperties
from app.core.config import settings
import os
import json
import pandas as pd
from sqlalchemy import text
import time
from sqlalchemy.exc import ProgrammingError, OperationalError



# tests/integration/test_projects.py
class TestValidateProjectNumber:
    def test_validate_project_number_available(self, client, auth_headers):
        """Test that a new project number is available"""
        response = client.get(
            "/api/Projects/ValidateProjectNumber",
            params={"ProjectNumber": "NEW001"},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "available": True,
            "message": "Project number is available"
        }

    def test_validate_project_number_exists(self, client, db_session, auth_headers):
        """Test that an existing project number returns conflict"""
        user = create_test_user(db_session)
        create_test_project(db_session, "EXIST001", user.UserId)
        response = client.get(
            "/api/Projects/ValidateProjectNumber",
            params={"ProjectNumber": "EXIST001"},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
         "detail": {
            "available": False,
            "message": "Project number already exists"
        }
    }

class TestGetProjectList:
    def test_get_project_list_success(self, client, db_session, auth_headers):
        """Test retrieving active projects"""
        # First create the required LLM provider and model
        provider = LLMProvider(
            Name=settings.LLMProvider,  # "Azure OpenAI"
            # CreatedAt=datetime.now(timezone.utc)
        )
        db_session.add(provider)
        db_session.commit()
        
        model = LLMModel(
            ModelName=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            ProviderId=provider.Id,
            # CreatedAt=datetime.now(timezone.utc)
        )
        db_session.add(model)
        db_session.commit()
        
        # Now create the test user and project
        user = create_test_user(db_session)
        project = create_test_project(db_session, "TEST001", user.UserId)
        
        response = client.get(
            "/api/Projects/GetProjectList",
            headers=auth_headers
        )
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["ProjectNumber"] == "TEST001"
        assert data[0]["CreatedByUsername"] == "Test User"

    def test_get_project_list_empty(self, client,db_session, auth_headers):

        """Test empty project list"""
        # First create the required LLM provider and model
        provider = LLMProvider(
            Name=settings.LLMProvider,  # "Azure OpenAI"
            # CreatedAt=datetime.now(timezone.utc)
        )
        db_session.add(provider)
        db_session.commit()
        
        model = LLMModel(
            ModelName=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            ProviderId=provider.Id,
            # CreatedAt=datetime.now(timezone.utc)
        )
        db_session.add(model)
        db_session.commit()
        response = client.get(
            "/api/Projects/GetProjectList",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

class TestCreateProject:
    def test_create_project_success(self, client, db_session, auth_headers):
        """Test successful project creation"""
        user = create_test_user(db_session)
        
        project_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "STUDY001",
            "CustomerName": "New Customer",
            "CutDate": date(2025, 1, 1).isoformat(),
            "ExtractionDate": date(2025, 1, 2).isoformat(),
        }
        
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["ProjectNumber"] == "NEW001"
    
    def test_create_project_invalid_project_number(self, client, db_session, auth_headers):
        user = create_test_user(db_session)
        
        project_data = {
            "ProjectNumber": "TEST&001",
            "StudyNumber": "STUDY001",
            "CustomerName": "Valid Customer",
        }
        
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Only underscores (_)" in response.json()["detail"]
    def test_create_project_invalid_customer_name(self, client, db_session, auth_headers):
        user = create_test_user(db_session)
        
        project_data = {
            "ProjectNumber": "VALID_001",
            "StudyNumber": "STUDY001",
            "CustomerName": "John^Doe",
        }
        
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Hyphens (-), underscores (_), dots (.), ampersands (&)" in response.json()["detail"]
    def test_create_project_invalid_study_number(self, client, db_session, auth_headers):
        user = create_test_user(db_session)
        
        project_data = {
            "ProjectNumber": "VALID_001",
            "StudyNumber": "STD00.1",
            "CustomerName": "Valid Customer",
        }
        
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Only hyphens (-) and underscores (_)" in response.json()["detail"]

    def test_create_project_conflict(self, client, db_session, auth_headers):
        """Test creating duplicate project"""
        user = create_test_user(db_session)
        create_test_project(db_session, "EXIST001", user.UserId)
        
        project_data = {
            "ProjectNumber": "EXIST001",
            "StudyNumber": "STUDY001",
            "CustomerName": "New Customer",
            "CutDate": date(2025, 1, 1).isoformat(),
            "ExtractionDate": date(2025, 1, 2).isoformat(),
        }
        
        response = client.post(
            "/api/Projects/CreateProject",
            data=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

class TestEditProject:
    def test_edit_project_success(self, client, db_session, auth_headers):
        """Test successful project edit"""
        user = create_test_user(db_session)
        project = create_test_project(db_session, "NEW001", user.UserId)

        update_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "UPDATED001",
            "CustomerName":"New_customer"
        }
        
        response = client.put(
            "/api/Projects/EditProject?ProjectNumber=NEW001",
            data=update_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["StudyNumber"] == "UPDATED001"
        assert data["CustomerName"] == "New_customer" 
        # assert data["ModifiedBy"] == user.UserId


    def test_edit_project_invalid_customer_name(self, client, db_session, auth_headers):
        user = create_test_user(db_session)
        create_test_project(db_session, "NEW001", user.UserId)

        update_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "STUDY001",
            "CustomerName": "John^Doe",
        }
        
        response = client.put(
            f"/api/Projects/EditProject?ProjectNumber=NEW001",
            data=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Hyphens (-), underscores (_), dots (.), ampersands (&)" in response.json()["detail"]

    def test_edit_project_invalid_study_number(self, client, db_session, auth_headers):
        user = create_test_user(db_session)
        create_test_project(db_session, "NEW001", user.UserId)

        update_data = {
            "ProjectNumber": "NEW001",
            "StudyNumber": "STD00.1",
            "CustomerName": "Valid Customer",
        }
        
        response = client.put(
            f"/api/Projects/EditProject?ProjectNumber=NEW001",
            data=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Only hyphens (-) and underscores (_)" in response.json()["detail"]

    def test_edit_project_not_found(self, client, auth_headers):
        """Test editing non-existent project"""
        update_data = {
            "ProjectNumber": "NONEXISTENT",
            "StudyNumber": "UPDATED_STUDY",
            "CustomerName":"Old_customer"
        }
        
        response = client.put(
            "/api/Projects/EditProject?ProjectNumber=NONEXISTENT",
            data=update_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

class TestDeleteProject:
    def test_delete_project_success(self, client, db_session, auth_headers):
        """Test successful project deletion"""
        user = create_test_user(db_session)
        project = create_test_project(db_session, "DELETE001", user.UserId)
        
        response = client.request(
        "DELETE",
        "/api/Projects/DeleteProject",
        json={"project_numbers": ["DELETE001"]},
        headers=auth_headers
    )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Projects deleted successfully"

    def test_delete_project_not_found(self, client, auth_headers):
        """Test deleting non-existent project"""
        response = client.request(
        "DELETE",
        "/api/Projects/DeleteProject",
        json={"project_numbers": ["DELETE002"]},
        headers=auth_headers
    )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"]["message"] == "project numbers were not found."

    def test_delete_project_already_deleted(self, client,db_session, auth_headers):
        """Test deleting a project that was already deleted"""
        # First create and delete a project
        user = create_test_user(db_session)
        project = create_test_project(db_session, "DELETE001", user.UserId)
        
        # Soft delete the project
        project.RecordStatus = 'D'
        project.DeletedBy = user.UserId
        project.DeletedAt = datetime.now(timezone.utc)
        db_session.commit()

        # Try to delete it again
        response = client.request(
            "DELETE",
            "/api/Projects/DeleteProject",
            json={"project_numbers": ["DELETE001"]},
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already deleted" in response.json()["detail"]["message"]

class TestGetDeletedProjectList:
    def test_get_deleted_project_list_success(self, client, db_session, auth_headers):
        """Test retrieving deleted projects"""
        user = create_test_user(db_session)
        project = create_test_project(db_session, "DELETED001", user.UserId)
        project.RecordStatus = "D"
        project.DeletedBy = user.UserId
        project.DeletedAt = datetime.now(timezone.utc)
        db_session.commit()
        
        response = client.get(
            "/api/Projects/GetDeletedProjectList",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["ProjectNumber"] == "DELETED001"
        assert data[0]["DeleteByUsername"] == "Test User"

    def test_get_deleted_project_list_empty(self, client, auth_headers):
        """Test empty deleted projects list"""
        response = client.get(
            "/api/Projects/GetDeletedProjectList",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

class TestGetProjectInfo:
    def test_get_project_info_success(self, client, db_session, auth_headers):
        """Test successful project info retrieval"""
        user = create_test_user(db_session)
        project = create_test_project(db_session, "INFO001", user.UserId)
        
        response = client.get(
            "/api/Projects/GetProjectInfo?ProjectNumber=INFO001",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ProjectNumber"] == "INFO001"
        assert data["CreatedByUsername"] == "Test User"

    def test_get_project_info_not_found(self, client, auth_headers):
        """Test non-existent project info retrieval"""
        response = client.get(
            "/api/Projects/GetProjectInfo?ProjectNumber=NONEXISTENT",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

class TestGetProjectFolderFiles:
    @patch('app.api.routers.projects.ContainerClient')
    def test_get_project_files_success(self, mock_container, client, db_session, auth_headers):
        """Test successfully listing project files"""
        # Setup test data
        user = create_test_user(db_session)
        project = create_test_project(db_session, "TEST001", user.UserId)
        project.UploadedBy = user.UserId
        project.UploadedAt = datetime.now(timezone.utc)
        db_session.commit()

        # Mock Azure Blob response - need proper blob structure
        mock_blob = MagicMock()
        mock_blob.name = f"{settings.BASE_BLOB_PATH}/TEST001/SDTM/test_file.sas7bdat"
        mock_blob.size = 1024  # 1KB

        # Configure mock container client
        mock_client = MagicMock()
        mock_client.list_blobs.return_value = [mock_blob]
        mock_container.from_connection_string.return_value = mock_client

        # Make request
        response = client.get(
            "/api/Projects/GetProjectFolderFiles",
            params={"ProjectNumber": "TEST001", "folder": "SDTM"},
            headers=auth_headers
        )

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)  # Should return a dict, not message
        
        if "message" in data:
            print(f"Unexpected message: {data['message']}")
        
        assert "SDTM" in data
        assert len(data["SDTM"]) == 1
        assert data["SDTM"][0]["name"] == "test_file"

        
    def test_get_files_project_not_found(self, client, db_session, auth_headers):
        """Test with non-existent project"""
        response = client.get(
            "/api/Projects/GetProjectFolderFiles",
            params={"ProjectNumber": "NONEXISTENT", "folder": "SDTM"},
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_files_no_files_found(self, client, db_session, auth_headers):
        """Test when no files exist for project"""
        # Setup test data
        user = create_test_user(db_session)
        project = create_test_project(db_session, "TEST001", user.UserId)

        # Mock the Azure ContainerClient using context manager
        with patch('app.api.routers.projects.ContainerClient.from_connection_string') as mock_from_conn:
            # Create mock client
            mock_client = MagicMock()
            
            # Configure mock to return empty list
            mock_client.list_blobs.return_value = []
            mock_from_conn.return_value = mock_client

            # Make request
            response = client.get(
                "/api/Projects/GetProjectFolderFiles",
                params={
                    "ProjectNumber": "TEST001",
                    "folder": "SDTM"
                },
                headers=auth_headers
            )

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {
                "message": "No files found for project 'TEST001' in folder 'SDTM'"
            }

    def test_get_files_azure_error(self, client, db_session, auth_headers):
        """Test Azure Blob Storage error handling"""
        # Setup test data
        user = create_test_user(db_session)
        project = create_test_project(db_session, "TEST001", user.UserId)

        # Mock the Azure ContainerClient to raise an error
        with patch('app.api.routers.projects.ContainerClient.from_connection_string') as mock_from_conn:
            # Configure mock to raise an error
            mock_from_conn.side_effect = Exception("Azure connection failed")

            # Make request
            response = client.get(
                "/api/Projects/GetProjectFolderFiles",
                params={
                    "ProjectNumber": "TEST001",
                    "folder": "SDTM"
                },
                headers=auth_headers
            )

            # Verify error response
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Azure Blob" in response.json()["detail"]

class TestDownloadExcelFromDB:
    @patch('pandas.read_sql')
    def test_download_excel_success(self, mock_read_sql, client,db_session, auth_headers):
        """Test successful Excel download from SSMS"""
        # Step 2: Mock returned data from SSMS
        test_data = pd.DataFrame({
            'subject_id': [101, 102, 103],
            'gender': ['M', 'F', 'M'],
            'age': [25, 32, 41]
        })
        mock_read_sql.return_value = test_data

        # Step 3: Mock table existence check
        with patch('app.api.routers.projects.get_project_active') as mock_get_project, \
            patch.object(db_session, 'execute') as mock_execute:

            user = create_test_user(db_session)
            project = create_test_project(db_session, "TEST001", user.UserId)
            db_session.commit()

            mock_get_project.return_value = project
            mock_execute.return_value.fetchone.return_value = [1]

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "filename": "dm"
                },
                headers=auth_headers
            )

            print("Status Code:", response.status_code)
            print("Response Text:", response.text)

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            assert "attachment; filename=dm.xlsx" in response.headers["content-disposition"]

            content = BytesIO(response.content)
            df = pd.read_excel(content)

            assert df.shape == (3, 3)
            assert list(df['subject_id']) == [101, 102, 103]

    def test_download_nonexistent_table(self, client, db_session,auth_headers):
        """Test download with non-existent table"""
        # Setup mock to raise exception for table check
        with patch.object(db_session, 'execute') as mock_execute:
            mock_execute.side_effect = Exception("Table not found")

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "MISSING",
                    "foldername": "SDTM",
                    "filename": "nonexistent"
                },
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "Table 'missing_sdtm.nonexistent' not found" in response.json()["detail"]

    def test_download_empty_table(self,client, db_session, auth_headers):
        """Test download with empty table"""
        with patch('pandas.read_sql') as mock_read_sql, \
            patch.object(db_session, 'execute') as mock_execute:

            # Step 1: Return empty DataFrame
            mock_read_sql.return_value = pd.DataFrame()

            # Step 2: Pretend table exists
            mock_execute.return_value.fetchone.return_value = [1]

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "filename": "empty"
                },
                headers=auth_headers
            )

            assert response.status_code == 200
            content = BytesIO(response.content)
            df = pd.read_excel(content)
            assert df.empty



    @patch('pandas.read_sql')
    def test_download_large_table(self, mock_read_sql, client,db_session,auth_headers):
        """Test download with large dataset"""
        # Setup large dataframe (1000 rows)
        test_data = pd.DataFrame({
            'col1': range(1000),
            'col2': ['value'] * 1000
        })
        mock_read_sql.return_value = test_data

        with patch.object(db_session, 'execute') as mock_execute:
            mock_execute.return_value.fetchone.return_value = [1]  # Pretend table exists

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "filename": "large"
                },
                headers=auth_headers
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            content_length = int(response.headers.get("content-length", 0))
            assert content_length > 10000  # Make sure file is reasonably large

    @patch('pandas.read_sql')
    def test_download_special_chars(self, mock_read_sql, client,db_session,auth_headers):
        """Test download with special characters in data"""
        test_data = pd.DataFrame({
            'col1': [1, 2],
            'col2': ['áéíóú', '©®™']
        })
        mock_read_sql.return_value = test_data

        with patch.object(db_session, 'execute') as mock_execute:
            # Simulate table exists
            mock_execute.return_value.fetchone.return_value = [1]

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "filename": "special"
                },
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            content = BytesIO(response.content)
            df = pd.read_excel(content)
            assert 'áéíóú' in df['col2'].values

    @patch('pandas.read_sql')
    def test_download_with_nan_values(self, mock_read_sql, client,db_session,auth_headers):
        """Test download with NaN values in data"""
        test_data = pd.DataFrame({
            'col1': [1, None, 3],
            'col2': ['a', None, 'c']
        })
        mock_read_sql.return_value = test_data

        with patch.object(db_session, 'execute') as mock_execute:
            # Simulate table exists
            mock_execute.return_value.fetchone.return_value = [1]

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "filename": "nan"
                },
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            content = BytesIO(response.content)
            df = pd.read_excel(content)
            assert df.isna().sum().sum() == 2  # Verify two NaN values

    @patch('pandas.read_sql', side_effect=Exception("Database error"))
    def test_database_error(self, mock_read_sql, client,db_session,auth_headers):
        """Test handling of database errors"""
        with patch.object(db_session, 'execute') as mock_execute:
            # Simulate table exists
            mock_execute.return_value.fetchone.return_value = [1]

            response = client.get(
                "/api/Projects/DownloadExcelFromDB",
                params={
                    "project_number": "TEST001",
                    "foldername": "SDTM",
                    "filename": "error"
                },
                headers=auth_headers
            )

            assert response.status_code == 500
            assert "Excel generation failed" in response.json()["detail"]

    def test_missing_parameters(self, client,auth_headers):
        """Test with missing required parameters"""
        # Test missing project_number
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "foldername": "SDTM",
                "filename": "test"
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test missing foldername
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "filename": "test"
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test missing filename
        response = client.get(
            "/api/Projects/DownloadExcelFromDB",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM"
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestDeleteBlobFiles:
    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_delete_blob_files_success(self,mock_blob_client_factory, client, db_session, auth_headers):
        # Mock Azure blob delete success
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_blob_service.get_container_client.return_value = mock_container
        mock_blob_client_factory.return_value = mock_blob_service
        mock_container.delete_blob.return_value = None  # success

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
            data=json.dumps([{
                "project_number": "TEST001",
                "foldername": "SDTM",
                "name": "dm",
                "type": "xpt"
            }])
        )

            # --- Assert ---
            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert len(body["deleted_blobs"]) == 1
            assert body["not_found_blobs"] == []
            assert len(body["dropped_tables"]) == 1
            assert body["failed_to_drop_tables"] == []


    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_blob_not_found_but_table_dropped(self,mock_blob_client_factory, client, db_session, auth_headers):

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
            data=json.dumps([{
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



    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_blob_deleted_but_table_drop_fails(self,mock_blob_client_factory, client, db_session, auth_headers):
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
            data=json.dumps([{
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


    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_both_blob_and_table_fail(self,mock_blob_client_factory, client, db_session, auth_headers):
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
            data=json.dumps([{
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

class TestViewSasDatasets:
    @patch("pandas.read_sql")
    def test_view_sas_datasets_success(self,mock_read_sql, client, db_session, auth_headers):
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
                "page": 1,
                "page_size": 2
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 2
        assert data["data"] == [
            {"subject_id": 1, "gender": "M"},
            {"subject_id": 2, "gender": "F"}
        ]

    @patch("pandas.read_sql", side_effect=ProgrammingError("SELECT", {}, None))
    def test_view_sas_datasets_table_not_found(self,mock_read_sql, client, db_session, auth_headers):
        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "missing_table"
            },
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]

    @patch("pandas.read_sql", side_effect=OperationalError("SELECT", {}, None))
    def test_view_sas_datasets_operational_error(self,mock_read_sql, client, db_session, auth_headers):
        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "dm"
            },
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]

    @patch("pandas.read_sql", side_effect=Exception("Something went wrong"))
    def test_view_sas_datasets_internal_error(self,mock_read_sql, client, db_session, auth_headers):
        response = client.get(
            "/api/Projects/ViewSasDatasets",
            params={
                "project_number": "TEST001",
                "foldername": "SDTM",
                "filename": "dm"
            },
            headers=auth_headers
        )

        assert response.status_code == 500
        assert "Unexpected error" in response.json()["detail"]




