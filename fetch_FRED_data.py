import os
import requests
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

def fetch_fred_data(series_id):
    """Fetches the latest 30 observations from the FRED API"""
    if not FRED_API_KEY:
        print("Error: FRED_API_KEY is missing in .env")
        return []
        
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        # Return the 30 most recent data points
        return data["observations"][-30:]
    except Exception as e:
        print(f"Error fetching from FRED: {e}")
        return []

def save_to_supabase(observations, indicator_name):
    """Saves the data into the Supabase market_data table"""
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL is missing in .env")
        return
        
    if not observations:
        return
    
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        # SQL query to upsert data if the date and indicator already exist
        query = """
        INSERT INTO market_data (date, indicator_name, value)
        VALUES (%s, %s, %s)
        ON CONFLICT (date, indicator_name) DO UPDATE 
        SET value = EXCLUDED.value;
        """
        
        saved_count = 0
        for obs in observations:
            if obs["value"] == ".":  # Ignore empty data points
                continue
            
            date = obs["date"]
            value = float(obs["value"])
            
            cur.execute(query, (date, indicator_name, value))
            saved_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        print(f"Success! Saved {saved_count} rows for '{indicator_name}' to Supabase.")
    except Exception as e:
        print(f"Error storing in Supabase: {e}")

if __name__ == "__main__":
    print("Starting economic data fetch...")
    
    # 'FEDFUNDS' is the code for the US Federal Funds Effective Rate
    interest_data = fetch_fred_data("FEDFUNDS")
    
    if interest_data:
        save_to_supabase(interest_data, "US Federal Funds Rate")