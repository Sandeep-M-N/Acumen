from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db, get_files_db
from typing import Optional
import os
import logging
import json
import ast
import pandas as pd
from io import BytesIO
from app.core.security import azure_ad_dependency
from app.models.user import QueryModule, QueryCategory, PredefinedQuery, QueryPlaceholder, LabAnalytes, ClinicalQueryMessage
from sqlalchemy import text
from datetime import datetime



# Set up logging
log_file = "logs/upload.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(azure_ad_dependency)])

@router.get("/GetQueryModules", tags=["Predefined Template Query"])
def get_query_modules(db: Session = Depends(get_db)):
    modules = db.query(QueryModule).filter(QueryModule.Status == True).all()
    
    result = {
        "modules": [
            {
                "id": module.Id,
                "name": module.Name,
                "categories": [
                    {"id": cat.Id, "Name": cat.Name, "LBCAT": cat.LBCAT}
                    for cat in module.categories if cat.Status == True
                ]
            }
            for module in modules
        ]
    }
    
    return result

@router.get("/GetPredefinedQueries", tags=["Predefined Template Query"])
def get_predefined_queries(CategoryId: int, db: Session = Depends(get_db)):
    queries = db.query(PredefinedQuery).filter(
        PredefinedQuery.CategoryId == CategoryId,
        PredefinedQuery.Status == True
    ).all()
    
    result = []
    for query in queries:
        placeholders = db.query(QueryPlaceholder).filter(
            QueryPlaceholder.QueryId == query.Id
        ).all()
        
        placeholder_data = []
       
        for p in placeholders:
            category_filter = None
            categoryColumn = None 
            if p.CategoryFilter:
                category = db.query(QueryCategory).filter(QueryCategory.Id == p.CategoryFilter).first()
                category_filter = category.LBCAT if category else None
                
                if category_filter:
                    categoryColumn = "LBCAT"
            placeholder_data.append({
                "id": p.Id,
                "placeholder": p.PlaceholderText,
                "inputType": p.InputType,
                "sourceTable": p.SourceTable,
                "sourceColumn": p.SourceColumn,
                "categoryFilter": category_filter,
                "categoryColumn": categoryColumn
            })
        
        result.append({
            "queryId": query.Id,
            "templateText": query.TemplateText,
            "datasetType": query.DatasetType,
            "tablesInvolved": query.TablesInvolved,
            "queryType": query.QueryType,
            "placeholders": placeholder_data
        })
    
    return result

@router.get("/GetSubjects", tags=["Predefined Template Query"])
def get_subjects(
    ProjectNumber: str,
    DatasetType: str,
    Tables: str,
    USUBJID: Optional[str] = None,
    db: Session = Depends(get_files_db)
):
    schema = f"{ProjectNumber}_{DatasetType.lower()}"
    table_list = [t.strip().lower() for t in Tables.split(",") if t.strip()]
    
    # Case 1: Validate specific USUBJID across all tables
    if USUBJID:
        checks = [f"EXISTS (SELECT 1 FROM [{schema}].[{table}] WHERE USUBJID = :usubjid)" for table in table_list]
        condition = " AND ".join(checks)
        
        query = text(f"SELECT CASE WHEN {condition} THEN 1 ELSE 0 END AS is_match")
        print("check",query)
        result = db.execute(query, {"usubjid": USUBJID}).scalar()
        
        if result == 1:
            return {"USUBJID": USUBJID, "exists": True}
        else:
            raise HTTPException(status_code=404, detail=f"USUBJID {USUBJID} not found in all specified tables")
    
    # Case 2: Single table - return all unique USUBJIDs
    if len(table_list) == 1:
        query = text(f"SELECT DISTINCT USUBJID FROM [{schema}].[{table_list[0]}] WHERE USUBJID IS NOT NULL")
        print("singletable",query)
    
    # Case 3: Multiple tables - return intersection
    else:
        base = f"SELECT DISTINCT t0.USUBJID FROM [{schema}].[{table_list[0]}] t0"
        joins = "".join([f" INNER JOIN [{schema}].[{table}] t{i} ON t0.USUBJID = t{i}.USUBJID" 
                       for i, table in enumerate(table_list[1:], 1)])
        query = text(f"{base}{joins} WHERE t0.USUBJID IS NOT NULL")
        print("multipletable",query)
    result = db.execute(query).fetchall()
    return [row[0] for row in result]


