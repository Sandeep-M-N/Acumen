def handle_disposition_outcome_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Disposition and Outcome module - DS table"""
    
    base_where = f"FROM {schema}.DS WHERE USUBJID = '{usubject}'"
    select_clause = "SELECT DSTERM as 'Reported Term for the Disposition Event (DSTERM)', DSDECOD as 'Standardized Disposition Term (DSDECOD)', DSSTDTC as 'Start Date/Time of Disposition Event (DSSTDTC)', DSSTDY as 'Study Day of Start of Disposition Event (DSSTDY)'"
    
    if QuestionType.lower() == "treatment_discontinuation":
        sql_query = f"{select_clause} {base_where} AND DSSCAT = 'END OF TREATMENT' ORDER BY DSSTDTC"
    
    elif QuestionType.lower() == "study_discontinuation":
        sql_query = f"{select_clause} {base_where} AND DSSCAT = 'END OF STUDY' ORDER BY DSSTDTC"
    
    else:
        raise ValueError(f"Query type '{QuestionType}' is not supported. Available types: treatment_discontinuation, study_discontinuation")
    
    result = db.run_no_throw(sql_query, fetch='all', include_columns=True)
    
    return {
        "query": sql_query,
        "query_result": result if result else "No data found"
    }