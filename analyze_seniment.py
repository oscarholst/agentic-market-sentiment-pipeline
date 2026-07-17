import os
import psycopg2
from dotenv import load_dotenv
from transformers import pipeline

# Load environment variables
load_dotenv()

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

print("Loading local financial sentiment model (ProsusAI/finbert)...")
# Initialize the financial sentiment pipeline
sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusAI/finbert")

def get_unanalyzed_news():
    """Fetches up to 10 articles from Supabase where sentiment has not been processed yet"""
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL is missing.")
        return []
        
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        # Select articles where sentiment is missing
        cur.execute("""
            SELECT id, title, summary 
            FROM news_sentiment 
            WHERE sentiment IS NULL 
            LIMIT 10;
        """)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching news from database: {e}")
        return []

def update_article_sentiment(article_id, sentiment_label, score):
    """Updates the sentiment and score columns for a specific article in Supabase"""
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE news_sentiment
            SET sentiment = %s, sentiment_score = %s
            WHERE id = %s;
        """, (sentiment_label, score, article_id))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error updating sentiment in database: {e}")

if __name__ == "__main__":
    print("Starting local sentiment analysis pipeline...")
    articles = get_unanalyzed_news()
    
    if not articles:
        print("No unanalyzed articles found in the database.")
    else:
        print(f"Processing {len(articles)} articles...")
        for art_id, title, summary in articles:
            # Combine title and summary, truncating to fit model sequence limits
            text_to_analyze = f"{title}. {summary}"[:512]
            
            try:
                result = sentiment_analyzer(text_to_analyze)[0]
                label = result["label"]  # positive, negative, or neutral
                score = float(result["score"])
                
                update_article_sentiment(art_id, label, score)
                print(f"Processed ID {art_id}: {label.upper()} (Score: {score:.2f}) -> {title[:40]}...")
            except Exception as e:
                print(f"Failed to analyze article {art_id}: {e}")
                
        print("Batch processing complete.")