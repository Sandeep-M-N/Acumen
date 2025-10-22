import json
import time
from langchain_community.utilities import SQLDatabase
from app.core.config import settings
from datetime import date, datetime
from .lab_module import handle_lab_module
from .medications_module import handle_medications_module
from .procedures_module import handle_procedures_module
from .adverse_events_module import handle_adverse_events_module
from .disposition_outcome_module import handle_disposition_outcome_module
from .vital_signs_module import handle_vital_signs_module
from .dosing_exposure_module import handle_dosing_exposure_module
from app.db.session import get_db
from app.models.user import QueryModule
from sqlalchemy.orm import Session

def handle_standard_query(ProjectNumber: str, FolderName: str, Question: str, query_data: dict):
    """Handle standard query flow with hardcoded data - returns query and result with column headings"""
    print("query_dataaaaaaaaaaaaaaaaaaaaaaa....",query_data)
    try:
        # Database connection
        schema = f"{ProjectNumber}_{FolderName}"
        sql_server_conn_str = settings.DATABASE_URL_FILES
        db = SQLDatabase.from_uri(sql_server_conn_str, schema=schema, sample_rows_in_table_info=0)
        
        # Extract common data from query_data
        module_type = query_data.get("ModuleType")
        usubject = query_data.get("Usubject")
        aestdtc = query_data.get("AESTDTC")
        aeendtc = query_data.get("AEENDTC")
        days = query_data.get("Days")
        QuestionType = query_data.get("QuestionType")
        
        if aeendtc == "ONGOING":
            aeendtc = datetime.now().strftime("%Y-%m-%d")
            
        # Route based on ModuleType name
        if module_type == 1: # Lab
            return handle_lab_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)
        elif module_type == 2: # Medications
            return handle_medications_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)
        elif module_type == 3: # Proceduress
            return handle_procedures_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)
        elif module_type == 4: # Adverse Events
            return handle_adverse_events_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)
        elif module_type == 5: # Vital Signs
            return handle_vital_signs_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)
        elif module_type == 6: # Disposition and Outcome
            return handle_disposition_outcome_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)
        elif module_type == 7: # Dosing and Exposure
            return handle_dosing_exposure_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType)

        else:
            raise ValueError(f"Unsupported ModuleType: {module_type}")
            
    except Exception as e:
        return {
            "query": "",
            "query_result": f"Error: {str(e)}"
        }
