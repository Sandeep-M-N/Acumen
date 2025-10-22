from pydantic import BaseModel, Field, field_validator,model_validator,ConfigDict
from datetime import date, datetime,timezone
from typing import Optional,Literal
from typing import List, Tuple,TypedDict
import re
class ProjectBase(BaseModel):
    ProjectId: Optional[int] = None  # Make it optional
    ProjectNumber: str = Field(..., min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9\_]+$')
    CustomerName: str = Field(..., min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9\-_.&\s]+$')
    StudyNumber: str = Field(..., min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9\-_]+$')
    CutDate: Optional[date] = None  # Changed to date type
    ExtractionDate: Optional[date] = None  # Changed to date type
    IsDatasetUploaded: int = Field(0, ge=0, le=1)
    ProjectStatus: Optional[str] = None
    CreatedBy:Optional[int] = None
    ModifiedBy:Optional[int] = None
    UploadedBy:Optional[int]=None
    UploadedAt: Optional[datetime] = None
    CreatedAt:datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ModifiedAt:Optional[datetime] = None

class ProjectCheckRequest(BaseModel):
    ProjectNumber: str = Field(..., min_length=1, max_length=80)

class ProjectCheckResponse(BaseModel):
    available: bool
    message: str

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(BaseModel):
    ProjectNumber:str
    StudyNumber: str
    CustomerName : str
    CutDate: Optional[date] = None
    ExtractionDate: Optional[date] = None
    ProjectStatus:Optional[str]=None
    CreatedBy:Optional[int] = None
    ModifiedBy:Optional[int]= None
    UploadedBy:Optional[int]=None
    UploadedAt: Optional[datetime] = None
    CreatedAt:datetime
    ModifiedAt:Optional[datetime]=None
    DeletedBy:Optional[int]=None
    DeletedAt:Optional[datetime]=None
    CreatedByUsername:Optional[str]=None
    DeleteByUsername:Optional[str]=None
    ModifiedByUsername:Optional[str]=None
    model_config = ConfigDict(from_attributes=True)

class ProjectRequest(BaseModel):
    project_name: str

class FileDeleteItem(BaseModel):
    name: str
    type: str
    foldername: str
    project_number: str

class QueryRequest(BaseModel):
    ProjectNumber: str
    FolderName: str
    Question: str
    LlmType: str
    ModelName: str
    SessionId: Optional[int] = None
    Type: Literal['Table', 'Summary']
    FlowType: Literal['AI', 'STANDARD'] # New field to specify flow type
    STANDARD_QUERY_DATA: Optional[dict] = None  # Optional field for standard query data


class QuerySessionOut(BaseModel):
    Id:            int
    ProjectNumber : str
    Title:         str
    IsFavorite:    bool
    CreatedAt:     datetime
    UpdatedAt:     datetime
    LastMessageSnippet: Optional[str]

    class Config:
        from_attributes  = True


class QuerySessionIn(BaseModel):
    Title:      Optional[str] = None
    IsFavorite: Optional[bool]  = None

    class Config:
        from_attributes  = True


class MessageIn(BaseModel):
    Sender:   str
    Content:  str
    Metadata: Optional[dict] = None
    FeedbackType : Optional[str] = None 
    FeedbackComment: Optional[str] = None 
    FeedbackAt: Optional[datetime] = None
    QueryBy: Optional[int] = None
    ViewType: Optional[str] = None  # 'Table' or 'Summary'
    FlowType: Optional[str] = None  # 'AI' or 'STANDARD'

    class Config:
        from_attributes  = True

class UserOut(BaseModel):
    UserId: int
    UserName: str
    class Config:
        from_attributes = True

class MessageOut(MessageIn):
    Id:        int
    CreatedAt: datetime
    User: Optional[UserOut] = None

class UpdateLLMConfigInput(BaseModel):
    UserId: int
    ProviderId: int
    ModelId: int

class TableConfig(BaseModel):
    FolderName: str
    TableName: str
    SelectedColumns: List[str]

class PatientProfileRequest(BaseModel):
    ProjectNumber: str
    Tables: List[TableConfig]
    CreatedBy: int