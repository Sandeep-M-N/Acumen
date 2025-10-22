from typing import Literal
from langchain_core.messages import AIMessage
import os
from langgraph.graph import END, MessagesState


generate_query_system_prompt = """
You are an intelligent agent designed to interact with a SQL database using the {dialect} SQL syntax.

Given a user question, generate a syntactically correct SQL query that retrieves only the relevant columns from the appropriate table(s).

If the user request implies a specific number of results, include a LIMIT clause using that value. Otherwise:

If the query is highly specific (e.g., based on primary keys or unique identifiers) and likely to return only exact matches, do not apply a limit.

Order the results by the most relevant column to surface the most useful or interesting entries.

⚠️ Do not perform any DML operations (INSERT, UPDATE, DELETE, DROP).
Always generate read-only queries.
"""

check_query_system_prompt = """
You are a SQL expert with a strong attention to detail.
Double check the {dialect} query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no mistakes,
just reproduce the original query.

You will call the appropriate tool to execute the query after running this check.
"""

def list_tables(tools):
    def _node(state):
        tool = next(t for t in tools if t.name == "sql_db_list_tables")
        tool_call = {"name": tool.name, "args": {}, "id": "abc123", "type": "tool_call"}
        tool_call_msg = AIMessage(content="", tool_calls=[tool_call])
        tool_msg = tool.invoke(tool_call)
        response = AIMessage(f"Available tables: {tool_msg.content}")
        return {"messages": [tool_call_msg, tool_msg, response]}
    return _node

def call_get_schema(llm, get_schema_tool):
    def _node(state):
        return {"messages": [llm.bind_tools([get_schema_tool]).invoke(state["messages"])]}
    return _node

def generate_query(llm, run_query_tool, db):
    def _node(state):
        sys_msg = {"role": "system", "content": generate_query_system_prompt.format(dialect=db.dialect)}
        return {"messages": [llm.bind_tools([run_query_tool]).invoke([sys_msg] + state["messages"])]}
    return _node

def check_query(llm, run_query_tool, db):
    def _node(state):
        sys_msg = {"role": "system", "content": check_query_system_prompt.format(dialect=db.dialect)}
        user_msg = {"role": "user", "content": state["messages"][-1].tool_calls[0]["args"]["query"]}
        res = llm.bind_tools([run_query_tool]).invoke([sys_msg, user_msg])
        res.id = state["messages"][-1].id
        return {"messages": [res]}
    return _node

def should_continue(state: MessagesState) -> Literal[END, "check_query"]:
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return END
    else:
        return "check_query"
