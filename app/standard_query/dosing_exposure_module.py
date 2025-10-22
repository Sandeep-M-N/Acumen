def handle_dosing_exposure_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Dosing and Exposure module - EX table"""
    
    base_where = f"FROM {schema}.EX WHERE USUBJID = '{usubject}'"
    
    if QuestionType.lower() == "summary":
        sql_query = f"SELECT EXTRT as 'Treatment (EXTRT)', MIN(EXSTDTC) as 'First Dose Start Date (EXSTDTC)', MIN(EXSTDY) as 'First Dose Study Day (EXSTDY)', MAX(EXENDTC) as 'Last Dose End Date (EXENDTC)', MAX(EXENDY) as 'Last Dose Study Day (EXENDY)' {base_where} GROUP BY EXTRT ORDER BY MIN(EXSTDTC)"
    
    elif QuestionType.lower() == "modification":
        sql_query = f"SELECT EXTRT as 'Name of Treatment (EXTRT)', CONCAT(EXDOSE, ' ', EXDOSU) as 'Dose (EXDOSE)/Dose Units (EXDOSU)', EXDOSFRQ as 'Dosing Frequency per Interval (EXDOSFRQ)', EXSTDTC as 'Start Date/Time of Treatment (EXSTDTC)', EXSTDY as 'Study Day of Start of Treatment (EXSTDY)', EXADJ as 'Reason for Dose Adjustment (EXADJ)' {base_where} AND (EXADJ LIKE '%Increased%' OR EXADJ LIKE '%Withdrawn%' OR EXADJ LIKE '%Reduced%') ORDER BY EXSTDTC"
    
    elif QuestionType.lower() == "interruption":
        sql_query = f"SELECT EXTRT as 'Name of Treatment (EXTRT)', CONCAT(EXDOSE, ' ', EXDOSU) as 'Dose (EXDOSE)/Dose Units (EXDOSU)', EXDOSFRQ as 'Dosing Frequency per Interval (EXDOSFRQ)', EXSTDTC as 'Start Date/Time of Treatment (EXSTDTC)', EXSTDY as 'Study Day of Start of Treatment (EXSTDY)', EXADJ as 'Reason for Dose Adjustment (EXADJ)' {base_where} AND (EXADJ LIKE '%Delayed%' OR EXADJ LIKE '%Held%' OR EXADJ LIKE '%Interrupted%' OR EXADJ LIKE '%Missed%') ORDER BY EXSTDTC"
    
    else:
        raise ValueError(f"Query type '{QuestionType}' is not supported. Available types: summary, modification, interruption")
    
    result = db.run_no_throw(sql_query, fetch='all', include_columns=True)
    
    return {
        "query": sql_query,
        "query_result": result if result else "No data found"
    }