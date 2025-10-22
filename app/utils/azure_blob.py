from azure.storage.blob import BlobServiceClient, BlobClient, BlobBlock
import os
import uuid
import logging
import time
from app.core.config import settings
from concurrent.futures import ThreadPoolExecutor

# Set up logging to file
log_file = "logs/upload.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a file handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(file_handler)

def upload_to_azure_blob(blob_path: str, local_path: str) -> bool:
    """
    Uploads a local file to Azure Blob Storage.
    
    Args:
        blob_path (str): The path in Azure Blob Storage where the file will be uploaded.
        local_path (str): The local file path to upload.
        
    Returns:
        bool: True if upload is successful, False otherwise.
    """
    try:
        # Log start of upload
        logger.debug(f"[DEBUG] Starting upload of {local_path} to {blob_path}")
        start_time = time.time()

        # Check if the file exists and is readable
        if not os.path.exists(local_path):
            logger.error(f"[ERROR] File not found: {local_path}")
            return False

        if not os.path.isfile(local_path):
            logger.error(f"[ERROR] Not a file: {local_path}")
            return False

        # Get connection string from environment
        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
        if not conn_str:
            logger.error("[ERROR] AZURE_STORAGE_CONNECTION_STRING is not set.")
            return False

        # Initialize clients
        blob_service_client = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING,
            max_single_put_size=8*1024*1024,  # 8MB threshold for single upload
            max_block_size=8*1024*1024
        )
        blob_client = blob_service_client.get_blob_client(
            container=settings.AZURE_STORAGE_CONTAINER_NAME,
            blob=blob_path
        )

        # For files smaller than 8MB, use simple upload
        file_size = os.path.getsize(local_path)
        if file_size <= 8*1024*1024:
            with open(local_path, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)
            return True

        # Parallel upload for larger files
        chunk_size = 8*1024*1024  # 8MB chunks
        block_list = []

        def upload_chunk(chunk_data, chunk_num):
            block_id = str(uuid.uuid4())
            blob_client.stage_block(block_id=block_id, data=chunk_data)
            return BlobBlock(block_id=block_id)

        with ThreadPoolExecutor(max_workers=4) as executor, \
             open(local_path, "rb") as f:
            
            futures = []
            chunk_num = 0
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                futures.append(executor.submit(upload_chunk, chunk_data, chunk_num))
                chunk_num += 1

            # Wait for all uploads to complete and collect block IDs
            block_list = [future.result() for future in futures]

        blob_client.commit_block_list(block_list)
        
        duration = time.time() - start_time
        logger.debug(f"Upload completed in {duration:.2f} seconds")
        return True

    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return False

def upload_files_in_parallel(files_to_upload: list[tuple[str, str]]) -> tuple[int, int]:
    """
    Upload multiple files in parallel using thread pool.

    Args:
        files_to_upload (list[tuple[str, str]): List of (blob_path, local_path) tuples.

    Returns:
        tuple[int, int]: (success_count, failed_count)
    """
    success_count = 0
    failed_count = 0

    def _upload_file(blob_path: str, local_path: str):
        nonlocal success_count, failed_count
        try:
            if upload_to_azure_blob(blob_path, local_path):
                success_count += 1
                logger.debug(f"[DEBUG] Uploaded {local_path} to {blob_path}")
            else:
                failed_count += 1
                logger.error(f"[ERROR] Failed to upload {local_path} to {blob_path}")
        except Exception as e:
            failed_count += 1
            logger.error(f"[ERROR] Exception during upload of {local_path}: {str(e)}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        for blob_path, local_path in files_to_upload:
            executor.submit(_upload_file, blob_path, local_path)

    return success_count, failed_count