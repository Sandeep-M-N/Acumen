from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, ForeignKey, CheckConstraint, Text, JSON, Index, BigInteger, UniqueConstraint, Float, text
from app.db.base import Base
from sqlalchemy.orm import relationship
from datetime import datetime,timezone
from uuid import UUID

class User(Base):
    __tablename__ = "User"

    UserId = Column(Integer, primary_key=True, autoincrement=True)
    UserEmail = Column(String(256), nullable=False)
    UserName = Column(String(100), nullable=False)
    ObjectId = Column(String(36), nullable=False)  # UUID as string
    UserType = Column(String(50), nullable=True)
    RecordStatus = Column(String(1), nullable=False, default='A', server_default='A')
    CreatedBy = Column(Integer, nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    ModifiedBy = Column(Integer, nullable=True)
    ModifiedAt = Column(DateTime, nullable=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(RecordStatus.in_(['A', 'D']), name='chk_user_record_status'),
    )

class Project(Base):
    __tablename__ = "Project"
    ProjectId = Column(Integer, primary_key=True, autoincrement=True)
    ProjectNumber = Column(String(80), unique=True, nullable=False)
    StudyNumber = Column(String(80), nullable=False)
    CustomerName = Column(String(80), nullable=False)
    CutDate = Column(Date, nullable=True)
    ExtractionDate = Column(Date, nullable=True)
    IsDatasetUploaded = Column(Boolean, nullable=False, default=False)
    UploadedBy = Column(Integer, ForeignKey("User.UserId"), nullable=True)
    UploadedAt = Column(DateTime, nullable=True)
    ProjectStatus = Column(String(50), nullable=False, default="InProgress")
    RecordStatus = Column(String(1), nullable=False, default='A', server_default='A')
    CreatedBy = Column(Integer, ForeignKey("User.UserId"), nullable=True)
    CreatedAt = Column(DateTime, nullable=True, default=datetime.now(timezone.utc))
    ModifiedBy = Column(Integer, ForeignKey("User.UserId"), nullable=True)
    ModifiedAt = Column(DateTime, nullable=True)
    DeletedBy = Column(Integer, ForeignKey("User.UserId"), nullable=True)
    DeletedAt = Column(DateTime, nullable=True)

    # Relationships
    user_uploaded_by = relationship("User", foreign_keys=[UploadedBy])
    user_created_by = relationship("User", foreign_keys=[CreatedBy])
    user_modified_by = relationship("User", foreign_keys=[ModifiedBy])
    user_deleted_by = relationship("User", foreign_keys=[DeletedBy])

    # Constraints
    __table_args__ = (
        CheckConstraint(ProjectStatus.in_(['InProgress', 'Verification', 'Completed']), name='chk_project_status'),
        CheckConstraint(RecordStatus.in_(['A', 'D']), name='chk_project_record_status'),
        
    )

class ClinicalQuerySession(Base):
    __tablename__ = "ClinicalQuerySession"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    ProjectNumber = Column(String(80), ForeignKey("Project.ProjectNumber", ondelete="CASCADE"), nullable=False)
    Title = Column(Text, nullable=False)
    IsFavorite = Column(Boolean, nullable=False, default=False)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    UpdatedAt = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))

    project = relationship("Project", backref="ClinicalQuerySessions")



Index(
    "ix_ClinicalQuerySession_ProjectNumber_UpdatedAt",
    ClinicalQuerySession.ProjectNumber,
    ClinicalQuerySession.UpdatedAt.desc()
)

Index(
    "ix_ClinicalQuerySession_ProjectNumber_IsFavorite",
    ClinicalQuerySession.ProjectNumber,
    ClinicalQuerySession.IsFavorite
)

