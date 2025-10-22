def handle_lab_module(db, schema, query_data, usubject, aestdtc, aeendtc, days, QuestionType):
    """Handle Lab module - existing flow"""
    lbtests = query_data.get("LBTEST", "").split(",")
    lbcat = query_data.get("LBCAT", "Hematology")
    use_db_descriptions = 0  # 0 = use hardcoded, 1 = use DB
    
    # Column mapping based on flag
    if use_db_descriptions == 1:
        # Get column descriptions from database
        column_desc_query = f"""
        SELECT COLUMN_NAME, 
                ISNULL(CAST(ep.value AS NVARCHAR(255)), COLUMN_NAME) as DESCRIPTION
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN sys.extended_properties ep 
            ON ep.major_id = OBJECT_ID('{schema}.LB')
            AND ep.minor_id = COLUMNPROPERTY(OBJECT_ID('{schema}.LB'), c.COLUMN_NAME, 'ColumnId')
            AND ep.name = 'MS_Description'
        WHERE c.TABLE_SCHEMA = '{schema}' AND c.TABLE_NAME = 'LB'
        AND c.COLUMN_NAME IN ('LBTEST', 'LBSTRESC', 'LBSTRESU', 'LBSTNRLO', 'LBSTNRHI', 'LBDTC')
        ORDER BY c.COLUMN_NAME
        """
        
        # Execute column description query and build mapping
        column_info_result = db.run(column_desc_query)
        column_mapping = {}
        
        # Parse the result to build column mapping
        if column_info_result and column_info_result != "No data found":
            try:
                import ast
                if isinstance(column_info_result, str):
                    rows = ast.literal_eval(column_info_result) if column_info_result.startswith('[') else []
                else:
                    rows = column_info_result
                
                for row in rows:
                    if len(row) >= 2:
                        column_mapping[row[0]] = row[1]
            except:
                # Fallback to hardcoded if parsing fails
                column_mapping = {
                    'LBTEST': 'Lab Test or Examination Name',
                    'LBSTRESC': 'Character Result/Finding in Std Format', 
                    'LBSTRESU': 'Standard Units',
                    'LBSTNRLO': 'Reference Range Lower Limit-Std Units',
                    'LBSTNRHI': 'Reference Range Upper Limit-Std Units',
                    'LBDTC': 'Date/Time of Specimen Collection'
                }
        else:
            # Fallback to hardcoded
            column_mapping = {
                'LBTEST': 'Lab Test or Examination Name',
                'LBSTRESC': 'Character Result/Finding in Std Format', 
                'LBSTRESU': 'Standard Units',
                'LBSTNRLO': 'Reference Range Lower Limit-Std Units',
                'LBSTNRHI': 'Reference Range Upper Limit-Std Units',
                'LBDTC': 'Date/Time of Specimen Collection'
            }
    else:
        # Use hardcoded column mapping (faster)
        column_mapping = {
            'LBTEST': 'Lab Test or Examination Name',
            'LBSTRESC': 'Character Result/Finding in Std Format', 
            'LBSTRESU': 'Standard Units',
            'LBSTNRLO': 'Reference Range Lower Limit-Std Units',
            'LBSTNRHI': 'Reference Range Upper Limit-Std Units',
            'LBDTC': 'Date/Time of Specimen Collection'
        }
    
    # Build single-line select clause
    select_clause = f"SELECT LBTEST as '{column_mapping.get('LBTEST', 'LBTEST')}', LBSTRESC as '{column_mapping.get('LBSTRESC', 'LBSTRESC')}', LBSTRESU as '{column_mapping.get('LBSTRESU', 'LBSTRESU')}', ROUND(LBSTNRLO, 2) as '{column_mapping.get('LBSTNRLO', 'LBSTNRLO')}', ROUND(LBSTNRHI, 2) as '{column_mapping.get('LBSTNRHI', 'LBSTNRHI')}', LBDTC as '{column_mapping.get('LBDTC', 'LBDTC')}'"
    
    # For subqueries, use plain column names
    subquery_select = "SELECT LBTEST, LBSTRESC, LBSTRESU, LBSTNRLO, LBSTNRHI, LBDTC"
    
    # Fix the syntax error by separating the test list creation
    test_list = ','.join([f"'{test.strip()}'" for test in lbtests])
    base_where = f"FROM {schema}.LB WHERE USUBJID = '{usubject}' AND LBTEST IN ({test_list}) AND LBCAT = '{lbcat}'"
    
    # Common query templates (no date validation needed)
    query_templates = {
        "study": f"{select_clause} {base_where} ORDER BY LBDTC, LBTEST",
        "graph": f"{select_clause} {base_where} ORDER BY LBDTC, LBTEST"
    }
    
    # Date-dependent templates (require AESTDTC validation)
    if QuestionType.lower() in ["at_time", "prior"]:
        if not aestdtc:
            raise ValueError("AESTDTC is required for date-based query types")
        
        query_templates.update({
            "at_time": f"{select_clause} FROM ({subquery_select}, ROW_NUMBER() OVER (PARTITION BY LBTEST ORDER BY CASE WHEN TRY_CAST(LEFT(LBDTC, 10) AS DATE) = '{aestdtc}' THEN 0 ELSE 1 END, ABS(DATEDIFF(day, TRY_CAST(LEFT(LBDTC, 10) AS DATE), '{aestdtc}'))) as rn {base_where}) ranked WHERE rn = 1",
            
            "prior": f"{select_clause} FROM ({subquery_select}, ROW_NUMBER() OVER (PARTITION BY LBTEST ORDER BY LBDTC DESC) as rn {base_where} AND TRY_CAST(LEFT(LBDTC, 10) AS DATE) <= '{aestdtc}') ranked WHERE rn = 1"
        })
    
    elif QuestionType.lower() == "during":
        if not aestdtc or not aeendtc:
            raise ValueError("AESTDTC and AEENDTC are required for 'during' query type")
        query_templates["during"] = f"{select_clause} {base_where} AND TRY_CAST(LEFT(LBDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND '{aeendtc}' ORDER BY LBDTC, LBTEST"

    elif QuestionType.lower() == "within_days":
        if not aestdtc or days is None:
            raise ValueError("AESTDTC and Days are required for 'within_days' query type")
        if days >= 0:
            within_days_condition = f"AND TRY_CAST(LEFT(LBDTC, 10) AS DATE) BETWEEN '{aestdtc}' AND DATEADD(day, {days}, '{aestdtc}')"
        else:
            within_days_condition = f"AND TRY_CAST(LEFT(LBDTC, 10) AS DATE) BETWEEN DATEADD(day, {days}, '{aestdtc}') AND '{aestdtc}'"
        query_templates["within_days"] = f"{select_clause} {base_where} {within_days_condition} ORDER BY LBDTC, LBTEST"
    
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
