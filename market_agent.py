import os
import json
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import ollama
from langgraph.graph import StateGraph, END
from typing import TypedDict, Any

# Load environment variables
load_dotenv()

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

print("Loading embedding model for RAG queries...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# 1. Define state using standard TypedDict
class AgentState(TypedDict):
    fred_rate: Any
    avg_sentiment: Any
    rag_context: Any
    market_report: Any

def fetch_database_metrics_node(state: AgentState):
    """Node 1: Fetches metrics and returns ONLY the updates"""
    print("Agent Node: Fetching metrics from Supabase...")
    
    conn = psycopg2.connect(SUPABASE_DB_URL)
    cur = conn.cursor()
    
    # Get latest Fed Funds Rate
    cur.execute("SELECT value FROM market_data ORDER BY date DESC LIMIT 1;")
    rate_row = cur.fetchone()
    fred_rate = float(rate_row[0]) if rate_row else "Unknown"
    
    # Get processed sentiment metrics
    cur.execute("""
        SELECT sentiment, COUNT(*) 
        FROM news_sentiment 
        WHERE sentiment IS NOT NULL 
        GROUP BY sentiment;
    """)
    sentiment_rows = cur.fetchall()
    
    cur.close()
    conn.close()
    
    sentiment_summary = {row[0]: row[1] for row in sentiment_rows}
    
    # Return ONLY the updates for this node
    return {
        "fred_rate": fred_rate,
        "avg_sentiment": json.dumps(sentiment_summary)
    }

def query_rag_knowledge_node(state: AgentState):
    """Node 2: Queries RAG and returns ONLY the rag_context update"""
    print("Agent Node: Querying RAG knowledge base...")
    
    search_query = "What does the Fed do when inflation or interest rates change?"
    query_vector = embedding_model.encode(search_query).tolist()
    
    conn = psycopg2.connect(SUPABASE_DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT content 
        FROM document_embeddings 
        ORDER BY embedding <=> %s::vector 
        LIMIT 1;
    """, (str(query_vector),))
    
    rag_row = cur.fetchone()
    cur.close()
    conn.close()
    
    rag_context = rag_row[0] if rag_row else "No matching historical guidelines found."
    
    # Return ONLY the updates for this node
    return {
        "rag_context": rag_context
    }

def generate_report_node(state: AgentState):
    """Node 3: Generates the report using safely retrieved state values"""
    print("Agent Node: Generating report using local Mistral model...")
    
    # Safely extract values from state to prevent KeyErrors
    fred_rate = state.get("fred_rate", "Unknown")
    avg_sentiment = state.get("avg_sentiment", "{}")
    rag_context = state.get("rag_context", "No context available.")
    
    prompt = f"""
    You are an advanced AI Financial Analyst. Synthesize the following pipeline data into a professional market brief.
    
    DATA METRICS:
    - Current US Federal Funds Rate (FRED): {fred_rate}%
    - Recent Market News Sentiment Count: {avg_sentiment}
    
    HISTORICAL POLICY CONTEXT (RAG):
    {rag_context}
    
    INSTRUCTIONS:
    Write a concise 2-paragraph market report explaining how the current news sentiment aligns with the current interest rate level based on the historical policy context.
    """
    
    try:
        response = ollama.chat(
            model="mistral",
            messages=[{"role": "user", "content": prompt}]
        )
        report_content = response["message"]["content"]
    except Exception as e:
        report_content = f"Failed to generate report via Ollama: {e}"
        
    return {
        "market_report": report_content
    }

# --- Build the LangGraph Workflow ---
workflow = StateGraph(AgentState)

workflow.add_node("fetch_metrics", fetch_database_metrics_node)
workflow.add_node("query_rag", query_rag_knowledge_node)
workflow.add_node("generate_report", generate_report_node)

workflow.set_entry_point("fetch_metrics")
workflow.add_edge("fetch_metrics", "query_rag")
workflow.add_edge("query_rag", "generate_report")
workflow.add_edge("generate_report", END)

compiled_agent = workflow.compile()

if __name__ == "__main__":
    print("Executing LangGraph Agent Workflow...")
    
    initial_state = {
        "fred_rate": None,
        "avg_sentiment": None,
        "rag_context": None,
        "market_report": None
    }
    
    final_output = compiled_agent.invoke(initial_state)
    
    print("\n" + "="*50)
    print("FINAL AGENT MARKET REPORT:")
    print("="*50)
    print(final_output.get("market_report", "No report generated."))
    print("="*50)