class ClinicalQueryMessage(Base):
    __tablename__ = "ClinicalQueryMessage"

    Id = Column(BigInteger, primary_key=True, autoincrement=True)
    SessionId = Column(Integer, ForeignKey("ClinicalQuerySession.Id", ondelete="CASCADE"), nullable=False)
    Sender = Column(String(20), nullable=False)  # 'user' or 'assistant'
    Content = Column(Text, nullable=False)
    Metadata = Column(JSON, nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    # New columns
    FeedbackType = Column(String(20), nullable=True)       # 'Positive', 'Negative', or None
    FeedbackComment = Column(Text, nullable=True)           # Optional comment
    FeedbackAt = Column(DateTime, nullable=True,default=datetime.now(timezone.utc))# Timestamp of feedback
    QueryBy = Column(Integer, ForeignKey("User.UserId"), nullable=True)
    
    session = relationship("ClinicalQuerySession", backref="Messages")
    user_query_by = relationship("User", foreign_keys=[QueryBy])
    ViewType = Column(String(20), nullable=True)  # 'Table' or 'Summary'
    QnAGroupId = Column(Integer, nullable=True)  # Optional grouping for Q&A
    FlowType = Column(String(20), nullable=True)  # 'AI' or 'STANDARD'
    StandardTableContent = Column(JSON, nullable=True)  # JSON data for standard queries


Index(
    "ix_ClinicalQueryMessage_SessionId_CreatedAt",
    ClinicalQueryMessage.SessionId,
    ClinicalQueryMessage.CreatedAt.desc()
),
CheckConstraint(
            "FeedbackType IN ('Positive', 'Negative') OR FeedbackType IS NULL",
            name="check_feedback_type"
        )
CheckConstraint(
            "ViewType IN ('Table', 'Summary') OR ViewType IS NULL",
            name="check_view_type"
        )

class LLMProvider(Base):
    __tablename__ = "LLMProvider"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(100), nullable=False, unique=True)  # e.g., 'OpenAI', 'Azure OpenAI', 'Claude'
    IsActive = Column(Boolean, nullable=False, default=True, server_default='1')
    
    models = relationship("LLMModel", backref="Provider", cascade="all, delete-orphan")
    user_configs = relationship("UserLLMConfig", backref="Provider")  # no cascade here


class LLMModel(Base):
    __tablename__ = "LLMModel"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    ProviderId = Column(Integer, ForeignKey("LLMProvider.Id", ondelete="CASCADE"), nullable=False)
    ModelName = Column(String(100), nullable=False)
    IsActive = Column(Boolean, nullable=False, default=True, server_default='1')

    user_configs = relationship("UserLLMConfig", backref="Model")  # no cascade here

    __table_args__ = (
        UniqueConstraint('ProviderId', 'ModelName', name='UQ_Provider_Model'),
    )


class UserLLMConfig(Base):
    __tablename__ = "UserLLMConfig"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("User.UserId", ondelete="CASCADE"), nullable=False)
    ProviderId = Column(Integer, ForeignKey("LLMProvider.Id", ondelete="NO ACTION"), nullable=False)
    ModelId = Column(Integer, ForeignKey("LLMModel.Id", ondelete="NO ACTION"), nullable=False)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    UpdatedAt = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('UserId', name='UQ_User_Config'),
        Index("ix_UserLLMConfig_UserId_ModelId", "UserId", "ModelId"),
    )
class DomainClassification(Base):
    __tablename__ = "DomainClassification"

    Id = Column(Integer, primary_key=True, nullable=False)
    DomainName = Column(String(50), nullable=False, unique=True)
    DomainFullName = Column(String(255), nullable=True)
    ClassificationType = Column(String(10), nullable=False, server_default=text("'SDTM'"))
    IsAIGenerated = Column(Boolean, nullable=False, server_default=text("0"))
    CreatedAt = Column(DateTime, server_default=text("GETDATE()"))  # Or use `default=datetime.utcnow` if cross-DB
    CreatedBy = Column(String(50), server_default=text("'System'"))

    __table_args__ = (
        CheckConstraint("ClassificationType IN ('ADaM', 'SDTM')", name='check_classification_type'),
        CheckConstraint("IsAIGenerated IN (0, 1)", name='check_is_ai_generated'),
        CheckConstraint("CreatedBy IN ('System', 'AI')", name='check_created_by'),
    )
class UploadBatch(Base):
    __tablename__ = "UploadBatch"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    ProjectNumber = Column(String(80), nullable=False)
    FileName = Column(String(255), nullable=False)
    FileType = Column(String(10), nullable=False)      # 'zip' or 'sas'
    FileSize = Column(Float, nullable=True)
    FileCount = Column(Integer, nullable=True)
    UploadTime = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    Status = Column(String(50), nullable=False)
    UploadedBy = Column(Integer, ForeignKey("User.UserId"), nullable=True)

    user = relationship("User", backref="UploadBatches")

Index(
    "ix_UploadBatch_ProjectNumber_UploadTime",
    UploadBatch.ProjectNumber,
    UploadBatch.UploadTime.desc()
    )
