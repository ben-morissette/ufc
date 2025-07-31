import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from difflib import get_close_matches

# === Helper scraping functions ===

def search_fighter_by_name_part(query):
    url = "http://ufcstats.com/statistics/fighters/search"
    params = {"query": query}
    response = requests.get(url, params=params)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    if not table:
        return []
    rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
    candidates = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        first_name_col = cols[0].find('a', class_='b-link_style_black')
        last_name_col = cols[1].find('a', class_='b-link_style_black')
        if not first_name_col or not last_name_col:
            continue
        first_name = first_name_col.get_text(strip=True)
        last_name = last_name_col.get_text(strip=True)
        fighter_link = last_name_col['href']
        full_name = f"{first_name} {last_name}".strip()
        candidates.append((full_name, fighter_link))
    return candidates

def get_fighter_url_by_name(fighter_name):
    name_parts = fighter_name.strip().split()
    fighter_name_clean = fighter_name.strip().lower()

    if len(name_parts) > 1:
        last_name = name_parts[-1]
        first_name = name_parts[0]
        candidates = search_fighter_by_name_part(last_name)
        if not candidates:
            candidates = search_fighter_by_name_part(first_name)
        if not candidates:
            for part in name_parts:
                candidates = search_fighter_by_name_part(part)
                if candidates:
                    break
        if not candidates:
            raise ValueError(f"No suitable match found for fighter: {fighter_name_clean}")
        all_names = [c[0].lower() for c in candidates]
        close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.0)
        if close:
            best = close[0]
            for c in candidates:
                if c[0].lower() == best:
                    return c[1]
            return candidates[0][1]
        else:
            return candidates[0][1]
    else:
        query = name_parts[0]
        candidates = search_fighter_by_name_part(query)
        if not candidates:
            raise ValueError(f"No suitable match found for fighter: {fighter_name_clean}")
        all_names = [c[0].lower() for c in candidates]
        close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.0)
        if close:
            best = close[0]
            for c in candidates:
                if c[0].lower() == best:
                    return c[1]
            return candidates[0][1]
        else:
            return candidates[0][1]

def get_two_values_from_col(col):
    ps = col.find_all('p', class_='b-fight-details__table-text')
    if len(ps) == 2:
        return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
    return None, None

def ctrl_to_seconds(x):
    if x and ':' in x:
        m,s = x.split(':')
        if m.isdigit() and s.isdigit():
            return str(int(m)*60 + int(s))
    return x

def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        raise Exception("No fight details table found on the fighter page.")
    
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

        fights_data.append({
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
            'time_seconds': time_val,
            'fight_link': fight_url
        })

    return pd.DataFrame(fights_data)

# Helper to parse significant strikes landed from string like "20 of 30"
def parse_sig_strikes(strike_str):
    if not strike_str or 'of' not in strike_str:
        return 0
    try:
        landed = int(strike_str.split('of')[0].strip())
        return landed
    except:
        return 0

def calculate_rax(row):
    rax = 0
    if row['Result'] and row['Result'].lower() == 'win':
        method = row['Method Main']
        if method:
            method = method.strip().lower()
        else:
            method = ''

        if method in ['ko', 'tko', 'ko/tko']:
            rax += 100
        elif method in ['sub', 'submission', 'submission attempts']:
            rax += 90
        elif method in ['u-dec', 'decision - unanimous', 'decision unanimous']:
            rax += 80
        elif method in ['m-dec', 'decision - majority', 'decision majority']:
            rax += 75
        elif method in ['s-dec', 'decision - split', 'decision split']:
            rax += 70
        # No fallback: if no match, no points added for method

    elif row['Result'] and row['Result'].lower() == 'loss':
        rax += 25

    try:
        sig_str_fighter = int(row.get('Strikes Fighter', '0'))
    except:
        sig_str_fighter = 0
    try:
        sig_str_opponent = int(row.get('Strikes Opponent', '0'))
    except:
        sig_str_opponent = 0

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    if row.get('Round', '') == '5':
        rax += 25

    if row.get('Method Detail') and 'Fight of the Night' in row['Method Detail']:
        rax += 50

    return rax


# === Streamlit app ===

st.title("UFC Fighter RAX Calculator")

fighter_name = st.text_input("Enter UFC Fighter Name", value="Conor McGregor")

if st.button("Calculate Total RAX"):
    with st.spinner(f"Looking up {fighter_name}..."):
        try:
            fighter_url = get_fighter_url_by_name(fighter_name)
            fights_df = get_fight_links(fighter_url)

            # Calculate RAX for each fight
            fights_df['RAX'] = fights_df.apply(calculate_rax, axis=1)

            total_rax = fights_df['RAX'].sum()

            st.success(f"Total RAX for {fighter_name}: {total_rax}")

            # Show detailed dataframe with RAX breakdown
            display_cols = [
                'event_date', 'event_name', 'opponent_name', 'result', 'method_main',
                'method_detail', 'round', 'time_seconds', 'RAX'
            ]
            st.subheader("RAX Breakdown by Fight")
            st.dataframe(fights_df[display_cols].sort_values(by='event_date', ascending=False).reset_index(drop=True))

        except Exception as e:
            st.error(f"Error: {e}")
