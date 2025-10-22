def handle_vital_signs_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Vital Signs module - VS table"""
    vstests = query_data.get("VSTEST", "").split(",")
    
    # Use hardcoded column mapping
    column_mapping = {
        'VSTEST': 'Vital Signs Test Name',
        'VSSTRESN': 'Numeric Result/Finding in Standard Units', 
        'VSSTRESU': 'Standard Units',
        'VSDTC': 'Date/Time of Measurements',
        'VSDY': 'Study Day of Vital Signs'
    }
    
    # Build single-line select clause
    select_clause = f"SELECT VSTEST as '{column_mapping.get('VSTEST', 'VSTEST')}', VSSTRESN as '{column_mapping.get('VSSTRESN', 'VSSTRESN')}', VSSTRESU as '{column_mapping.get('VSSTRESU', 'VSSTRESU')}', VSDTC as '{column_mapping.get('VSDTC', 'VSDTC')}', VSDY as '{column_mapping.get('VSDY', 'VSDY')}'"
    
    # For subqueries, use plain column names
    subquery_select = "SELECT VSTEST, VSSTRESN, VSSTRESU, VSDTC, VSDY"
    
    # Fix the syntax error by separating the test list creation
    test_list = ','.join([f"'{test.strip()}'" for test in vstests])
    base_where = f"FROM {schema}.VS WHERE USUBJID = '{usubject}' AND VSTEST IN ({test_list})"
    
    if QuestionType.lower() == "at_time":
        if not aestdtc:
            raise ValueError("AESTDTC is required for at_time query type")
        sql_query = f"{select_clause} FROM ({subquery_select}, ROW_NUMBER() OVER (PARTITION BY VSTEST ORDER BY CASE WHEN TRY_CAST(LEFT(VSDTC, 10) AS DATE) = '{aestdtc}' THEN 0 ELSE 1 END, ABS(DATEDIFF(day, TRY_CAST(LEFT(VSDTC, 10) AS DATE), '{aestdtc}'))) as rn {base_where}) ranked WHERE rn = 1"
    
    elif QuestionType.lower() == "prior":
        if not aestdtc:
            raise ValueError("AESTDTC is required for prior query type")
        sql_query = f"{select_clause} FROM ({subquery_select}, ROW_NUMBER() OVER (PARTITION BY VSTEST ORDER BY VSDTC DESC) as rn {base_where} AND TRY_CAST(LEFT(VSDTC, 10) AS DATE) <= '{aestdtc}') ranked WHERE rn = 1"
    
    elif QuestionType.lower() == "during":
        if not aestdtc or not aeendtc:
            raise ValueError("AESTDTC and AEENDTC are required for during query type")
        sql_query = f"{select_clause} {base_where} AND TRY_CAST(LEFT(VSDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND '{aeendtc}' ORDER BY VSDTC, VSTEST"

    elif QuestionType.lower() == "within_days":
        if not aestdtc or days is None:
            raise ValueError("AESTDTC and Days are required for within_days query type")
        if days >= 0:
            within_days_condition = f"AND TRY_CAST(LEFT(VSDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND DATEADD(day, {days}, '{aestdtc}')"
        else:
            within_days_condition = f"AND TRY_CAST(LEFT(VSDTC, 10) AS DATE) BETWEEN DATEADD(day, {days}, '{aestdtc}') AND '{aestdtc}'"
        sql_query = f"{select_clause} {base_where} {within_days_condition} ORDER BY VSDTC, VSTEST"
    
    else:
        raise ValueError(f"Query type '{QuestionType}' is not supported. Available types: at_time, prior, during, within_days")
    
    sql_query = ' '.join(sql_query.split())
    
    # Execute query with column headers
    result = db.run_no_throw(sql_query, fetch='all', include_columns=True)
    
    # Return query and result with headers
    return {
        "query": sql_query,
        "query_result": result if result else "No data found"
    }