Index(
        "ix_UploadBatch_ProjectNumber_Status",
        UploadBatch.ProjectNumber,
        UploadBatch.Status
    )

class UploadBatchFile(Base):
    __tablename__ = "UploadBatchFile"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    BatchId = Column(Integer, ForeignKey("UploadBatch.Id", ondelete="CASCADE"), nullable=False)
    FileName = Column(String(255), nullable=False)     # .sas7bdat file name
    Domain = Column(String(10), nullable=True)         # 'SDTM', 'ADaM'
    StagedAt = Column(DateTime, nullable=True)
    CopiedAt = Column(DateTime, nullable=True)
    EnqueuedAt = Column(DateTime, nullable=True)
    ProcessedAt = Column(DateTime, nullable=True)
    Status = Column(String(50), nullable=False)        # 'Staged', 'Copied', 'Processed', 'Error', etc.
    ErrorNote = Column(Text, nullable=True)

    batch = relationship("UploadBatch", backref="Files")

Index(
    "ix_UploadBatchFile_BatchId_Status",
    UploadBatchFile.BatchId,
    UploadBatchFile.Status
)

Index(
    "ix_UploadBatchFile_Domain_Status",
    UploadBatchFile.Domain,
    UploadBatchFile.Status
)

class PatientProfileConfig(Base):
    __tablename__ = "PatientProfileConfig"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    ProjectNumber = Column(String(80), nullable=False) 
    DatasetType = Column(String(10), nullable=False)   # 'SDTM' or 'ADAM'
    TableName = Column(String(50), nullable=False)     # e.g. 'AE', 'EX'
    SelectedColumns = Column(String(2000), nullable=False)  # e.g. 'STUDYID'
    CreatedAt = Column(DateTime, server_default=text("GETDATE()"))
    CreatedBy = Column(Integer, nullable=False)
    ModifiedBy = Column(Integer, nullable=True)
    ModifiedAt = Column(DateTime, nullable=True)

# Example indexes if you want to speed up lookups
Index(
    "ix_PatientProfileConfig_ProjectID_TableName",
    PatientProfileConfig.ProjectNumber,
    PatientProfileConfig.TableName
)

Index(
    "ix_PatientProfileConfig_DatasetType",
    PatientProfileConfig.DatasetType
)

class QueryModule(Base):
    __tablename__ = "QueryModule"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(100), nullable=False)
    Status = Column(Boolean, nullable=False, default=True, server_default='1')

    categories = relationship("QueryCategory", backref="module", cascade="all, delete-orphan")

class QueryCategory(Base):
    __tablename__ = "QueryCategory"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    ModuleId = Column(Integer, ForeignKey("QueryModule.Id", ondelete="CASCADE"), nullable=False)
    Name = Column(String(100), nullable=False)
    LBCAT = Column(String(50), nullable=True)
    Status = Column(Boolean, nullable=False, default=True, server_default='1')

    queries = relationship("PredefinedQuery", backref="category", cascade="all, delete-orphan")
    lab_analytes = relationship("LabAnalytes", backref="category", cascade="all, delete-orphan")

class LabAnalytes(Base):
    __tablename__ = "LabAnalytes"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    CategoryId = Column(Integer, ForeignKey("QueryCategory.Id", ondelete="CASCADE"), nullable=False)
    LabTest = Column(JSON, nullable=False)

class PredefinedQuery(Base):
    __tablename__ = "PredefinedQuery"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    CategoryId = Column(Integer, ForeignKey("QueryCategory.Id", ondelete="CASCADE"), nullable=False)
    TemplateText = Column(Text, nullable=False)
    DatasetType = Column(String(50), nullable=True)
    TablesInvolved = Column(String(200), nullable=True)
    QueryType = Column(String(100), nullable=True)
    Status = Column(Boolean, nullable=False, default=True, server_default='1')

    placeholders = relationship("QueryPlaceholder", backref="query", cascade="all, delete-orphan")

class QueryPlaceholder(Base):
    __tablename__ = "QueryPlaceholder"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    QueryId = Column(Integer, ForeignKey("PredefinedQuery.Id", ondelete="CASCADE"), nullable=False)
    PlaceholderText = Column(String(100), nullable=False)
    InputType = Column(String(50), nullable=False)
    SourceTable = Column(String(50), nullable=True)
    SourceColumn = Column(String(50), nullable=True)
    CategoryFilter = Column(Integer, ForeignKey("QueryCategory.Id"), nullable=True)