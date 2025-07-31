import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os

CACHE_FILE = 'ufc_rax_leaderboard.csv'
FIGHTER_LIMIT = 10  # Limit for test runs

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
    urls = []
    for row in rows:
        name_cell = row.find_all('td')[0]
        link = name_cell.find('a', class_='b-link_style_black')
        if link and link.has_attr('href'):
            urls.append(link['href'])
    return urls[:FIGHTER_LIMIT]

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
        method = row['Method Main']
        if method == 'KO/TKO':
            rax += 100
        elif method in ['Submission', 'SUB']:
            rax += 90
        elif method in ['Decision - Unanimous', 'U-DEC']:
            rax += 80
        elif method == 'Decision - Majority':
            rax += 75
        elif method == 'Decision - Split':
            rax += 70
    elif row['Result'] == 'loss':
        rax += 25

    try:
        strikes_fighter = int(row['Strikes Fighter'])
    except:
        strikes_fighter = 0
    try:
        strikes_opponent = int(row['Strikes Opponent'])
    except:
        strikes_opponent = 0

    strike_diff = strikes_fighter - strikes_opponent
    if strike_diff > 0:
        rax += strike_diff

    if row['Round'] == '5':
        rax += 25

    event_name = row['Event Name'].lower() if row['Event Name'] else ''
    if 'fight of the night' in event_name or 'fight of night' in event_name:
        rax += 50
    if 'championship' in event_name:
        rax += 25

    return rax

def generate_leaderboard():
    st.info("Generating leaderboard for the first 10 fighters (testing)...")
    fighter_urls = get_fighter_urls()
    leaderboard = []

    for idx, url in enumerate(fighter_urls):
        try:
            fights_df = get_fight_data(url)
            if fights_df.empty:
                continue
            fights_df['Rax Earned'] = fights_df.apply(calculate_rax, axis=1)
            total_rax = fights_df['Rax Earned'].sum()
            fighter_name = fights_df.iloc[0]['Fighter Name']
            leaderboard.append({
                'Fighter Name': fighter_name,
                'Total Rax': total_rax,
                'Fight Count': len(fights_df),
            })
            if idx % 5 == 0:
                st.write(f"Processed {idx + 1} fighters...")
        except Exception as e:
            st.warning(f"Error processing fighter {url}: {e}")
            continue

    leaderboard_df = pd.DataFrame(leaderboard)
    if not leaderboard_df.empty:
        leaderboard_df = leaderboard_df.sort_values(by='Total Rax', ascending=False).reset_index(drop=True)
        leaderboard_df['Rank'] = leaderboard_df.index + 1
    return leaderboard_df

# === Main app ===

st.title("UFC Fighter RAX Leaderboard (Test with 10 fighters)")

if cache_is_fresh():
    st.success("Loading leaderboard from cached CSV (updated after last Tuesday).")
    leaderboard_df = pd.read_csv(CACHE_FILE)
else:
    leaderboard_df = generate_leaderboard()
    if not leaderboard_df.empty:
        leaderboard_df.to_csv(CACHE_FILE, index=False)
        st.success("Leaderboard generated and cached.")

if not leaderboard_df.empty:
    if 'Rank' not in leaderboard_df.columns:
        leaderboard_df = leaderboard_df.sort_values(by='Total Rax', ascending=False).reset_index(drop=True)
        leaderboard_df['Rank'] = leaderboard_df.index + 1

    st.markdown("### Leaderboard")
    for i, row in leaderboard_df.iterrows():
        with st.container():
            rarity = st.selectbox(
                f"Rarity for {row['Fighter Name']} (Rank {int(row['Rank'])})",
                options=list(RARITY_MULTIPLIERS.keys()),
                key=f"rarity_{i}",
                index=0
            )
            multiplier = RARITY_MULTIPLIERS[rarity]
            adjusted_rax = int(row['Total Rax'] * multiplier)

            st.markdown(
                f"""
                <div style='border: 1px solid #999; border-radius: 10px; padding: 10px; margin-bottom: 10px; background-color: #f9f9f9'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div><b>Rank:</b> {row['Rank']}</div>
                        <div><b>Fighter:</b> {row['Fighter Name']}</div>
                        <div><b>RAX:</b> {adjusted_rax}</div>
                        <div style='width: 200px;'>{rarity}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
else:
    st.write("No leaderboard data available.")
