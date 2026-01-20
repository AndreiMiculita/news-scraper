import streamlit as st
import pandas as pd
from GoogleNews import GoogleNews
from datetime import datetime, timedelta
import time
import random
import base64

# --- HELPER FUNCTIONS ---

def get_half_year_intervals(start_str, end_str):
    """Splits date range into ~6-month chunks."""
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

def scrape_interval(query, start_date, end_date):
    """Scrapes a single interval."""
    googlenews = GoogleNews()
    googlenews.set_lang('en')
    googlenews.set_time_range(start_date, end_date)
    googlenews.set_encode('utf-8')
    
    googlenews.search(query)
    all_results = googlenews.result()
    
    # Try to get up to 5 pages
    for i in range(2, 6):
        try:
            googlenews.getpage(i)
            page_results = googlenews.result()
            if not page_results:
                break
            all_results.extend(page_results)
            time.sleep(random.uniform(1, 3)) # Polite delay
        except Exception:
            break
            
    return all_results

def clean_data(results_list):
    """Dedupes and cleans data."""
    cleaned = []
    seen_urls = set()
    for item in results_list:
        url = item.get('link', '')
        if url in seen_urls:
            continue
        seen_urls.add(url)
        cleaned.append({
            'headline': item.get('title', ''),
            'date': item.get('date', ''),
            'url': url,
            'description': item.get('desc', '')
        })
    return cleaned

# --- STREAMLIT UI ---

st.set_page_config(page_title="Gaza News Scraper", page_icon="📰")

st.title("📰 Historical News Scraper")
st.markdown("Scrape Google News results by date range and outlet.")

# Sidebar Inputs
st.sidebar.header("Configuration")
start_input = st.sidebar.text_input("Start Date (MM/DD/YYYY)", "10/07/2023")
end_input = st.sidebar.text_input("End Date (MM/DD/YYYY)", "01/01/2026")

outlets = st.sidebar.text_area(
    "Outlets & Queries (One per line)", 
    "Gaza site:bbc.com\nGaza site:nytimes.com\nGaza site:foxnews.com"
)

if st.button("Start Scraping"):
    queries = [q.strip() for q in outlets.split('\n') if q.strip()]
    intervals = get_half_year_intervals(start_input, end_input)
    
    total_steps = len(queries) * len(intervals)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    all_dfs = []
    step_count = 0
    
    for query_text in queries:
        outlet_safe = query_text.replace(' ', '_').replace(':', '').replace('/', '')
        st.subheader(f"Processing: {query_text}")
        
        for interval in intervals:
            step_count += 1
            progress = step_count / total_steps
            progress_bar.progress(progress)
            status_text.text(f"Scraping {interval['start']} to {interval['end']}...")
            
            # Scrape
            raw = scrape_interval(query_text, interval['start'], interval['end'])
            data = clean_data(raw)
            
            if data:
                df = pd.DataFrame(data)
                # Add metadata columns
                df['query'] = query_text
                df['interval_label'] = interval['label']
                all_dfs.append(df)
                st.success(f"  Found {len(df)} articles for {interval['start']} - {interval['end']}")
            else:
                st.warning(f"  No results for {interval['start']} - {interval['end']}")
            
            # Sleep to avoid block
            time.sleep(random.uniform(2, 5))

    # Combine all results
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        st.write("### Preview of Results")
        st.dataframe(final_df.head())
        
        # Convert to CSV for download
        csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download All Data as CSV",
            data=csv,
            file_name='scraped_news_data.csv',
            mime='text/csv',
        )
    else:
        st.error("No data found.")