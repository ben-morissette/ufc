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

        if time_val and ':' in time_val:
            parts = time_val.split(':')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                mm, ss = parts
                total_sec = int(mm)*60 + int(ss)
                time_val = str(total_sec)

        details = ""  # We will check event_name for FOTN instead

        fight_data = {
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
            'Event Date': event_date,
            'Method Main': method_main,
            'Method Detail': method_detail,
            'Round': round_val,
            'Time (seconds)': time_val,
            'Details': details,
        }
        
        fights_data.append(fight_data)
    return pd.DataFrame(fights_data)

# RAX calculation function updated to check "Fight of the Night" variants in Event Name
def calculate_rax(row):
    rax = 0
    result = str(row.get('Result', '')).strip().lower()
    method = str(row.get('Method Main', '')).strip().lower()
    
    if result == 'win':
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
    elif result == 'loss':
        rax += 25

    try:
        sig_str_fighter = int(row.get('Strikes Fighter', '0'))
        sig_str_opponent = int(row.get('Strikes Opponent', '0'))
    except ValueError:
        sig_str_fighter = 0
        sig_str_opponent = 0

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    round_val = str(row.get('Round', ''))
    if round_val == '5':
        rax += 25

    event_name = str(row.get('Event Name', '')).lower()
    # Check variants of fight of the night in event name
    if any(phrase in event_name for phrase in ['fight of the night', 'fight of night', 'fight night']):
        rax += 50

    return rax

# === Streamlit app ===

st.title("UFC Fighter Fight History & RAX Calculator")

fighter_name = st.text_input("Enter UFC Fighter Name", value="Conor McGregor")

if st.button("Get Fighter Fights & Calculate RAX"):
    with st.spinner(f"Looking up {fighter_name}..."):
        try:
            url = get_fighter_url_by_name(fighter_name)
            st.success(f"Found fighter page: {url}")

            fights_df = get_fight_links(url)
            if fights_df.empty:
                st.warning("No fights found for this fighter.")
            else:
                fights_df['Fight Title'] = fights_df['Event Name'].fillna('Unknown Event')
                fights_df['RAX Earned'] = fights_df.apply(calculate_rax, axis=1)
                
                total_rax = fights_df['RAX Earned'].sum()
                st.markdown(f"### Total RAX earned by {fighter_name}: **{total_rax}**")
                
                st.markdown(f"### Fight details with RAX earned per fight")
                st.dataframe(fights_df[['Fight Title', 'Result', 'Method Main', 'Round', 'Strikes Fighter', 'Strikes Opponent', 'RAX Earned']])

        except Exception as e:
            st.error(f"Error: {str(e)}")
