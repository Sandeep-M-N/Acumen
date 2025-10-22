def handle_medications_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Medications module with prior_during, during, within_days"""
    if QuestionType not in ["prior_during", "during", "within_days"]:
        raise ValueError(f"Medications module only supports: prior_during, during, within_days")
    
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
    cmcat_list = query_data.get("CMCAT", "").split(",") if query_data.get("CMCAT") else []
    cmindc_list = query_data.get("CMINDC", "").split(",") if query_data.get("CMINDC") else []
    
    # Column mapping with full descriptive names
    column_mapping = {
        'CMDECOD':	'Standardized Medication Name',
        'CMTRT': 'Medication/Treatment',
        'CMDOSE': 'Dose per Administration',
        'CMDOSU': 'Dose Units',
        'CMSTDTC': 'Start Date/Time of Medication',
        'CMENDTC': 'End Date/Time of Medication',
        'CMROUTE': 'Route of Administration',
        'CMSTDY': 'Study Day of Start of Medication',
        'CMENDY': 'Study Day of End of Medication'
    }
    
    select_clause = f"SELECT CMDECOD as '{column_mapping['CMDECOD']}', CMTRT as '{column_mapping['CMTRT']}', CMDOSE as '{column_mapping['CMDOSE']}', CMDOSU as '{column_mapping['CMDOSU']}', CMSTDTC as '{column_mapping['CMSTDTC']}', CMENDTC as '{column_mapping['CMENDTC']}'"
    base_where = f"FROM {schema}.CM WHERE USUBJID = '{usubject}'"
    
    # Add CMCAT filter if provided (skip if default "No categories")
    if cmcat_list and cmcat_list[0].strip() and cmcat_list[0].strip() != "No categories":
        cmcat_filter = ','.join([f"'{cat.strip()}'" for cat in cmcat_list])
        base_where += f" AND CMCAT IN ({cmcat_filter})"
    
    # Add CMINDC filter if provided (skip if default "No indications")
    if cmindc_list and cmindc_list[0].strip() and cmindc_list[0].strip() != "No indications":
        cmindc_filter = ','.join([f"'{indc.strip()}'" for indc in cmindc_list])
        base_where += f" AND CMINDC IN ({cmindc_filter})"
    
    if QuestionType == "prior_during":
        # Get study dates from DM table
        dm_query = f"SELECT RFSTDTC, RFENDTC FROM {schema}.DM WHERE USUBJID = '{usubject}'"
        dm_result = db.run_no_throw(dm_query, fetch='one')
        
        if not dm_result or dm_result == "No data found":
            raise ValueError(f"No study dates found for subject {usubject}")
        
        # Extract dates properly from nested structure
        from datetime import datetime, timedelta
        
        if isinstance(dm_result, str):
            # Parse string result like "[('2021-08-05', '2021-08-10')]"
            import ast
            dm_result = ast.literal_eval(dm_result)
        
        # Extract first date from result
        if isinstance(dm_result, (list, tuple)) and len(dm_result) > 0:
            first_row = dm_result[0]
            if isinstance(first_row, (list, tuple)) and len(first_row) > 0:
                rfstdtc = first_row[0]
                rfendtc = first_row[1] if len(first_row) > 1 else first_row[0]
            else:
                rfstdtc = first_row
                rfendtc = first_row
        else:
            rfstdtc = dm_result
            rfendtc = dm_result
        
        # Calculate 30 days prior to study start
        if not rfstdtc or rfstdtc == '' or rfstdtc is None:
            # Skip date calculation if rfstdtc is empty
            condition = ""
        else:
            try:
                rfstdtc_date = datetime.strptime(rfstdtc, '%Y-%m-%d')
                with_prior_dm_start = (rfstdtc_date - timedelta(days=30)).strftime('%Y-%m-%d')
                condition = f"""AND ((CMSTDTC IS NOT NULL AND TRY_CAST(LEFT(CMSTDTC, 10) AS DATE) BETWEEN '{with_prior_dm_start}' AND '{rfendtc}') 
                                 OR (CMENDTC IS NOT NULL AND TRY_CAST(LEFT(CMENDTC, 10) AS DATE) BETWEEN '{with_prior_dm_start}' AND '{rfendtc}') 
                                 OR (NULLIF(CMSTDTC, '') IS NULL OR NULLIF(CMENDTC, '') IS NULL))"""
            
            except ValueError:
                # Skip date calculation if date format is invalid
                condition = ""
    elif QuestionType == "during":
        if not aestdtc or not aeendtc:
            raise ValueError("AESTDTC and AEENDTC required for during")
        condition = f"AND TRY_CAST(LEFT(CMSTDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND '{aeendtc}'"
    elif QuestionType == "within_days":
        if not aestdtc or days is None:
            raise ValueError("AESTDTC and Days required for within_days")
        if days >= 0:
            condition = f"AND TRY_CAST(LEFT(CMSTDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND DATEADD(day, {days}, '{aestdtc}')"
        else:
            condition = f"AND TRY_CAST(LEFT(CMSTDTC, 10) AS DATE) BETWEEN DATEADD(day, {days}, '{aestdtc}') AND '{aestdtc}'"
    
    sql_query = f"{select_clause} {base_where} {condition} ORDER BY CMSTDTC"
    result = db.run_no_throw(sql_query, fetch='all', include_columns=True)
    
    return {
        "query": sql_query,
        "query_result": result if result else "No data found"
    }