@router.get("/GetPlaceholderValues", tags=["Predefined Template Query"])
def get_placeholder_values(
    ProjectNumber: str,
    DatasetType: str,
    USUBJID: str,
    sourceTable: str,
    sourceColumn: str,
    categoryColumn: Optional[str] = None,
    categoryFilterValue: Optional[str] = None,
    AdditionalColumn: Optional[str] = None,
    AdditionalFilterValue: Optional[str] = None,
    CategoryId: Optional[int] = None,
    db_files: Session = Depends(get_files_db),
    db_main: Session = Depends(get_db)
):
    schema = f"{ProjectNumber}_{DatasetType.lower()}"
    
    # Handle multiple category filter values
    if categoryFilterValue and ',' in categoryFilterValue:
        category_values = [v.strip() for v in categoryFilterValue.split(',')]
        category_in_list = "','".join(category_values)
        category_condition = f"{categoryColumn} IN ('{category_in_list}')"
    else:
        category_condition = f"{categoryColumn} = :category_filter"
    
    # Case 1: Both category and additional filters
    if categoryColumn and categoryFilterValue and AdditionalFilterValue and AdditionalColumn:
        if ',' in categoryFilterValue:
            category_values = [v.strip() for v in categoryFilterValue.split(',')]
            category_in_list = "','".join(category_values)
            query = text(f"""
                SELECT DISTINCT {sourceColumn}
                FROM [{schema}].[{sourceTable}]
                WHERE USUBJID = :usubjid 
                  AND {categoryColumn} IN ('{category_in_list}')
                  AND {AdditionalColumn} = :additional_filter
            """)
            result = db_files.execute(query, {
                "usubjid": USUBJID,
                "additional_filter": AdditionalFilterValue
            }).fetchall()
        else:
            query = text(f"""
                SELECT DISTINCT {sourceColumn}
                FROM [{schema}].[{sourceTable}]
                WHERE USUBJID = :usubjid 
                  AND {categoryColumn} = :category_filter 
                  AND {AdditionalColumn} = :additional_filter
            """)
            result = db_files.execute(query, {
                "usubjid": USUBJID,
                "category_filter": categoryFilterValue,
                "additional_filter": AdditionalFilterValue
            }).fetchall()
        
        db_values = [row[0] for row in result if row[0] is not None and row[0] != '']
        
        # Special handling for AEENDTC when values are empty
        if not db_values and sourceColumn.upper() == 'AEENDTC':
            db_values = ["ONGOING"]
        if not db_values and sourceColumn.upper() == 'PRCAT':
            db_values = ["No categories"]
        if not db_values and sourceColumn.upper() == 'CMCAT':
            db_values = ["No categories"]
        if not db_values and sourceColumn.upper() == 'CMINDC':
            db_values = ["No indications"]
        if not db_values and sourceColumn.upper() == 'PRINDC':
            db_values = ["No indications"]
            
    # Case 2: Only category filter
    elif categoryColumn and categoryFilterValue:
        if ',' in categoryFilterValue:
            category_values = [v.strip() for v in categoryFilterValue.split(',')]
            category_in_list = "','".join(category_values)
            query = text(f"""
                SELECT DISTINCT {sourceColumn} 
                FROM [{schema}].[{sourceTable}] 
                WHERE USUBJID = :usubjid AND {categoryColumn} IN ('{category_in_list}')
            """)
            result = db_files.execute(query, {
                "usubjid": USUBJID
            }).fetchall()
        else:
            query = text(f"""
                SELECT DISTINCT {sourceColumn} 
                FROM [{schema}].[{sourceTable}] 
                WHERE USUBJID = :usubjid AND {categoryColumn} = :category_filter
            """)
            result = db_files.execute(query, {
                "usubjid": USUBJID, 
                "category_filter": categoryFilterValue
            }).fetchall()
        
        db_values = [row[0] for row in result if row[0] is not None and row[0] != '']
        
        # Special handling for empty values
        if not db_values and sourceColumn.upper() == 'AEENDTC':
            db_values = ["ONGOING"]
        if not db_values and sourceColumn.upper() == 'PRCAT':
            db_values = ["No categories"]
        if not db_values and sourceColumn.upper() == 'CMCAT':
            db_values = ["No categories"]
        if not db_values and sourceColumn.upper() == 'CMINDC':
            db_values = ["No indications"]
        if not db_values and sourceColumn.upper() == 'PRINDC':
            db_values = ["No indications"]
    
    # Case 3: No filters
    else:
        query = text(f"""
            SELECT DISTINCT {sourceColumn} 
            FROM [{schema}].[{sourceTable}] 
            WHERE USUBJID = :usubjid
        """)
        result = db_files.execute(query, {"usubjid": USUBJID}).fetchall()
        db_values = [row[0] for row in result if row[0] is not None and row[0] != '']
        
        # Special handling for empty values
        if not db_values and sourceColumn.upper() == 'AEENDTC':
            db_values = ["ONGOING"]
        if not db_values and sourceColumn.upper() == 'PRCAT':
            db_values = ["No categories"]
        if not db_values and sourceColumn.upper() == 'CMCAT':
            db_values = ["No categories"]
        if not db_values and sourceColumn.upper() == 'CMINDC':
            db_values = ["No indications"]
        if not db_values and sourceColumn.upper() == 'PRINDC':
            db_values = ["No indications"]
            
    
    # Filter against LabAnalytes if CategoryId provided
    if CategoryId:
        lab_analytes = db_main.query(LabAnalytes).filter(
            LabAnalytes.CategoryId == CategoryId
        ).first()
        
        if lab_analytes and lab_analytes.LabTest:
            allowed_tests_lower = [test.lower() for test in lab_analytes.LabTest]
            filtered_values = [val for val in db_values if val.lower() in allowed_tests_lower]
            return {"values": filtered_values}
    
    return {"values": db_values}

