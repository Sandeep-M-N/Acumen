def handle_adverse_events_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Adverse Events module"""
    
    # Use hardcoded column mapping
    column_mapping = {
        'AETOXGR': 'Grade/Severity',
        'AESTDTC': 'Start Date', 
        'AESTDY': 'Start Date Study Day',
        'AEENDY': 'End Date Study Day',
        'AEDECOD': 'Preferred Term'
    }
    
    # Build single-line select clause
    select_clause = f"SELECT AETOXGR as '{column_mapping.get('AETOXGR', 'AETOXGR')}', AESTDTC as '{column_mapping.get('AESTDTC', 'AESTDTC')}', AESTDY as '{column_mapping.get('AESTDY', 'AESTDY')}', AEENDY as '{column_mapping.get('AEENDY', 'AEENDY')}', AEDECOD as '{column_mapping.get('AEDECOD', 'AEDECOD')}'"
    
    # For subqueries, use plain column names
    subquery_select = "SELECT AETOXGR, AESTDTC, AESTDY, AEENDY, AEDECOD"
    
    base_where = f"FROM {schema}.AE WHERE USUBJID = '{usubject}'"
    
    # Common query templates (no date validation needed)
    query_templates = {
        "study": f"{select_clause} {base_where} ORDER BY AESTDTC, AEDECOD",
        "graph": f"{select_clause} {base_where} ORDER BY AESTDTC, AEDECOD"
    }
    
    # Date-dependent templates (require AESTDTC validation)
    if QuestionType.lower() in ["at_time", "prior"]:
        if not aestdtc:
            raise ValueError("AESTDTC is required for date-based query types")
        
        query_templates.update({
            "at_time": f"{select_clause} FROM ({subquery_select}, ROW_NUMBER() OVER (PARTITION BY AEDECOD ORDER BY CASE WHEN TRY_CAST(LEFT(AESTDTC, 10) AS DATE) = '{aestdtc}' THEN 0 ELSE 1 END, ABS(DATEDIFF(day, TRY_CAST(LEFT(AESTDTC, 10) AS DATE), '{aestdtc}'))) as rn {base_where}) ranked WHERE rn = 1",
            
            "prior": f"{select_clause} FROM ({subquery_select}, ROW_NUMBER() OVER (PARTITION BY AEDECOD ORDER BY AESTDTC DESC) as rn {base_where} AND TRY_CAST(LEFT(AESTDTC, 10) AS DATE) <= '{aestdtc}') ranked WHERE rn = 1"
        })
    
    elif QuestionType.lower() == "during":
        if not aestdtc or not aeendtc:
            raise ValueError("AESTDTC and AEENDTC are required for 'during' query type")
        query_templates["during"] = f"{select_clause} {base_where} AND TRY_CAST(LEFT(AESTDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND '{aeendtc}' ORDER BY AESTDTC, AEDECOD"

    elif QuestionType.lower() == "within_days":
        if not aestdtc or days is None:
            raise ValueError("AESTDTC and Days are required for 'within_days' query type")
        if days >= 0:
            within_days_condition = f"AND TRY_CAST(LEFT(AESTDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND DATEADD(day, {days}, '{aestdtc}')"
        else:
            within_days_condition = f"AND TRY_CAST(LEFT(AESTDTC, 10) AS DATE) BETWEEN DATEADD(day, {days}, '{aestdtc}') AND '{aestdtc}'"
        query_templates["within_days"] = f"{select_clause} {base_where} {within_days_condition} ORDER BY AESTDTC, AEDECOD"
    
    # Get query or raise error if not available
    if QuestionType.lower() not in query_templates:
        raise ValueError(f"Query type '{QuestionType}' is not supported")
    
    # Clean query - remove all extra whitespace and newlines
    sql_query = ' '.join(query_templates[QuestionType.lower()].split())
    
    # Execute query with column headers
    result = db.run_no_throw(sql_query, fetch='all', include_columns=True)
    
    # Return query and result with headers
    return {
        "query": sql_query,
        "query_result": result if result else "No data found"
    }