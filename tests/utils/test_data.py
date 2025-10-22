from datetime import datetime, timezone, date
from app.models.user import User, Project

def create_test_user(db, user_id=1, object_id="test-object-id"):
    user = User(
        UserId=user_id,
        UserEmail="test@example.com",
        UserName="Test User",
        ObjectId=object_id,
        UserType="Admin",
        RecordStatus="A",
        CreatedBy=1,
        CreatedAt=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    return user

def create_test_project(db, project_number="TEST001", user_id=1):
    project = Project(
        ProjectNumber=project_number,
        StudyNumber="STUDY001",
        CustomerName="Test Customer",
        CutDate=date.today(),
        ExtractionDate=date.today(),
        IsDatasetUploaded=False,
        UploadedBy=user_id,
        ProjectStatus="InProgress",
        RecordStatus="A",
        CreatedBy=user_id,
        CreatedAt=datetime.now(timezone.utc)
    )
    db.add(project)
    db.commit()
    return project