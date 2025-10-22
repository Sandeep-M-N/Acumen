import os
import shutil
import zipfile
import re
import tempfile
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.user import Project,User,UploadBatch, UploadBatchFile
from app.schemas.project import ProjectCreate
from app.utils.azure_blob import upload_to_azure_blob, upload_files_in_parallel
from app.core.config import settings
from fastapi import UploadFile,HTTPException
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from app.core.config import settings
from datetime import date,datetime,timezone
# Set up logging to file
log_file = "logs/upload.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

logger = logging.getLogger(__name__)

def get_project(db: Session, ProjectNumber: str):
    return db.query(Project).filter(Project.ProjectNumber == ProjectNumber).first()
def get_project_active(db: Session, ProjectNumber: str):
    return db.query(Project).filter(Project.ProjectNumber == ProjectNumber,Project.RecordStatus=='A').first()
def get_deleted_projects(db: Session):
    return db.query(Project).filter(Project.RecordStatus == 'D').all()
def get_all_projects(db: Session):
    """Get all projects from the database."""
    return db.query(Project).filter(Project.RecordStatus == 'A').all()
def get_username_from_user_id(user_id: int, db: Session) -> str:
    user = db.query(User).filter(User.UserId == user_id).first()
    return user.UserName if user else "Unknown"

def create_project(db: Session, project: ProjectCreate):
    db_project = Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and invalid characters."""
    return re.sub(r'[^\w\.\-]', '_', filename)

def classify_sas_file(filename: str) -> str:
    """Classify SAS files as ADAM or SDTM"""
    filename = filename.lower()
    if re.match(r'^ad[a-z]{1,3}\.sas7bdat$', filename) or re.match(r'^ad[a-z]{1,3}\d+\.sas7bdat$', filename):
        return "ADAM"
    if filename.startswith('supp') and filename.endswith('.sas7bdat'):
        return "SDTM"
    if re.match(r'^[a-z]{2,3}\.sas7bdat$', filename) or re.match(r'^[a-z]{2,3}\d+\.sas7bdat$', filename):
        return "SDTM"
    return None

def process_uploaded_file(ProjectNumber: str, uploaded_files: List[UploadFile], db: Session, uploaded_by: int) -> int:
    """
    Process multiple uploaded files (ZIP, SAS, or Excel) and upload them to Azure Blob Storage.
    Inserts records into UploadBatch and UploadBatchFile.
    Returns 1 if at least one file was processed and uploaded, else 0.
    """

    IsDatasetUploaded = False
    # processed_files = []

    try:
        # Start time for full process
        start_time_total = time.time()
        logger.debug(f"[DEBUG] Start time for full process: {start_time_total}")

        if not uploaded_files:
            logger.warning("No files were uploaded.")
            return 0

        # Create a temporary directory to store all files
        tmpdirname = tempfile.mkdtemp()
        logger.debug(f"[DEBUG] Created temporary directory: {tmpdirname}")

        for uploaded_file in uploaded_files:
            if uploaded_file.filename:
                file_path = os.path.join(tmpdirname, uploaded_file.filename)
                logger.debug(f"[DEBUG] Saving file: {file_path}")

                # Save the file locally
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(uploaded_file.file, f)
                # Get file size in KB
                file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
                sanitized_name = sanitize_filename(uploaded_file.filename)
                blob_raw_path = f"{settings.BASE_RAW_PATH}/{ProjectNumber}/{sanitized_name}"
                
                # FIX: Get extension in lowercase consistently
                ext = os.path.splitext(uploaded_file.filename)[-1].lower().lstrip('.')
                
                if ext == 'zip':
                    # FIX: Create UNIQUE extraction directory per ZIP file
                    extract_path = tempfile.mkdtemp(dir=tmpdirname)
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)

                    # Recursively walk through folders (e.g., SDTM, ADaM) and count files
                    total_files = 0
                    for root, dirs, files in os.walk(extract_path):
                        total_files += len(files)
                else:
                    # For non-ZIP files, just count the single file
                    total_files = 1
                if upload_to_azure_blob(blob_raw_path, file_path):
                    logger.debug(f"[DEBUG] File '{uploaded_file.filename}' uploaded successfully.")
                    Status = "Uploaded"
                    IsDatasetUploaded = True
                else:
                    Status = "Uploaded - Error"
                    logger.warning(f"[WARNING] Failed to upload file: {uploaded_file.filename}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to upload file: {uploaded_file.filename}. Please try again later."
                    )
                # Insert UploadBatch before blob upload
                upload_batch = UploadBatch(
                    ProjectNumber=ProjectNumber,
                    FileName=uploaded_file.filename,
                    FileSize=file_size_kb,
                    FileType=ext,
                    FileCount=total_files,  # Now counts ONLY current file's contents
                    UploadTime=datetime.now(timezone.utc),
                    Status=Status,
                    UploadedBy=uploaded_by
                )
                db.add(upload_batch)
                db.commit()
                db.refresh(upload_batch)

        total_duration = time.time() - start_time_total
        logger.debug(f"[DEBUG] Total upload duration: {total_duration:.2f} seconds")

        # Clean up temp directory
        shutil.rmtree(tmpdirname)
        return int(IsDatasetUploaded)  # Ensure int return

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        raise