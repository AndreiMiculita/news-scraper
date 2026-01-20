import streamlit as st
import subprocess
import pandas as pd
from GoogleNews import GoogleNews
from datetime import datetime, timedelta
import time
import random

def get_git_revision_hash():
    try:
        # Runs 'git rev-parse --short HEAD' to get the 7-character hash
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except Exception:
        return "No Git Hash Found"

# --- 1. DATE CALCULATIONS ---
def get_half_year_intervals(start_str, end_str):
    """Splits the long timeline into 6-month chunks to maximize results."""
    start = datetime.strptime(start_str, "%m/%d/%Y")
    end = datetime.strptime(end_str, "%m/%d/%Y")
    intervals = []
    current = start
    while current < end:
        next_chunk = current + timedelta(days=180)
        if next_chunk > end:
            next_chunk = end
        intervals.append({
            "start": current.strftime("%m/%d/%Y"),
            "end": next_chunk.strftime("%m/%d/%Y"),
            "label": f"{current.strftime('%Y-%m')}_{next_chunk.strftime('%Y-%m')}"
        })
        current = next_chunk + timedelta(days=1)
    return intervals

# --- 2. THE SCRAPER ---
def scrape_interval(query, start_date, end_date):
    """Scrapes multiple pages for a specific window using absolute date parameters."""
    # We initialize with start/end to force Google's custom range (cdr) parameters
    googlenews = GoogleNews(lang='en', encode='utf-8', start=start_date, end=end_date)
    
    googlenews.search(query)
    all_raw_results = []
    
    # Iterate through pages (Google typically provides up to 10 for news)
    for i in range(1, 6):
        googlenews.get_page(i)
        page_results = googlenews.results()
        if page_results:
            all_raw_results.extend(page_results)
        
        googlenews.clear() # Clear internal buffer for next page
        time.sleep(random.uniform(2, 4))
            
    return all_raw_results

# --- 3. DEDUPLICATION & CLEANING ---
def clean_and_format_data(raw_list, query_text, interval_label):
    """Processes raw library output into a clean list of dictionaries."""
    cleaned = []
    seen_urls = set()
    
    for item in raw_list:
        url = item.get('link')
        if not url or url in seen_urls:
            continue
        
        seen_urls.add(url)
        cleaned.append({
            'absolute_datetime': item.get('datetime'), # The precision timestamp
            'headline': item.get('title'),
            'outlet': item.get('media'),
            'url': url,
            'description': item.get('desc'),
            'query_filter': query_text,
            'time_chunk': interval_label
        })
    return cleaned

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="📰 Historical News Researcher", layout="wide")
st.title("📰 Historical News Researcher")

# Sidebar
st.sidebar.header("Search Configuration")
start_input = st.sidebar.text_input("Start Date (MM/DD/YYYY)", "10/07/2023")
end_input = st.sidebar.text_input("End Date (MM/DD/YYYY)", "01/01/2026")
query_list = st.sidebar.text_area("Queries", "Gaza site:bbc.com\nGaza site:nytimes.com\nGaza site:foxnews.com")

st.sidebar.markdown(f"**Version (Commit):** `{get_git_revision_hash()}`")

if st.sidebar.button("Run Full Scrape"):
    queries = [q.strip() for q in query_list.split('\n') if q.strip()]
    intervals = get_half_year_intervals(start_input, end_input)
    
    master_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_tasks = len(queries) * len(intervals)
    current_task = 0
    
    for q_text in queries:
        for interval in intervals:
            current_task += 1
            status_text.info(f"Task {current_task}/{total_tasks}: {q_text} ({interval['label']})")
            
            # 1. Get raw data from Google
            raw_results = scrape_interval(q_text, interval['start'], interval['end'])
            
            # 2. Clean and deduplicate it
            chunk_data = clean_and_format_data(raw_results, q_text, interval['label'])
            
            # 3. Add to master list
            master_data.extend(chunk_data)
            
            progress_bar.progress(current_task / total_tasks)
            time.sleep(random.uniform(3, 5)) # Safety delay

    if master_data:
        df = pd.DataFrame(master_data)
        
        # Final formatting
        df['absolute_datetime'] = pd.to_datetime(df['absolute_datetime'], errors='coerce')
        df = df.sort_values('absolute_datetime', ascending=False)
        
        st.success(f"Successfully extracted {len(df)} unique articles!")
        st.dataframe(df.head(100)) # Show preview
        
        # Export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Precision CSV", csv, "historical_news_export.csv", "text/csv")
    else:
        st.error("No data found. Check your dates or IP status.")