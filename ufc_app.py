import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import difflib

RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

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
    if len(ps) == 2:
        return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
    else:
        return None, None

def get_fight_data(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        return pd.DataFrame()

    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fights = []

    method_map = {
        'KO/TKO': 'KO/TKO',
        'Submission': 'Submission',
        'U-DEC': 'Decision - Unanimous',
        'M-DEC': 'Decision - Majority',
        'S-DEC': 'Decision - Split',
    }

    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')

        result = cols[0].find('p').get_text(strip=True).lower()
        fighter_name = cols[1].find_all('p')[0].get_text(strip=True)
        opponent_name = cols[1].find_all('p')[1].get_text(strip=True)

        kd_fighter, kd_opponent = get_two_values_from_col(cols[2])
        str_fighter, str_opponent = get_two_values_from_col(cols[3])
        td_fighter, td_opponent = get_two_values_from_col(cols[4])
        sub_fighter, sub_opponent = get_two_values_from_col(cols[5])

        event_name = cols[6].find_all('p')[0].get_text(strip=True)
        event_date = cols[6].find_all('p')[1].get_text(strip=True) if len(cols[6].find_all('p')) > 1 else None

        method_main_raw = cols[7].find_all('p')[0].get_text(strip=True)
        method_detail = cols[7].find_all('p')[1].get_text(strip=True) if len(cols[7].find_all('p')) > 1 else ''

        method_main = method_map.get(method_main_raw, method_main_raw)

        round_val = cols[8].find('p').get_text(strip=True)
        time_val = cols[9].find('p').get_text(strip=True) if len(cols) > 9 else ''

        fight_url = ''  # Placeholder for fight-specific URL if you want to add it later

        fight_data = {
            'result': result,
            'fighter_name': fighter_name,
            'opponent_name': opponent_name,
            'kd_fighter': kd_fighter,
            'kd_opponent': kd_opponent,
            'str_fighter': str_fighter,
            'str_opponent': str_opponent,
            'td_fighter': td_fighter,
            'td_opponent': td_opponent,
            'sub_fighter': sub_fighter,
            'sub_opponent': sub_opponent,
            'event_name': event_name,
            'event_date': event_date,
            'method_main': method_main,
            'method_detail': method_detail,
            'round': round_val,
            'Time': time_val,
            'fight_link': fight_url
        }
        fights.append(fight_data)

    return pd.DataFrame(fights)

def calculate_rax(row):
    rax = 0
    # Rule 1: Rax based on method_main
    if row['result'] == 'win':
        if row['method_main'] == 'KO/TKO':
            rax += 100
        elif row['method_main'] == 'Submission':
            rax += 90
        elif row['method_main'] == 'Decision - Unanimous':
            rax += 80
        elif row['method_main'] == 'Decision - Majority':
            rax += 75
        elif row['method_main'] == 'Decision - Split':
            rax += 70
    elif row['result'] == 'loss':
        rax += 25

    # Rule 2: Rax based on significant strike difference
    sig_str_fighter = 0
    sig_str_opponent = 0
    try:
        sig_str_fighter = int(row['str_fighter']) if row['str_fighter'] is not None else 0
        sig_str_opponent = int(row['str_opponent']) if row['str_opponent'] is not None else 0
    except:
        sig_str_fighter = 0
        sig_str_opponent = 0

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights
    if '5 Rnd' in str(row.get('Time', '')) or '5' in str(row.get('round', '')):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Fight of the Night' in str(row.get('method_detail', '')) or 'Fight of the Night' in str(row.get('event_name', '')):
        rax += 50

    return rax

st.title("UFC Fighter RAX Search")

@st.cache_data(show_spinner=False)
def load_all_fighters():
    return get_all_fighters()

with st.spinner("Loading fighter list (this may take a moment)..."):
    fighter_dict = load_all_fighters()

fighter_names = list(fighter_dict.keys())

search_input = st.text_input("Type full or partial fighter name and press Enter")

if search_input.strip():
    # Try to find best match, fallback to no results
    matches = difflib.get_close_matches(search_input.strip(), fighter_names, n=1, cutoff=0.3)
    if not matches:
        st.warning("No fighters matched your search. Try a different name or spelling.")
    else:
        selected_name = matches[0]
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
                fights_df[[
                    'event_date',
                    'event_name',
                    'result',
                    'opponent_name',
                    'method_main',
                    'method_detail',
                    'round',
                    'Time',
                    'kd_fighter',
                    'kd_opponent',
                    'str_fighter',
                    'str_opponent',
                    'td_fighter',
                    'td_opponent',
                    'sub_fighter',
                    'sub_opponent',
                    'Rax Earned'
                ]],
                use_container_width=True,
            )
else:
    st.info("Please type a fighter's name above and press Enter to search.")
