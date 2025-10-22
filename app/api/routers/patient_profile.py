from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.project import PatientProfileRequest
from app.db.session import get_db, get_files_db
from datetime import datetime
from typing import List, Dict, Any
import os
import logging
from app.core.security import azure_ad_dependency
from app.models.user import User ,Project,DomainClassification, PatientProfileConfig
import re, io
import pandas as pd
from sqlalchemy.exc import ProgrammingError, OperationalError
from fastapi.responses import StreamingResponse
from sqlalchemy import text, bindparam
import time
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

@router.get("/GetSchemaInfo/Tables", tags=["Patient Profile"])
def get_schema_tables(ProjectNumber: str, FolderName: str,
                      db_files: Session = Depends(get_files_db),
                      db_main: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    schema_name = f"{ProjectNumber}_{FolderName}".lower()

    # Get all tables for schema
    query = text("""
        SELECT DISTINCT
            t.name AS TableName
        FROM 
            sys.tables t
        JOIN 
            sys.schemas s ON t.schema_id = s.schema_id
        WHERE 
            s.name = :schema_name
        ORDER BY t.name
    """)
    result = db_files.execute(query, {"schema_name": schema_name}).fetchall()

    if not result:
        raise HTTPException(status_code=404, detail=f"No tables found in schema {schema_name}")

    # Domain lookup
    domain_map = {
        d.DomainName.lower(): d.DomainFullName
        for d in db_main.query(DomainClassification).all()
    }

    # PatientProfileConfig
    configs = db_main.query(PatientProfileConfig).filter(
        PatientProfileConfig.ProjectNumber == ProjectNumber,
        PatientProfileConfig.DatasetType == FolderName
    ).all()

    table_config_map = {cfg.TableName.lower(): True for cfg in configs}

    # Build response
    tables_list = []
    for row in result:
        tname = row.TableName.lower()
        tables_list.append({
            "TableName": tname,
            "DomainFullName": domain_map.get(tname, tname.upper()),
            "isCheck": table_config_map.get(tname, False)
        })

    return tables_list

@router.get("/GetSchemaInfo/Columns", tags=["Patient Profile"])
def get_schema_columns(ProjectNumber: str, FolderName: str, TableName: str,
                       db_files: Session = Depends(get_files_db),
                       db_main: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    schema_name = f"{ProjectNumber}_{FolderName}".lower()

    query = text("""
        SELECT 
            c.name AS ColumnName,
            ep.value AS Description
        FROM 
            sys.columns c
        JOIN 
            sys.tables t ON c.object_id = t.object_id
        JOIN 
            sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN 
            sys.extended_properties ep 
            ON ep.major_id = c.object_id 
            AND ep.minor_id = c.column_id 
            AND ep.name = 'MS_Description'
        WHERE 
            s.name = :schema_name
            AND t.name = :table_name
        ORDER BY c.column_id
    """)
    result = db_files.execute(query, {"schema_name": schema_name, "table_name": TableName}).fetchall()

    if not result:
        raise HTTPException(status_code=404, detail=f"No columns found for {TableName}")

    # Get PatientProfileConfig for this table
    config = db_main.query(PatientProfileConfig).filter(
        PatientProfileConfig.ProjectNumber == ProjectNumber,
        PatientProfileConfig.DatasetType == FolderName,
        PatientProfileConfig.TableName == TableName
    ).first()

    selected_cols = [c.strip().upper() for c in config.SelectedColumns.split(",")] if config and config.SelectedColumns else []

    # Build response
    columns_list = []
    for row in result:
        col_name = row.ColumnName.upper()
        columns_list.append({
            "ColumnName": row.ColumnName,
            "Description": row.Description if row.Description else row.ColumnName,
            "isCheck": col_name in selected_cols
        })

    return columns_list

@router.post("/PatientProfileConfig", tags=["Patient Profile"])
def upsert_patient_profile_config(
    req: PatientProfileRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(azure_ad_dependency)
):
    project = db.query(Project).filter(Project.ProjectNumber == req.ProjectNumber).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {req.ProjectNumber} not found")

    user = db.query(User).filter(User.ObjectId == current_user.get("ObjectId")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now()
    
    # Get all existing configs for this project
    existing_configs = db.query(PatientProfileConfig).filter(
        PatientProfileConfig.ProjectNumber == project.ProjectNumber
    ).all()
    
    # Create maps for processing
    existing_map = {f"{cfg.DatasetType}_{cfg.TableName}".lower(): cfg for cfg in existing_configs}
    payload_tables = {f"{tbl.FolderName}_{tbl.TableName}".lower(): tbl for tbl in req.Tables}
    
    # Process each table in payload
    for tbl in req.Tables:
        # Skip if SelectedColumns is empty
        if not tbl.SelectedColumns:
            continue
            
        key = f"{tbl.FolderName}_{tbl.TableName}".lower()
        
        if key in existing_map:
            # Update existing record
            existing_map[key].SelectedColumns = ",".join(tbl.SelectedColumns)
            existing_map[key].ModifiedAt = now
            existing_map[key].ModifiedBy = user.UserId
        else:
            # Create new record
            db.add(PatientProfileConfig(
                ProjectNumber=project.ProjectNumber,
                DatasetType=tbl.FolderName,
                TableName=tbl.TableName,
                SelectedColumns=",".join(tbl.SelectedColumns),
                CreatedAt=now,
                CreatedBy=user.UserId
            ))
    
    # Delete records not present in payload
    for key, cfg in existing_map.items():
        if key not in payload_tables:
            db.delete(cfg)
    
    db.commit()
    return {"message": "Patient profile config synchronized successfully"}

@router.get("/GetSelectedColumnsWithData",tags=["Patient Profile"])
def get_selected_columns_with_data(
    project_number: str,
    foldername: str,          # e.g. "SDTM"
    filename: str,            # e.g. "fa"
    page: int = 1,
    page_size: int = 100,
    db_files: Session = Depends(get_files_db),  # files DB (schemas: <project>_<folder>)
    db_main: Session  = Depends(get_db)         # main DB (PatientProfileConfig, DomainClassification)
):
    try:
        # Build names as provided; compare case-insensitively in existence checks
        schema = f"{project_number}_{foldername}"
        table  = filename
        offset = (page - 1) * page_size

        # 0) Ensure target table exists (case-insensitive)
        exists = db_files.execute(text("""
            SELECT TOP 1 1
            FROM sys.tables t
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            WHERE LOWER(s.name) = LOWER(:schema)
              AND LOWER(t.name) = LOWER(:table)
        """), {"schema": schema, "table": table}).scalar()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Table '{schema.lower()}.{table.lower()}' does not exist.")

        # 1) Get SelectedColumns from PatientProfileConfig
        cfg = db_main.execute(text("""
            SELECT SelectedColumns, CreatedAt, CreatedBy
            FROM PatientProfileConfig
            WHERE ProjectNumber = :project_number
              AND DatasetType  = :dataset_type
              AND TableName    = :table_name
        """), {
            "project_number": project_number,
            "dataset_type":   foldername,
            "table_name":     table
        }).mappings().first()

        if not cfg:
            raise HTTPException(
                status_code=404,
                detail=f"No PatientProfileConfig found for ProjectNumber={project_number}, DatasetType={foldername}, TableName={table}"
            )

        selected_columns = [c.strip() for c in (cfg["SelectedColumns"] or "").split(",") if c.strip()]
        if not selected_columns:
            raise HTTPException(status_code=400, detail=f"No SelectedColumns configured for {table}")

        # 2) Lookup DomainFullName from DomainClassification
        domain_map = {
            d.DomainName.lower(): d.DomainFullName
            for d in db_main.query(DomainClassification).all()
        }
        domain_full_name = domain_map.get(table.lower())

        # 3) Fetch descriptions for ONLY the selected columns
        desc_rows = db_files.execute(
            text("""
                SELECT 
                    c.name AS ColumnName,
                    ISNULL(ep.value, c.name) AS Description
                FROM sys.columns c
                JOIN sys.tables  t ON c.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                LEFT JOIN sys.extended_properties ep 
                       ON ep.major_id = c.object_id 
                      AND ep.minor_id = c.column_id 
                      AND ep.name     = 'MS_Description'
                WHERE LOWER(s.name) = LOWER(:schema)
                  AND LOWER(t.name) = LOWER(:table)
                  AND c.name IN :cols
            """).bindparams(bindparam("cols", expanding=True)),
            {"schema": schema, "table": table, "cols": selected_columns}
        ).fetchall()

        desc_map = {r.ColumnName: r.Description for r in desc_rows}
        selected_with_desc = [{"ColumnName": col, "Description": desc_map.get(col, col)}
                              for col in selected_columns]

        # 4) Query ONLY the selected columns with pagination
        cols_sql = ", ".join(f"[{c}]" for c in selected_columns)
        data_sql = f"""
            SELECT {cols_sql}
            FROM [{schema}].[{table}]
            ORDER BY TRY_CAST(ROWID AS INT)
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        """
        df = pd.read_sql(data_sql, db_files.bind)

        # 5) Total count
        total = int(pd.read_sql(f"SELECT COUNT(*) AS total FROM [{schema}].[{table}]", db_files.bind).iloc[0]["total"])

        # 6) Response
        return {
            "ProjectNumber": project_number,
            "DatasetType": foldername,
            "TableName": table,
            "DomainFullName": domain_full_name,     # from DomainClassification
            "SelectedColumns": selected_with_desc,  # only configured columns + descriptions
            "CreatedAt": cfg["CreatedAt"],
            "CreatedBy": cfg["CreatedBy"],
            "page": page,
            "page_size": page_size,
            "total": total,
            "data": df.fillna("").to_dict(orient="records")  # only selected columns in data
        }

    except (ProgrammingError, OperationalError):
        # Keep detail aligned with existence message for clarity
        raise HTTPException(status_code=404, detail=f"Table '{schema.lower()}.{table.lower()}' does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

INVALID_SHEET_CHARS = r'[:\\/?*\[\]]'

def _sanitize_sheet_name(name: str, used: set) -> str:
    """Excel sheet name: max 31 chars, no invalid chars, unique."""
    base = re.sub(INVALID_SHEET_CHARS, "_", (name or "Sheet")).strip().strip("'")
    if not base:
        base = "Sheet"
    base = base[:31]
    candidate = base
    i = 1
    while candidate in used:
        suffix = f"_{i}"
        candidate = (base[:31 - len(suffix)] + suffix)
        i += 1
    used.add(candidate)
    return candidate

@router.get("/ExportPatientProfile", tags=["Patient Profile"])
def export_patient_profile_config(
    ProjectNumber: str,
    db_files: Session = Depends(get_files_db),
    db_main: Session = Depends(get_db),
):
    start_time = time.time()
    print(f"ExportPatientProfile started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1) Load configs for this project
    configs = db_main.execute(
        text("""
            SELECT DatasetType, TableName, SelectedColumns
            FROM PatientProfileConfig
            WHERE ProjectNumber = :p
            ORDER BY DatasetType, TableName
        """),
        {"p": ProjectNumber},
    ).mappings().all()

    if not configs:
        raise HTTPException(status_code=404, detail=f"No PatientProfileConfig rows found for Project {ProjectNumber}.")

    # 2) DomainName -> DomainFullName map
    domain_map = {
        d.DomainName.lower(): d.DomainFullName
        for d in db_main.query(DomainClassification).all()
    }

    output = io.BytesIO()
    used_sheet_names = set()
    errors = []

    # Batch get all column info for all tables at once
    all_schemas_tables = [(f"{ProjectNumber}_{(cfg['DatasetType'] or '').lower()}".lower(), (cfg['TableName'] or '').lower()) for cfg in configs]
    
    # Get all column descriptions in one query per schema
    all_desc_maps = {}
    for schema, table in set(all_schemas_tables):
        try:
            desc_rows = db_files.execute(
                text("""
                    SELECT c.name AS ColumnName, CAST(ep.value AS NVARCHAR(4000)) AS Description
                    FROM sys.columns c
                    JOIN sys.tables t ON c.object_id = t.object_id
                    JOIN sys.schemas s ON t.schema_id = s.schema_id
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = c.object_id
                       AND ep.minor_id = c.column_id
                       AND ep.name = 'MS_Description'
                    WHERE s.name = :schema AND t.name = :table
                """),
                {"schema": schema, "table": table},
            ).fetchall()
            all_desc_maps[(schema, table)] = {r.ColumnName.upper(): (r.Description or r.ColumnName) for r in desc_rows}
        except:
            all_desc_maps[(schema, table)] = {}

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for cfg in configs:
            file_start_time = time.time()
            dataset_type = (cfg["DatasetType"] or "").lower()
            table = (cfg["TableName"] or "").lower()
            selected_raw = (cfg["SelectedColumns"] or "")
            selected_cols = [c.strip() for c in selected_raw.split(",") if c.strip()]

            if not dataset_type or not table or not selected_cols:
                errors.append({
                    "Table": table or "(missing)",
                    "Error": "Missing DatasetType, TableName or SelectedColumns in PatientProfileConfig.",
                    "ProcessingTime": f"{time.time() - file_start_time:.2f}s"
                })
                continue

            schema = f"{ProjectNumber}_{dataset_type}".lower()
            desc_map = all_desc_maps.get((schema, table), {})
            
            # Build SELECT for selected columns
            select_list = ", ".join(f"[{c}]" for c in selected_cols)
            sql = f"SELECT {select_list} FROM [{schema}].[{table}]"

            try:
                df = pd.read_sql(sql, db_files.bind)
            except Exception as e:
                errors.append({
                    "Table": f"{schema}.{table}", 
                    "Error": f"Data read failed: {e}",
                    "ProcessingTime": f"{time.time() - file_start_time:.2f}s"
                })
                continue

            # Rename headers to "Description (ColumnName)"
            df.columns = [f"{desc_map.get(c.upper(), c)} ({c})" for c in selected_cols]

            # Sheet name = DomainFullName (fallback to UPPER(table))
            domain_full_name = domain_map.get(table, table.upper())
            sheet_name = _sanitize_sheet_name(f"{domain_full_name} ({table.upper()})", used_sheet_names)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            file_processing_time = time.time() - file_start_time
            print(f"Processed {schema}.{table} in {file_processing_time:.2f}s")

        # Error sheet (if needed)
        if errors:
            error_columns = ["Table", "Error", "ProcessingTime"] if any("ProcessingTime" in err for err in errors) else ["Table", "Error"]
            pd.DataFrame(errors, columns=error_columns).to_excel(
                writer, sheet_name="Table_Error", index=False
            )

    output.seek(0)
    filename = f"{ProjectNumber}_PatientProfile_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    
    total_time = time.time() - start_time
    print(f"ExportPatientProfile completed in: {total_time:.2f}s at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/GetProjectDomains",tags=["Patient Profile"])
def get_project_domains(ProjectNumber: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Fetch all TableName entries for a given ProjectNumber from PatientProfileConfig,
    and return with corresponding DomainFullName from DomainClassification.
    """

    # 1. Get all PatientProfileConfig rows for the ProjectNumber
    configs = (
        db.query(PatientProfileConfig)
        .filter(PatientProfileConfig.ProjectNumber == ProjectNumber)
        .all()
    )

    if not configs:
        # ✅ Use HTTPException so API responds properly with error
        raise HTTPException(
            status_code=404,
            detail=f"No tables found for ProjectNumber {ProjectNumber}"
        )

    # 2. Create a map of DomainName -> DomainFullName
    domain_map = {
        d.DomainName.lower(): d.DomainFullName
        for d in db.query(DomainClassification).all()
    }

    # 3. Prepare output
    result = []
    for cfg in configs:
        domain_full_name = domain_map.get(cfg.TableName.lower(), "Unknown Domain")
        result.append({
            "ProjectNumber": cfg.ProjectNumber,
            "DatasetType": cfg.DatasetType,
            "TableName": cfg.TableName,
            "DomainFullName": domain_full_name
        })

    return result