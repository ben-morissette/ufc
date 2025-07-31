import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# === Helper scraping functions ===

def get_fighters_list(limit=10):
    url = "http://ufcstats.com/statistics/fighters"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    fighters = []
    for row in table.find('tbody').find_all('tr', class_='b-statistics__table-row'):
        # The first 'a' tag in the row under first column holds fighter's page and name
        a_tag = row.find('a', class_='b-link_style_black')
        if a_tag:
            fighter_name = a_tag.text.strip()
            fighter_url = a_tag['href']
            fighters.append({'name': fighter_name, 'url': fighter_url})
            if len(fighters) >= limit:
                break
    return fighters

def get_two_values_from_col(col):
    ps = col.find_all('p', class_='b-fight-details__table-text')
    if len(ps) == 2:
        return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
    return None, None

def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        return pd.DataFrame()
    
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fights_data = []
    
    for row in rows:
        fight_url = row.get('data-link')
        if not fight_url:
            continue
        
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
        event_date = event_td[1].get_text(strip=True) if len(event_td) > 1 else None

        method_td = cols[7].find_all('p', class_='b-fight-details__table-text')
        method_main = method_td[0].get_text(strip=True) if len(method_td) > 0 else None
        method_detail = method_td[1].get_text(strip=True) if len(method_td) > 1 else None

        round_val = cols[8].find('p', class_='b-fight-details__table-text')
        round_val = round_val.get_text(strip=True) if round_val else None

        time_val = cols[9].find('p', class_='b-fight-details__table-text')
        time_val = time_val.get_text(strip=True) if time_val else None

        # Convert time_val to seconds if mm:ss
        if time_val and ':' in time_val:
            parts = time_val.split(':')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                mm, ss = parts
                total_sec = int(mm)*60 + int(ss)
                time_val = str(total_sec)

        fight_data = {
            'result': result,
            'fighter_name': fighter_name,
            'opponent_name': opponent_name,
            'kd_fighter': kd_fighter,
            'kd_opponent': kd_opponent,
            'strikes_fighter': str_fighter,
            'strikes_opponent': str_opponent,
            'td_fighter': td_fighter,
            'td_opponent': td_opponent,
            'sub_fighter': sub_fighter,
            'sub_opponent': sub_opponent,
            'event_name': event_name,
            'event_date': event_date,
            'method_main': method_main,
            'method_detail': method_detail,
            'round': round_val,
            'time_seconds': time_val,
        }
        
        fights_data.append(fight_data)

    return pd.DataFrame(fights_data)

# Rarity multipliers
RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2.0,
    "Legendary": 2.5,
    "Mystic": 4.0,
    "Iconic": 6.0,
}

def calculate_rax(row):
    rax = 0

    if row['result'] == 'win':
        if row['method_main'] == 'KO/TKO':
            rax += 100
        elif row['method_main'] in ['Submission', 'SUB']:
            rax += 90
        elif row['method_main'] in ['Decision - Unanimous', 'U-DEC', 'Decision - unanimous']:
            rax += 80
        elif row['method_main'] in ['Decision - Majority', 'M-DEC']:
            rax += 75
        elif row['method_main'] in ['Decision - Split', 'S-DEC']:
            rax += 70
    elif row['result'] == 'loss':
        rax += 25

    try:
        sig_str_fighter = int(row['strikes_fighter']) if row['strikes_fighter'] and row['strikes_fighter'].isdigit() else 0
        sig_str_opponent = int(row['strikes_opponent']) if row['strikes_opponent'] and row['strikes_opponent'].isdigit() else 0
    except Exception:
        sig_str_fighter = 0
        sig_str_opponent = 0

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    if row['event_name']:
        event_name_lower = row['event_name'].lower()
        if '5 rnd' in event_name_lower or '5 round' in event_name_lower or 'championship' in event_name_lower:
            rax += 25

    if row['event_name']:
        event_name_lower = row['event_name'].lower()
        if 'fight of the night' in event_name_lower or 'fight of night' in event_name_lower or 'fight night' in event_name_lower:
            rax += 50

    return rax

st.title("UFC Fighter RAX Leaderboard with Rarity Multiplier (Auto Fetch)")

rarity = st.selectbox(
    "Select Rarity multiplier",
    list(RARITY_MULTIPLIERS.keys()),
    index=0,
    help="Select rarity level for RAX multiplier"
)
rarity_multiplier = RARITY_MULTIPLIERS[rarity]

@st.cache_data(ttl=60*60*24*7)  # cache 1 week
def get_rax_for_fighter(fighter):
    try:
        df_fights = get_fight_links(fighter['url'])
        if df_fights.empty:
            return 0, pd.DataFrame()
        df_fights['rax'] = df_fights.apply(calculate_rax, axis=1)
        total_rax = df_fights['rax'].sum() * rarity_multiplier
        df_fights['rax_with_multiplier'] = df_fights['rax'] * rarity_multiplier
        return total_rax, df_fights
    except Exception as e:
        st.warning(f"Could not get data for {fighter['name']}: {e}")
        return 0, pd.DataFrame()

if st.button("Generate Leaderboard for First 10 Fighters"):
    fighters = get_fighters_list(limit=10)
    leaderboard = []
    for fighter in fighters:
        total_rax, df_fights = get_rax_for_fighter(fighter)
        leaderboard.append({
            'fighter': fighter['name'],
            'total_rax': total_rax,
            'fight_details': df_fights
        })
    leaderboard_df = pd.DataFrame(leaderboard).sort_values('total_rax', ascending=False).reset_index(drop=True)
    
    st.subheader("Leaderboard")
    st.dataframe(leaderboard_df[['fighter', 'total_rax']])

    selected = st.selectbox("Select a fighter to see detailed fight RAX breakdown:", leaderboard_df['fighter'])
    selected_fight_df = leaderboard_df[leaderboard_df['fighter'] == selected]['fight_details'].values[0]
    if not selected_fight_df.empty:
        display_df = selected_fight_df[[
            'event_name', 'result', 'method_main', 'round', 'time_seconds',
            'strikes_fighter', 'strikes_opponent', 'rax', 'rax_with_multiplier'
        ]]
        st.write(f"Detailed fight breakdown for {selected} (RAX multiplied by {rarity}):")
        st.dataframe(display_df)
    else:
        st.write("No fight data found for this fighter.")
