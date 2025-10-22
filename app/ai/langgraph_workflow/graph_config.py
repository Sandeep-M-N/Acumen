import os
from typing import Literal
import re
import json
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langchain.chat_models import init_chat_model
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from app.core.config import settings
from langchain_core.messages import ToolMessage, AIMessage
from langgraph.checkpoint.redis import RedisSaver
# from langgraph.store.redis import RedisStore
# from langgraph.store.base import BaseStore

from dotenv import load_dotenv
import ast
import time
from app.ai.prompts.generate_query import get_prompt as get_generate_query_prompt
from app.ai.prompts.check_query import get_prompt as get_check_query_prompt
from app.ai.prompts.summary_query import get_prompts as get_summary_prompt
load_dotenv()

is_redis = settings.REDIS_CONFIG
def build_agent(ProjectNumber: str, FolderName: str, LlmType: str, ModelName: str, Type: str):
    schema = f"{ProjectNumber}_{FolderName}"
    sql_server_conn_str = settings.DATABASE_URL_FILES
    start_time = time.time()
    db = SQLDatabase.from_uri(sql_server_conn_str, schema=schema, sample_rows_in_table_info=0)
    # print("⏱️ SQLDatabase init took", time.time() - start_time, "seconds")
    # 🧠 Decide LLM config based on LlmType
    if LlmType == "Azure OpenAI":
        deployment_name = ModelName
        model_provider = "azure_openai"
    elif LlmType == "OpenAI":
        deployment_name = ModelName  # or your preferred OpenAI model
        model_provider = "openai"
    else:
        raise ValueError(f"Unsupported LLM type: {LlmType}")
    
    api_key = settings.AZURE_OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env")

    llm = init_chat_model(
        deployment_name,
        model_provider=model_provider,
        temperature=0,
        api_key=api_key,
    )
    # print("✅ LLM initialized with:", LlmType)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    # for tool in tools:
    #     print(f"{tool.name}: {tool.description}\n")

    get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")
    get_schema_node = ToolNode([get_schema_tool], name="get_schema")

    run_query_tool = next(tool for tool in tools if tool.name == "sql_db_query")
    run_query_node = ToolNode([run_query_tool], name="run_query")


    # Example: create a predetermined tool call
    def list_tables(state: MessagesState):
        print("List tables....................")
        tool_call = {
            "name": "sql_db_list_tables",
            "args": {},
            "id": "abc123",
            "type": "tool_call",
        }
        tool_call_message = AIMessage(content="", tool_calls=[tool_call])

        list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
        tool_message = list_tables_tool.invoke(tool_call)
        # response = AIMessage(f"Available tables: {tool_message.content}")

        return {"messages": [tool_call_message, tool_message]}


    # Example: force a model to create a tool call
    def call_get_schema(state: MessagesState):
        print("call_get_schema....................")
        # Note that LangChain enforces that all models accept `tool_choice="any"`
        # as well as `tool_choice=<string name of tool>`.
        llm_with_tools = llm.bind_tools([get_schema_tool])
        response = llm_with_tools.invoke(state["messages"])
        sanitized_response = AIMessage(
            content=response.content or "",  # Ensure content is not None
            tool_calls=response.tool_calls
        )
        return {"messages": [sanitized_response]}

    def generate_query(state: MessagesState):
        print("Generate query....................")
        generate_query_system_prompt=get_generate_query_prompt(db.dialect,schema)
        system_message = {
            "role": "system",
            "content": generate_query_system_prompt,
        }
        # We do not force a tool call here, to allow the model to
        # respond naturally when it obtains the solution.
        llm_with_tools = llm.bind_tools([run_query_tool])
        response = llm_with_tools.invoke([system_message] + state["messages"])
        sanitized_response = AIMessage(
            content=response.content or "",  # Ensure content is not None
            tool_calls=response.tool_calls
        )
        return {"messages": [sanitized_response]}
    
    def check_query(state: MessagesState):
        check_query_system_prompt=get_check_query_prompt(db.dialect)
        print("Check query....................")
        system_message = {
            "role": "system",
            "content": check_query_system_prompt,
        }

        # Generate an artificial user message to check
        tool_call = state["messages"][-1].tool_calls[0]
        user_message = {"role": "user", "content": tool_call["args"]["query"]}
        llm_with_tools = llm.bind_tools([run_query_tool])
        response = llm_with_tools.invoke([system_message, user_message])
        response.id = state["messages"][-1].id

        return {"messages": [response]}


    # Updated conditional edge for generate_query
    def should_continue(state: MessagesState) -> Literal["execute_query", "wrap_tooltips"]:
        print("should_continue....................")
        """Decide whether to execute query or wrap results"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If last message has tool calls, we need to execute them
        if last_message.tool_calls:
            return "execute_query"
        # Otherwise, we're ready to wrap the results
        return "wrap_tooltips"
    # Create a combined execute node
    def execute_query(state: MessagesState):
        print("execute_query....................")
        """Node that executes SQL queries and returns results"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Find the query tool call
        query = None
        tool_call_id = None
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "sql_db_query":
                query = tool_call["args"]["query"]
                tool_call_id = tool_call["id"]
                break
        if not query:
            return {
                "messages": [
                    ToolMessage(
                        content="No valid SQL query found in the tool call.",
                        name="sql_db_query",
                        tool_call_id=tool_call_id or "unknown"
                    )
                ]
            }
        
        try:
            # Execute the query
            result = db.run_no_throw(query, fetch='all', include_columns=True)
            print("Query result:", result)
            # Check if result is an error string
            if isinstance(result, str) and result.lower().startswith("error"):
                return {
                    "messages": [
                        ToolMessage(
                            content=f"Query execution failed: {result}",
                            name="sql_db_query",
                            tool_call_id=tool_call_id
                        )
                    ]
                }
            # Check if result is empty
            if not result:
                return {
                    "messages": [
                        ToolMessage(content="No records found for the given query.",                   name="sql_db_query",tool_call_id=tool_call_id)
                    ]
                }

            return {
                "messages": [
                    ToolMessage(content=result, name="sql_db_query", tool_call_id=tool_call["id"])
                ]
            }
        except Exception as e:
            error_msg = f"Query execution failed: {str(e)}"
            print("Caught Exception:", error_msg)
            return {"messages": [ToolMessage(content=error_msg, name="sql_db_query", tool_call_id=tool_call["id"])]}
    
    def wrap_tooltips(state: MessagesState):
        print("wrap_tooltips....................")
        messages = state["messages"]
        last_message = messages[-1]
        print("last_message:", last_message)

        def truncate_tool_messages(msgs, truncate_length=25):
            for msg in msgs:
                if isinstance(msg, ToolMessage) and len(msg.content) > truncate_length:
                    original_length = len(msg.content)
                    msg.content = msg.content[:truncate_length] + "..."
            return msgs
        
        # Handle error messages
        if "error" in last_message.content.lower() or "failed" in last_message.content.lower():
            copied_messages = state["messages"].copy()
            state["messages"].clear()
            filtered_messages = truncate_tool_messages(copied_messages)
            return {
                "messages": filtered_messages + [AIMessage(content="Query execution failed. Please check the input or query logic.")]
            }
        
        # Handle no results
        if "no records found" in last_message.content.lower():
            copied_messages = state["messages"].copy()
            state["messages"].clear()
            filtered_messages = truncate_tool_messages(copied_messages)
            return {
                "messages": filtered_messages + [AIMessage(content="No records found for the given query.")]
            }
        
        if Type == "Table":
            print("Type is Table, formatting as table")
            try:
                data_list = ast.literal_eval(last_message.content)
                response = {"data": data_list}
                json_string = json.dumps(response, indent=2)
                copied_messages = state["messages"].copy()
                state["messages"].clear()
                filtered_messages = truncate_tool_messages(copied_messages)
                return {"messages": filtered_messages + [AIMessage(content=json_string)]}
            except Exception as e:
                copied_messages = state["messages"].copy()
                state["messages"].clear()
                filtered_messages = truncate_tool_messages(copied_messages)
                return {"messages": filtered_messages + [AIMessage(content=f"❌ Error for table formatting: {str(e)}")]}
        else:
            # Find the query that was executed
            query = ""
            for msg in reversed(messages):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if tool_call["name"] == "sql_db_query":
                            query = tool_call["args"]["query"]
                            break
                if query:
                    break
            
            # Extract table name
            table_match = re.search(r'FROM\s+\[?([\w]+)\]?\.\[?([\w]+)\]?', query, re.IGNORECASE)
            if table_match:
                schema = table_match.group(1)
                table = table_match.group(2)
                table_name_full = f"{schema}.{table}"
            else:
                table_name_full = "unknown_table"

            # Normalize and format the table name based on schema
            if "ADaM" in table_name_full:
                domain = table_name_full.split("ADaM.")[-1]
                table_name = f"ADaM.{domain}"
            elif "SDTM" in table_name_full:
                domain = table_name_full.split("SDTM.")[-1]
                table_name = f"SDTM.{domain}"
            else:
                table_name = table_name_full  # fallback

            print("🔍 Table Name:", table_name)
            summary_prompt = get_summary_prompt(table_name,query,last_message.content)
            # Copy → Clear → Truncate → LLM
            copied_messages = state["messages"].copy()
            state["messages"].clear()
            filtered_messages = truncate_tool_messages(copied_messages)
            try:
                llm_response = llm.invoke(summary_prompt)
                return {"messages": filtered_messages + [AIMessage(content=llm_response.content)]}
            except Exception as e:
                error_msg = f"Error generating narrative: {str(e)}"
                return {"messages": filtered_messages + [AIMessage(content=error_msg)]}

    # Update graph builder
    builder = StateGraph(MessagesState)
    builder.add_node("list_tables", list_tables)
    builder.add_node("call_get_schema", call_get_schema)
    builder.add_node("get_schema", get_schema_node)
    builder.add_node("generate_query", generate_query)
    builder.add_node("check_query", check_query)
    builder.add_node("execute_query", execute_query)  # Combined execution node
    builder.add_node("wrap_tooltips", wrap_tooltips)

    # Define graph edges
    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "call_get_schema")
    builder.add_edge("call_get_schema", "get_schema")
    builder.add_edge("get_schema", "generate_query")
    builder.add_edge("check_query", "execute_query")
    builder.add_edge("execute_query", "wrap_tooltips")
    builder.add_edge("wrap_tooltips", END)

    # Conditional edges
    builder.add_conditional_edges(
        "generate_query",
        should_continue,
        {"execute_query": "execute_query", "wrap_tooltips": "wrap_tooltips"}
    )
    builder.add_conditional_edges(
        "check_query",
        should_continue,
        {"execute_query": "execute_query", "wrap_tooltips": "wrap_tooltips"}
    )
    if is_redis:
        print(f"RUNNING REDIS")
        redis_url = settings.REDIS_URL
        with RedisSaver.from_conn_string(redis_url) as saver:
            saver.setup()
            return builder.compile(checkpointer=saver)

        
    else:
        print(f"RUNNING without REDIS")
        return builder.compile()

