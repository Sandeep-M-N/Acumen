from app.ai.langgraph_workflow.graph_config import build_agent
import json
from bs4 import BeautifulSoup
from app.core.config import settings
is_redis = settings.REDIS_CONFIG
def run_agent(ProjectNumber: str, FolderName: str, Question: str, LlmType: str, ModelName: str,SessionId:int,Type: str):
    print(f"Running agent for project: {ProjectNumber}, folder: {FolderName}, question: {Question}, SessionId: {SessionId}")
    
    agent = build_agent(ProjectNumber, FolderName, LlmType, ModelName, Type)

    config = {"configurable": {"thread_id": str(SessionId)}} if is_redis else {}
    final_result = None
    json_output = {}
    try:
        final_result = agent.invoke(
            {"messages": [{"role": "user", "content": Question}]},
            config=config
        )
    except Exception as e:
        print(f"❌ Error invoking agent: {e}")
        json_output["summary"] = f"Error: {str(e)}"
        json_output["readable_summary"] = f"Error: {str(e)}"
        json_output["query"] = ""
    else:
        # Extract required information from agent output
        last_ai_content = ""
        last_query = ""

        # Traverse messages in reverse to efficiently find last AI message
        for msg in reversed(final_result['messages']):
            if msg.type == "ai":
                last_ai_content = msg.content
                break

        # Find the last SQL query used
        for msg in final_result['messages']:
            if msg.type == "ai" and hasattr(msg, 'tool_calls'):
                for tool_call in msg.tool_calls:
                    if tool_call['name'] == 'sql_db_query':
                        last_query = tool_call['args']['query']

        json_output["summary"] = last_ai_content
        json_output["query"] = last_query
        # For Log 
        if Type == "Summary":
            soup = BeautifulSoup(last_ai_content, "html.parser")
            # Remove unwanted elements in one pass
            for tag in soup.select(".tooltiptext, .display-none"):
                tag.decompose()
            # Get clean text
            readable_summary = " ".join(soup.get_text(separator=" ", strip=True).split())

            json_output["readable_summary"] = readable_summary
        else:
            json_output["readable_summary"] = "Table"
            
            
    # print(f"pretty_print:{final_result}")
    return json.dumps(json_output, indent=2)