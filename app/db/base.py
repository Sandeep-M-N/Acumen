from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

engine_files = create_engine(settings.DATABASE_URL_FILES)
SessionFiles = sessionmaker(autocommit=False, autoflush=False, bind=engine_files)

Base = declarative_base()