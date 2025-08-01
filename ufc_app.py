import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import difflib

RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

# Get all fighters from all alphabet pages (A-Z)
def get_all_fighters():
    base_url = "http://ufcstats.com/statistics/fighters?char="
    fighters = {}
    for letter in list("abcdefghijklmnopqrstuvwxyz"):
        url = base_url + letter
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='b-statistics__table')
        if not table:
            continue
        rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
        for row in rows:
            link = row.find_all('td')[0].find('a', class_='b-link_style_black')
            if link and link.has_attr('href'):
                name = link.text.strip()
                href = link['href']
                fighters[name] = href
    return fighters

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

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def calculate_rax(row):
    rax = 0
    if row['Result'] == 'win':
        method = row['Method Main'].lower()
        if 'ko' in method or 'tko' in method:
            rax += 100
        elif 'submission' in method:
            rax += 90
        elif 'unanimous' in method:
            rax += 80
        elif 'majority' in method:
            rax += 75
        elif 'split' in method:
            rax += 70
    elif row['Result'] == 'loss':
        rax += 25

    strike_diff = safe_int(row['Strikes Fighter']) - safe_int(row['Strikes Opponent'])
    if strike_diff > 0:
        rax += strike_diff

    if row['Round'] == '5':
        rax += 25

    ev = row['Event Name'].lower()
    if 'fight of the night' in ev or 'fight of night' in ev:
        rax += 50
    if 'championship' in ev:
        rax += 25

    return rax

# --- Streamlit UI ---

st.title("UFC Fighter RAX Search")

@st.cache_data(show_spinner=False)
def load_all_fighters():
    return get_all_fighters()

with st.spinner("Loading fighter list (this may take a moment)..."):
    fighter_dict = load_all_fighters()

fighter_names = list(fighter_dict.keys())

search_input = st.text_input("Type fighter name to search")

matched_names = []
if search_input.strip():
    # Use difflib to get close matches ignoring case
    matched_names = difflib.get_close_matches(search_input.strip(), fighter_names, n=10, cutoff=0.3)

if not matched_names and search_input.strip():
    st.warning("No fighters matched your search. Try a different name or spelling.")

selected_name = None
if matched_names:
    selected_name = st.selectbox("Select a fighter from matches", [""] + matched_names)

if selected_name:
    url = fighter_dict[selected_name]
    with st.spinner(f"Loading fights for {selected_name}..."):
        fights_df = get_fight_data(url)
    if fights_df.empty:
        st.warning("No fight data found for this fighter.")
    else:
        fights_df['Rax Earned'] = fights_df.apply(calculate_rax, axis=1)
        total_rax = fights_df['Rax Earned'].sum()

        rarity = st.selectbox("Select Rarity Multiplier", list(RARITY_MULTIPLIERS.keys()), index=0)
        multiplier = RARITY_MULTIPLIERS[rarity]
        adjusted_rax = round(total_rax * multiplier, 1)

        st.markdown(f"### {selected_name} - Total RAX: {total_rax} (Adjusted: {adjusted_rax} × {rarity})")

        st.dataframe(
            fights_df[['Event Name', 'Result', 'Opponent Name', 'Method Main', 'Round', 'Rax Earned']],
            use_container_width=True,
        )