@router.get("/GetMessageById", tags=["Predefined Template Query"])
def get_message_by_id(
    Id: int,
    toggleType: str,
    Isdownload: int,
    db: Session = Depends(get_db)
):
    msg = (
        db.query(ClinicalQueryMessage)
        .options(joinedload(ClinicalQueryMessage.user_query_by))
        .filter(ClinicalQueryMessage.Id == Id)
        .first()
    )
    
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Handle Excel download for table toggle type
    if toggleType.lower() == "table" and Isdownload == 1:
        try:
            # Parse the summary data from StandardTableContent
            if isinstance(msg.StandardTableContent, dict):
                content_data = msg.StandardTableContent
            else:
                try:
                    content_data = json.loads(msg.StandardTableContent)
                except json.JSONDecodeError:
                    content_data = ast.literal_eval(msg.StandardTableContent)
            
            summary_str = content_data.get("summary", "[]")
            if isinstance(summary_str, list):
                summary_data = summary_str
            else:
                try:
                    summary_data = json.loads(summary_str)
                except json.JSONDecodeError:
                    summary_data = ast.literal_eval(summary_str)
            
            if summary_data and isinstance(summary_data, list):
                # Create DataFrame from the data
                df = pd.DataFrame(summary_data)
                
                # Create Excel file in memory
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Query Results', index=False)
                
                output.seek(0)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"StandardQueryResult_{timestamp}.xlsx"
                # Return as downloadable Excel file
                return StreamingResponse(
                    BytesIO(output.read()),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            else:
                raise HTTPException(status_code=400, detail="No data available for download")
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating Excel file: {str(e)}")
    
    # Regular response flow
    if toggleType.lower() == "table" and Isdownload == 0:
        content = msg.StandardTableContent
    else:  # toggleType == "summary"
        content = msg.Content
    
    return {
        "Id": msg.Id,
        "CreatedAt": msg.CreatedAt,
        "Sender": msg.Sender,
        "Content": content,
        "Metadata": msg.Metadata,
        "FeedbackType": msg.FeedbackType,
        "FeedbackComment": msg.FeedbackComment,
        "FeedbackAt": msg.FeedbackAt,
        "QueryBy": msg.QueryBy,
        "ViewType": msg.ViewType,
        "User": {
            "UserId": msg.user_query_by.UserId,
            "UserName": msg.user_query_by.UserName
        } if msg.user_query_by else None
    }