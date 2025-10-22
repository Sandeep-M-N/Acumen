from app.standard_query.handler import handle_standard_query
import json
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.checkpoint.redis import RedisSaver
from app.core.config import settings

def build_summary_agent(LlmType: str, ModelName: str):
    """Build contextual summary agent with Redis support - only for AI part"""
    
    # LLM config
    if LlmType == "Azure OpenAI":
        deployment_name = ModelName
        model_provider = "azure_openai"
    elif LlmType == "OpenAI":
        deployment_name = ModelName
        model_provider = "openai"
    else:
        raise ValueError(f"Unsupported LLM type: {LlmType}")
    
    api_key = settings.AZURE_OPENAI_API_KEY
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY not found")

    llm = init_chat_model(
        deployment_name,
        model_provider=model_provider,
        temperature=0,
        api_key=api_key,
    )
    
    def generate_summary_node(state: MessagesState):
        """Node that generates contextual summary using LLM"""
        messages = state["messages"]
        
        # Get the latest message (should contain query results)
        latest_message = messages[-1].content if messages else ""
        
        # Create contextual prompt with conversation history
        system_prompt = """You are a clinical data analyst specializing in regulatory documentation. Generate clear, factual summaries of clinical trial data that can be directly used in narrative documents by clinical writers. Focus on presenting the data without additional recommendations or follow-up questions.
        """
        
        # Invoke LLM with full conversation context
        prompt_messages = [HumanMessage(content=system_prompt)]
        prompt_messages.extend(messages)
        
        response = llm.invoke(prompt_messages)
        
        return {"messages": [AIMessage(content=response.content)]}
    
    # Build simple graph for summary generation
    builder = StateGraph(MessagesState)
    builder.add_node("generate_summary", generate_summary_node)
    builder.add_edge(START, "generate_summary")
    builder.add_edge("generate_summary", END)
    
    # Add Redis support if enabled
    is_redis = settings.REDIS_CONFIG
    if is_redis:
        redis_url = settings.REDIS_URL
        with RedisSaver.from_conn_string(redis_url) as saver:
            saver.setup()
            return builder.compile(checkpointer=saver)
    else:
        return builder.compile()

def process_standard_query(ProjectNumber: str, FolderName: str, Question: str, LlmType: str, ModelName: str, STANDARD_QUERY_DATA: dict, SessionId: int):
    """Process standard query - only AI summary part is contextual"""
    print(f"Processing standard query for project: {ProjectNumber}, folder: {FolderName}")
    
    try:
        # Step 1: Get query result from handler (non-contextual)
        result = handle_standard_query(ProjectNumber, FolderName, Question, STANDARD_QUERY_DATA)
        
        if result["query_result"] and result["query_result"] != "No data found":
            # Step 2: Generate contextual summary using LangGraph agent
            summary_agent = build_summary_agent(LlmType, ModelName)
            
            # Configure with thread ID for Redis context
            is_redis = settings.REDIS_CONFIG
            config = {"configurable": {"thread_id": str(SessionId)}} if is_redis else {}
            
            # Create prompt for summary generation
            summary_prompt = f"""Based on the following clinical trial data, provide a concise narrative summary suitable for clinical documentation:

            Question: {Question}
            Query Results: {result["query_result"]}

            Generate a professional clinical narrative that:
            - Summarizes the key laboratory findings
            - Uses appropriate clinical terminology
            - Is ready to copy into clinical documents
            - Focuses only on the data presented without additional recommendations or follow-up suggestions

            Format the response as a clear, factual summary suitable for regulatory documentation.
            """
            
            # Invoke contextual summary agent
            summary_result = summary_agent.invoke(
                {"messages": [HumanMessage(content=summary_prompt)]},
                config=config
            )
            
            # Extract summary from agent response
            summary = summary_result["messages"][-1].content if summary_result["messages"] else "Summary generation failed"
           
            # Return structured response with required format
            response = {
                "summary": summary,
                "query": result["query"],
                "readable_summary": "Standard Query"
            }
            table_response = {
                "summary": result["query_result"],
                "query": result["query"],
                "readable_summary": "Standard Query"
            }

        else:
            # No data found
            response = {
                "summary": "No data found for the specified criteria.",
                "query": result["query"],
                "readable_summary": "Standard Query"
            }
            table_response = {
                "summary": "No data found for the specified criteria.",
                "query": result["query"],
                "readable_summary": "Standard Query"
            }
        
        return json.dumps(response, indent=2), json.dumps(table_response, indent=2)
        
    except Exception as e:
        # Handle both query errors and LLM errors
        error_message = f"Error in standard query processing: {str(e)}"
        
        error_response = {
            "summary": error_message,
            "query": "",
            "readable_summary": "Standard Query"
        }
        table_response = {
                "summary": error_message,
                "query": "",
                "readable_summary": "Standard Query"
            }
        return json.dumps(error_response, indent=2), json.dumps(table_response, indent=2)
