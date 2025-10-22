def handle_procedures_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Procedures module with study, prior_first, during, within_days"""
    if QuestionType not in ["study", "prior_first", "during", "within_days"]:
        raise ValueError(f"Procedures module only supports: study, prior_first, during, within_days")
    
    # Clean date parameters
    import re
    def clean_date(date_str):
        if not date_str:
            return None
        date_str = str(date_str)
        # Extract YYYY-MM-DD pattern
        match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
        return match.group(1) if match else date_str[:10]
    
    aestdtc = clean_date(aestdtc)
    aeendtc = clean_date(aeendtc)
    
    # Get user input filters
    prcat_list = query_data.get("PRCAT", "").split(",") if query_data.get("PRCAT") else []
    prindc_list = query_data.get("PRINDC", "").split(",") if query_data.get("PRINDC") else []
    
    # Column mapping with full descriptive names
    column_mapping = {
        'PRCAT': 'Category',
        'PRDECOD': 'Standardized Procedure Name',
        'PRTRT':	'Reported Name of Procedure',
        'PRENDTC': 'End Date/Time of Procedure',
        'PRENDY': 'Study Day of End of Procedure',
        'PRSTDTC': 'Start Date/Time of Procedure',
        'PRSTDY': 'Study Day of Start of Procedure'
    }
    
    select_clause = f"SELECT PRCAT as '{column_mapping['PRCAT']}', PRDECOD as '{column_mapping['PRDECOD']}', PRSTDTC as '{column_mapping['PRSTDTC']}', PRENDTC as '{column_mapping['PRENDTC']}', PRSTDY as '{column_mapping['PRSTDY']}', PRENDY as '{column_mapping['PRENDY']}'"
    base_where = f"FROM {schema}.PR WHERE USUBJID = '{usubject}'"
    
    # Add PRCAT filter if provided (skip if default "No categories")
    if prcat_list and prcat_list[0].strip() and prcat_list[0].strip() != "No categories":
        prcat_filter = ','.join([f"'{cat.strip()}'" for cat in prcat_list])
        base_where += f" AND PRCAT IN ({prcat_filter})"
    
    # Add PRINDC filter if provided (skip if default "No indications")
    if prindc_list and prindc_list[0].strip() and prindc_list[0].strip() != "No indications":
        prindc_filter = ','.join([f"'{indc.strip()}'" for indc in prindc_list])
        base_where += f" AND PRINDC IN ({prindc_filter})"
    
    if QuestionType == "study":
        # Get study dates from DM table
        dm_query = f"SELECT RFSTDTC, RFENDTC FROM {schema}.DM WHERE USUBJID = '{usubject}'"
        dm_result = db.run_no_throw(dm_query, fetch='one')
        
        if not dm_result or dm_result == "No data found":
            raise ValueError(f"No study dates found for subject {usubject}")
        
        # Extract and clean dates from result
        if isinstance(dm_result, str):
            import ast
            dm_result = ast.literal_eval(dm_result)
        
        if isinstance(dm_result, (list, tuple)) and len(dm_result) > 0:
            first_row = dm_result[0]
            if isinstance(first_row, (list, tuple)):
                rfstdtc = clean_date(first_row[0]) if len(first_row) > 0 else None
                rfendtc = clean_date(first_row[1]) if len(first_row) > 1 else rfstdtc
            else:
                rfstdtc = clean_date(first_row)
                rfendtc = rfstdtc
        else:
            rfstdtc = clean_date(dm_result)
            rfendtc = rfstdtc
        
        # Skip date filter if dates are None/missing
        if not rfstdtc or not rfendtc or rfstdtc == 'None' or rfendtc == 'None':
            condition = ""
        else:
            condition = f"AND TRY_CAST(LEFT(PRSTDTC, 10) AS DATE) BETWEEN '{rfstdtc}' AND '{rfendtc}'"
    elif QuestionType == "prior_first":
        # Get first dose date from EX table
        ex_query = f"SELECT MIN(EXSTDTC) FROM {schema}.EX WHERE USUBJID = '{usubject}'"
        ex_result = db.run_no_throw(ex_query, fetch='one')
        
        if not ex_result or ex_result == "No data found":
            raise ValueError(f"No exposure dates found for subject {usubject}")
        
        # Extract and clean date from result
        if isinstance(ex_result, str):
            import ast
            ex_result = ast.literal_eval(ex_result)
        
        if isinstance(ex_result, (list, tuple)) and len(ex_result) > 0:
            first_dose_date = clean_date(ex_result[0])
        else:
            first_dose_date = clean_date(ex_result)
        
        condition = f"AND TRY_CAST(LEFT(PRSTDTC, 10) AS DATE) < '{first_dose_date}'"
    elif QuestionType == "during":
        if not aestdtc or not aeendtc:
            raise ValueError("AESTDTC and AEENDTC required for during")
        condition = f"AND TRY_CAST(LEFT(PRSTDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND '{aeendtc}'"
    elif QuestionType == "within_days":
        if not aestdtc or days is None:
            raise ValueError("AESTDTC and Days required for within_days")
        if days >= 0:
            condition = f"AND TRY_CAST(LEFT(PRSTDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND DATEADD(day, {days}, '{aestdtc}')"
        else:
            condition = f"AND TRY_CAST(LEFT(PRSTDTC, 10) AS DATE) BETWEEN DATEADD(day, {days}, '{aestdtc}') AND '{aestdtc}'"
    
    sql_query = f"{select_clause} {base_where} {condition} ORDER BY PRSTDTC"
    result = db.run_no_throw(sql_query, fetch='all', include_columns=True)
    
    return {
        "query": sql_query,
        "query_result": result if result else "No data found"
    }
