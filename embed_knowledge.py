import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

# Load the local embedding model once at startup.
model = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text):
    """Generates a local vector embedding using SentenceTransformer."""
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def save_knowledge_to_rag(content, metadata):
    """Embeds text and stores it into the document_embeddings table"""
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL is missing in .env")
        return

    print(f"Generating embedding for: '{content[:40]}...'")
    embedding = get_embedding(content)
    
    if not embedding:
        return

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        # Insert the text, metadata, and vector embedding into Supabase
        import json
        query = """
        INSERT INTO document_embeddings (content, metadata, embedding)
        VALUES (%s, %s, %s);
        """
        cur.execute(query, (content, json.dumps(metadata), embedding))
        
        conn.commit()
        cur.close()
        conn.close()
        print("Success! Paragraph saved to RAG knowledge base.")
    except Exception as e:
        print(f"Error storing embedding in Supabase: {e}")

if __name__ == "__main__":
    print("Starting RAG knowledge base population...")
    
    # Sample heavy financial context that our agent will use later to understand inflation news
    sample_context = (
        "The Federal Reserve's primary mandate is to maintain price stability, targeting a long-run inflation rate of 2 percent. "
        "When inflation runs consistently above 2%, the FOMC typically responds by raising the Federal Funds Rate to cool down economic activity. "
        "Conversely, if interest rates are high and inflation begins to decelerate rapidly toward the target, market participants expect the Fed to consider rate cuts."
    )
    
    meta = {"source": "FOMC Guidelines", "topic": "Inflation & Interest Rates"}
    
    save_knowledge_to_rag(sample_context, meta)