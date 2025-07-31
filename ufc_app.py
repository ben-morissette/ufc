import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# Helper: Get two values safely from a row (for strikes landed etc.)
def get_two_values_from_col(row, col1, col2):
    val1 = row[col1] if col1 in row.index else 0
    val2 = row[col2] if col2 in row.index else 0
    try:
        val1 = int(val1)
    except:
        val1 = 0
    try:
        val2 = int(val2)
    except:
        val2 = 0
    return val1, val2

# Calculate RAX for a single fight row
def calculate_rax(row):
    rax = 0

    # Rule 1: RAX based on method_main and result
    if 'Result' in row.index:
        if row['Result'].lower() == 'win':
            method = str(row.get('method_main', '')).lower()
            if 'ko/tko' in method:
                rax += 100
            elif 'sub' in method or 'submission' in method:
                rax += 90
            elif 'u-dec' in method or 'decision - unanimous' in method:
                rax += 80
            elif 'm-dec' in method or 'decision - majority' in method:
                rax += 75
            elif 's-dec' in method or 'decision - split' in method:
                rax += 70
        elif row['Result'].lower() == 'loss':
            rax += 25

    # Rule 2: RAX for sig strike difference
    sig_str_fighter, sig_str_opponent = get_two_values_from_col(row, 'TOT_fighter_SigStr_landed', 'TOT_opponent_SigStr_landed')
    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights (main event or championship)
    if 'TimeFormat' in row.index and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    # Rule 4: Bonus for Fight of the Night
    details = str(row.get('Details', '')).lower()
    if 'fight of the night' in details or 'fight of night' in details or 'fight of the nigh' in details:
        rax += 50

    # Rule 5: Bonus for championship fights
    event = str(row.get('event_name', '')).lower()
    if 'championship' in event or 'title' in event:
        rax += 25

    return rax

# Scrape fight data for one fighter from their UFC Stats page
def get_fight_links(fighter_url):
    try:
        res = requests.get(fighter_url)
        res.raise_for_status()
    except:
        return pd.DataFrame()  # Return empty if error

    soup = BeautifulSoup(res.text, 'html.parser')
    tables = soup.find_all('table', class_='b-fight-details__table js-fight-table')

    if not tables:
        return pd.DataFrame()

    fight_rows = []
    for table in tables:
        rows = table.find_all('tr')[1:]  # skip header row
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 9:
                continue
            fight_data = {
                'date': cols[0].text.strip(),
                'event_name': cols[1].text.strip(),
                'result': cols[2].text.strip().lower(),
                'method_main': cols[3].text.strip(),
                'Round': cols[4].text.strip(),
                'Time': cols[5].text.strip(),
                'TimeFormat': cols[6].text.strip(),
                'Details': cols[7].text.strip(),
                'Opponent': cols[8].text.strip(),
                'Fighter Name': fighter_url.split('/')[-1].replace('-', ' ').title()
            }
            fight_rows.append(fight_data)

    df = pd.DataFrame(fight_rows)

    # Now, scrape the detailed stats table for significant strikes
    # The page has another table with fighter vs opponent significant strikes landed
    # This requires another step

    # Find stats table with class "b-fight-details__table js-fight-table"
    stats_table = soup.find('table', class_='b-fight-details__table')
    if stats_table:
        sig_cols = ['TOT_fighter_SigStr_landed', 'TOT_opponent_SigStr_landed']
        # The page has stats per fight, but it's complicated to match row by row in this simple approach
        # So for now, let's skip this part — we can enhance this later if needed

    # To approximate sig strikes, let's try to parse the fight stats rows under the "STRIKING" section
    # For now, fill zeros — better to improve with detailed scraping

    df['TOT_fighter_SigStr_landed'] = 0
    df['TOT_opponent_SigStr_landed'] = 0

    return df

# Scrape the top N fighters from UFC stats fighters page
def get_top_fighter_links(limit=10):
    url = "http://ufcstats.com/statistics/fighters"
    params = {"page": "all"}
    res = requests.get(url, params=params)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, 'html.parser')

    table = soup.find('table', class_='b-statistics__table')
    if not table:
        return []

    rows = table.find('tbody').find_all('tr')
    links = []
    for row in rows[:limit]:
        link_tag = row.find('a', href=True)
        if link_tag:
            links.append(link_tag['href'])
    return links


st.title("UFC Fighter RAX Leaderboard")

limit = st.number_input("Number of fighters to process", min_value=1, max_value=50, value=10, step=1)

if st.button("Generate Leaderboard"):
    fighter_links = get_top_fighter_links(limit)
    leaderboard = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, fighter_url in enumerate(fighter_links, 1):
        try:
            fighter_name = fighter_url.split('/')[-1].replace('-', ' ').title()
            status_text.text(f"Processing {i}/{limit}: {fighter_name}")
            fights_df = get_fight_links(fighter_url)

            if fights_df.empty:
                total_rax = 0
            else:
                fights_df['RAX Earned'] = fights_df.apply(calculate_rax, axis=1)
                total_rax = fights_df['RAX Earned'].sum()

            leaderboard.append({"Fighter": fighter_name, "Total RAX": total_rax})
        except Exception as e:
            leaderboard.append({"Fighter": fighter_name, "Total RAX": 0})

        progress_bar.progress(i / limit)
        time.sleep(0.5)

    leaderboard_df = pd.DataFrame(leaderboard).sort_values(by="Total RAX", ascending=False).reset_index(drop=True)
    st.markdown("### RAX Leaderboard")
    st.dataframe(leaderboard_df)
