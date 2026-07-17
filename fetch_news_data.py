import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

def fetch_financial_news():
    """Fetches recent financial news items from an RSS feed"""
    url = "https://finance.yahoo.com/rss/topstories"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        news_items = []
        
        # Parse RSS items
        for item in root.findall(".//item"):
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            description = item.find("description").text if item.find("description") is not None else ""
            pub_date_str = item.find("pubDate").text if item.find("pubDate") is not None else ""
            
            # Convert RSS pubDate string to datetime object
            # Example: "Fri, 17 Jul 2026 12:00:00 +0000"
            try:
                pub_date = datetime.strptime(pub_date_str[:25], "%a, %d %b %Y %H:%M:%S")
            except Exception:
                pub_date = datetime.utcnow()
                
            news_items.append({
                "title": title,
                "url": link,
                "summary": description,
                "published_at": pub_date,
                "source": "Yahoo Finance"
            })
            
        return news_items
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

def save_news_to_supabase(news_items):
    """Inserts news articles into the news_sentiment table"""
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL is missing in .env")
        return
        
    if not news_items:
        print("No news items to save.")
        return

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        # SQL query to insert articles, ignoring duplicates based on unique URL
        query = """
        INSERT INTO news_sentiment (title, url, summary, published_at, source)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING;
        """
        
        saved_count = 0
        for item in news_items:
            cur.execute(query, (
                item["title"],
                item["url"],
                item["summary"],
                item["published_at"],
                item["source"]
            ))
            # rowcount is 1 if inserted, 0 if skipped due to conflict
            if cur.rowcount > 0:
                saved_count += 1
                
        conn.commit()
        cur.close()
        conn.close()
        print(f"Success! Saved {saved_count} new articles to Supabase.")
    except Exception as e:
        print(f"Error storing news in Supabase: {e}")

if __name__ == "__main__":
    print("Starting financial news fetch...")
    articles = fetch_financial_news()
    print(f"Found {len(articles)} articles from the feed.")
    save_news_to_supabase(articles)