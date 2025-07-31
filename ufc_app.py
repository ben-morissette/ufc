import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os

CACHE_FILE = 'ufc_rax_leaderboard.csv'
FIGHTER_LIMIT = 10
RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

# Utilities
def get_last_tuesday(reference_date=None):
    if reference_date is None:
        reference_date = datetime.now()
    days_since_tuesday = (reference_date.weekday() - 1) % 7
    return reference_date - timedelta(days=days_since_tuesday)

def cache_is_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    return mod_time >= get_last_tuesday()

# Scraper
def get_fighter_urls():
    url = "http://ufcstats.com/statistics/fighters"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
    urls = []
    for row in rows:
        link = row.find_all('td')[0].find('a', class_='b-link_style_black')
        if link and link.has_attr('href'):
            urls.append(link['href'])
    return urls[:FIGHTER_LIMIT]

def get_two_values_from_col(col):
    ps = col.find_all('p', class_='b-fight-details__table-text')
    return (ps[0].get_text(strip=True), ps[1].get_text(strip=True)) if len(ps) == 2 else (None, None)

def get_fight_data(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        return pd.DataFrame()

    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fights = []
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        result = cols[0].find('p').get_text(strip=True).lower()
        fighter_name = cols[1].find_all('p')[0].get_text(strip=True)
        opponent_name = cols[1].find_all('p')[1].get_text(strip=True)
        kd_f, kd_o = get_two_values_from_col(cols[2])
        str_f, str_o = get_two_values_from_col(cols[3])
        td_f, td_o = get_two_values_from_col(cols[4])
        sub_f, sub_o = get_two_values_from_col(cols[5])
        event_name = cols[6].find_all('p')[0].get_text(strip=True)
        method = cols[7].find_all('p')[0].get_text(strip=True)
        round_val = cols[8].find('p').get_text(strip=True)

        fights.append({
            'Result': result,
            'Fighter Name': fighter_name,
            'Opponent Name': opponent_name,
            'KD Fighter': kd_f,
            'KD Opponent': kd_o,
            'Strikes Fighter': str_f,
            'Strikes Opponent': str_o,
            'Takedowns Fighter': td_f,
            'Takedowns Opponent': td_o,
            'Submission Attempts Fighter': sub_f,
            'Submission Attempts Opponent': sub_o,
            'Event Name': event_name,
            'Method Main': method,
            'Round': round_val,
        })
    return pd.DataFrame(fights)

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
        strike_diff = int(row['Strikes Fighter']) - int(row['Strikes Opponent'])
        if strike_diff > 0:
            rax += strike_diff
    except:
        pass

    if row['Round'] == '5':
        rax += 25

    ev = row['Event Name'].lower()
    if 'fight of the night' in ev or 'fight of night' in ev:
        rax += 50
    if 'championship' in ev:
        rax += 25

    return rax

def generate_leaderboard():
    fighter_urls = get_fighter_urls()
    leaderboard = []
    for idx, url in enumerate(fighter_urls):
        try:
            fights_df = get_fight_data(url)
            if fights_df.empty:
                continue
            fights_df['Rax Earned'] = fights_df.apply(calculate_rax, axis=1)
            total_rax = fights_df['Rax Earned'].sum()
            name = fights_df.iloc[0]['Fighter Name']
            leaderboard.append({
                'Fighter Name': name,
                'Base Rax': total_rax,
                'Fight Count': len(fights_df),
                'Rarity': 'Uncommon',
            })
        except Exception as e:
            continue
    df = pd.DataFrame(leaderboard)
    df = df.sort_values(by='Base Rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', df.index + 1)
    return df

st.title("UFC Fighter RAX Leaderboard")

if cache_is_fresh():
    leaderboard_df = pd.read_csv(CACHE_FILE)
    if 'Rank' in leaderboard_df.columns:
        leaderboard_df.drop(columns=['Rank'], inplace=True)
    leaderboard_df.insert(0, 'Rank', leaderboard_df.index + 1)
    leaderboard_df['Rarity'] = 'Uncommon'
    leaderboard_df.rename(columns={'Total Rax': 'Base Rax'}, inplace=True, errors='ignore')
else:
    leaderboard_df = generate_leaderboard()
    leaderboard_df.to_csv(CACHE_FILE, index=False)

# Session state to hold dataframe between runs
if 'edited_df' not in st.session_state:
    st.session_state.edited_df = leaderboard_df.copy()

# Editable table for rarity selection + other info
st.write("Edit the 'Rarity' column and click 'Recalculate Adjusted RAX'")

edited = st.data_editor(
    st.session_state.edited_df,
    column_config={
        "Rarity": st.column_config.SelectboxColumn(
            "Rarity",
            options=list(RARITY_MULTIPLIERS.keys()),
            required=True,
        )
    },
    use_container_width=True,
    num_rows="fixed"
)

# Button to recalculate Total Rax with updated rarity
if st.button("Recalculate Adjusted RAX"):
    # Update session state with user edits
    st.session_state.edited_df = edited.copy()
    # Compute adjusted RAX
    st.session_state.edited_df['Total Rax'] = st.session_state.edited_df.apply(
        lambda row: round(row['Base Rax'] * RARITY_MULTIPLIERS[row['Rarity']], 1),
        axis=1
    )
    # Show updated table (non-editable)
    st.success("Adjusted RAX recalculated!")
    st.dataframe(
        st.session_state.edited_df[['Rank', 'Fighter Name', 'Total Rax', 'Rarity', 'Fight Count']],
        use_container_width=True
    )
else:
    # Before recalculation, just show editable table without Total Rax adjusted column
    st.dataframe(
        st.session_state.edited_df[['Rank', 'Fighter Name', 'Base Rax', 'Rarity', 'Fight Count']],
        use_container_width=True
    )
