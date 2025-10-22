from sqlalchemy.orm import sessionmaker
from app.db.base import engine, engine_files
import pyodbc
import logging
from threading import Lock
from collections import defaultdict
import time
from app.core.config import settings
from sqlalchemy.orm import Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionFiles = sessionmaker(autocommit=False, autoflush=False, bind=engine_files)

def get_db():
    """
    Dependency function that yields db sessions
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_files_db():
    db = SessionFiles()
    try:
        yield db
    finally:
        db.close()

def get_websocket_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

logger = logging.getLogger("sas_importer")

class ConnectionPool:
    _pool = defaultdict(list)
    _lock = Lock()
    _count = defaultdict(int)
    _max_connections = 15
    _wait_timeout = 60  # 60 seconds to wait for a connection

    @classmethod
    def get_connection(cls, db_name=None):
        start_time = time.time()
        key = db_name or "default"
        while time.time() - start_time < cls._wait_timeout:
            with cls._lock:
                # Try to get an existing connection from the pool
                if cls._pool[key]:
                    return cls._pool[key].pop()
                # Create new connection if under limit
                if cls._count[key] < cls._max_connections:
                    conn = cls._create_connection(db_name)
                    cls._count[key] += 1
                    return conn
            # Wait before retrying
            time.sleep(0.5)
        raise RuntimeError(f"Timeout waiting for connection to {key} after {cls._wait_timeout} seconds")

    @classmethod
    def _create_connection(cls, db_name):
        conn_str = f'DRIVER={{{settings.DRIVER}}};SERVER={settings.SQL_SERVER};'
        if db_name:
            conn_str += f'DATABASE={db_name};'
        if settings.USE_WINDOWS_AUTH:
            conn_str += 'Trusted_Connection=yes;'
        else:
            conn_str += f'UID={settings.USERNAME};PWD={settings.PASSWORD};'
        conn = pyodbc.connect(conn_str, autocommit=False, timeout=settings.AZURE_DOWNLOAD_TIMEOUT)
        conn.timeout = settings.AZURE_DOWNLOAD_TIMEOUT
        return conn

    @classmethod
    def return_connection(cls, conn, db_name=None):
        key = db_name or "default"
        with cls._lock:
            # Reset connection state before returning
            try:
                if conn.autocommit != False:
                    conn.autocommit = False
                conn.rollback()
            except:
                pass
            cls._pool[key].append(conn)

    @classmethod
    def close_all(cls):
        with cls._lock:
            for key, connections in cls._pool.items():
                for conn in connections:
                    try:
                        conn.close()
                    except:
                        pass
                cls._pool[key] = []
                cls._count[key] = 0