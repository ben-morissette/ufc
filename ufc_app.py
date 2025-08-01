import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os

CACHE_FILE = 'ufc_rax_cache.csv'

RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6
}

def get_last_tuesday(reference_date=None):
    if reference_date is None:
        reference_date = datetime.now()
    days_since_tuesday = (reference_date.weekday() - 1) % 7
    last_tuesday = reference_date - timedelta(days=days_since_tuesday)
    return last_tuesday.replace(hour=0, minute=0, second=0, microsecond=0)

def cache_is_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    last_tuesday = get_last_tuesday()
    return mod_time >= last_tuesday

def get_fighter_urls():
    url = "http://ufcstats.com/statistics/fighters"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
    urls = {}
    for row in rows:
        name_cell = row.find_all('td')[0]
        link = name_cell.find('a', class_='b-link_style_black')
        name = name_cell.get_text(strip=True)
        if link and link.has_attr('href'):
            urls[name.lower()] = link['href']
    return urls

def get_two_values_from_col(col):
    ps = col.find_all('p', class_='b-fight-details__table-text')
    if len(ps) == 2:
        return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
    return None, None

def get_fight_data(fighter_url):
    response = requests.get(fighter_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        return pd.DataFrame()
    
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fights_data = []
    
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        
        result_tag = cols[0].find('p', class_='b-fight-details__table-text')
        result = result_tag.get_text(strip=True).lower() if result_tag else None
        
        fighter_td = cols[1].find_all('p', class_='b-fight-details__table-text')
        fighter_name = fighter_td[0].get_text(strip=True) if len(fighter_td) > 0 else None
        opponent_name = fighter_td[1].get_text(strip=True) if len(fighter_td) > 1 else None

        kd_fighter, kd_opponent = get_two_values_from_col(cols[2])
        str_fighter, str_opponent = get_two_values_from_col(cols[3])
        td_fighter, td_opponent = get_two_values_from_col(cols[4])
        sub_fighter, sub_opponent = get_two_values_from_col(cols[5])

        event_td = cols[6].find_all('p', class_='b-fight-details__table-text')
        event_name = event_td[0].get_text(strip=True) if len(event_td) > 0 else None

        method_td = cols[7].find_all('p', class_='b-fight-details__table-text')
        method_main = method_td[0].get_text(strip=True) if len(method_td) > 0 else None

        round_val = cols[8].find('p', class_='b-fight-details__table-text')
        round_val = round_val.get_text(strip=True) if round_val else None

        fights_data.append({
            'Result': result,
            'Fighter Name': fighter_name,
            'Opponent Name': opponent_name,
            'KD Fighter': kd_fighter,
            'KD Opponent': kd_opponent,
            'Strikes Fighter': str_fighter,
            'Strikes Opponent': str_opponent,
            'Takedowns Fighter': td_fighter,
            'Takedowns Opponent': td_opponent,
            'Submission Attempts Fighter': sub_fighter,
            'Submission Attempts Opponent': sub_opponent,
            'Event Name': event_name,
            'Method Main': method_main,
            'Round': round_val,
        })
    return pd.DataFrame(fights_data)

def calculate_rax(row):
    rax = 0
    if row['Result'] == 'win':
        method = (row['Method Main'] or '').lower()
        if 'ko/tko' in method:
            rax += 100
        elif 'sub' in method:
            rax += 90
        elif 'unanimous' in method or 'u-dec' in method:
            rax += 80
        elif 'majority' in method or 'm-dec' in method:
            rax += 75
        elif 'split' in method:
            rax += 70
    elif row['Result'] == 'loss':
        rax += 25

    try:
        strikes_fighter = int(str(row['Strikes Fighter']).replace(',', ''))
    except:
        strikes_fighter = 0
    try:
        strikes_opponent = int(str(row['Strikes Opponent']).replace(',', ''))
    except:
        strikes_opponent = 0

    strike_diff = strikes_fighter - strikes_opponent
    if strike_diff > 0:
        rax += strike_diff

    if row['Round'] == '5':
        rax += 25

    event_name = (row['Event Name'] or '').lower()
    if 'fight of the night' in event_name or 'fight of night' in event_name:
        rax += 50
    if 'championship' in event_name:
        rax += 25

    return rax

def get_fighter_rax(fighter_name, fighter_urls, cache_df):
    fighter_name_lower = fighter_name.lower()

    # Check cache first
    if cache_df is not None and fighter_name_lower in cache_df['Fighter Name'].str.lower().values:
        return cache_df[cache_df['Fighter Name'].str.lower() == fighter_name_lower].iloc[0]

    # Otherwise, fetch
    if fighter_name_lower not in fighter_urls:
        return None

    try:
        fights_df = get_fight_data(fighter_urls[fighter_name_lower])
        if fights_df.empty:
            return None
        fights_df['Rax Earned'] = fights_df.apply(calculate_rax, axis=1)
        total_rax = fights_df['Rax Earned'].sum()
        fight_count = len(fights_df)
        fighter_name_actual = fights_df.iloc[0]['Fighter Name']
        result = {
            'Fighter Name': fighter_name_actual,
            'Total Rax': total_rax,
            'Fight Count': fight_count,
        }
        return result
    except Exception as e:
        st.warning(f"Error fetching data for {fighter_name}: {e}")
        return None

# === Main app ===

st.title("UFC Fighter RAX Search")

# Load cache if fresh
if cache_is_fresh():
    cache_df = pd.read_csv(CACHE_FILE)
else:
    cache_df = None

fighter_urls = get_fighter_urls()

search_name = st.text_input("Enter Fighter Name to search:")

if search_name:
    result = get_fighter_rax(search_name, fighter_urls, cache_df)
    if result is None:
        st.error("Fighter not found or no fight data available.")
    else:
        rarity = st.selectbox(
            f"Select rarity for {result['Fighter Name']}:",
            options=list(RARITY_MULTIPLIERS.keys()),
            index=0
        )
        multiplier = RARITY_MULTIPLIERS[rarity]
        adjusted_rax = int(result['Total Rax'] * multiplier)

        st.write(f"Fighter: {result['Fighter Name']}")
        st.write(f"Total Fights: {result['Fight Count']}")
        st.write(f"Base RAX: {result['Total Rax']}")
        st.write(f"Adjusted RAX (with {rarity} multiplier): {adjusted_rax}")

        # Update cache file with this fighter
        if cache_df is None:
            cache_df = pd.DataFrame([result])
        else:
            cache_df = cache_df[cache_df['Fighter Name'].str.lower() != result['Fighter Name'].lower()]
            cache_df = pd.concat([cache_df, pd.DataFrame([result])], ignore_index=True)

        cache_df.to_csv(CACHE_FILE, index=False)
