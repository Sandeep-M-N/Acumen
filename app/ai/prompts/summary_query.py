def get_prompts(table_name:str,query:str,last_message:str)->str:
    return f"""
                Generate a concise clinical trial narrative using ONLY the provided query result data.
                **Table:** {table_name}
                **Final Query:** {query}  
                **Data:** {last_message}

                Instructions:

                1. For each unique record in the results:
                    - If the data includes a USUBJID or subject-level identifier:
                        - Write one sentence per participant.
                        - For each data value:
                            - If ROWID exists, wrap the value in this tooltip HTML format:
                            <div class="tooltip">[VALUE]<div class="tooltiptext"><span class="display-none">[ROWID]</span> [TABLE], [COLUMN]</div></div>
                            - If ROWID is missing or null, output the value as plain text (no tooltip).
                        - Combine records only if **all values** match exactly.
                    - If the data is aggregate (e.g., a count or summary row without subject identifiers):
                        - Write a single, short sentence summarizing the result using plain text only.
                        - DO NOT use any HTML or tooltips.
                        - DO NOT mention column or table names.

                2. Narrative Text Rules:
                    - DO NOT reference column names or table names.
                    - DO NOT add introductory or closing sentences.
                    - Use only the exact values from the result.
                    - Keep the language atleast 1sentence minimal, factual, and grammatical.
                    - Preserve the original casing of values.

                3. Output Formatting Rules:
                    - Tooltip format must be:
                    <div class="tooltip">[VALUE]<div class="tooltiptext"><span class="display-none">[ROWID]</span> [TABLE], [COLUMN]</div></div>
                    - If no ROWID is present, show plain text.
                    - Always generate the briefest valid sentence possible.

                Example outputs:

                **Per-subject with tooltips:**
                Subject <div class="tooltip">MB344-20-001<div class="tooltiptext"><span class="display-none">82</span> SDTM.dm, USUBJID</div></div> experienced <div class="tooltip">Headache<div class="tooltiptext"><span class="display-none">82</span> SDTM.ae, AETERM</div></div>.

                **Aggregate (no ROWID):**  
                Across the study, 2 subjects experienced b-cell aplasia.
                """ 