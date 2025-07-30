import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import string
import time
from tqdm import tqdm

# ------------------------
# Helper Functions
# ------------------------

def get_all_fighter_links():
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="
    
    for letter in string.ascii_lowercase:
        url = f"{base_url}{letter}&page=all"
        retries = 3
        for i in range(retries):
            try:
                response = requests.get(url)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                time.sleep(2)
        else:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        fighter_table = soup.find('table', class_='b-statistics__table')
        if not fighter_table:
            continue

        fighter_rows = fighter_table.find('tbody').find_all('tr', class_='b-statistics__table-row')
        if not fighter_rows:
            continue

        for row in fighter_rows:
            link_tag = row.find('a', class_='b-link_style_black')
            if link_tag and 'href' in link_tag.attrs:
                all_links.append(link_tag['href'])

    return list(set(all_links))


def get_fight_links(fighter_url):
    # Get main fights table for fighter
    retries = 3
    for i in range(retries):
        try:
            resp = requests.get(fighter_url)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException:
            time.sleep(2)
    else:
        raise ValueError(f"Failed to get fighter page: {fighter_url}")

    soup = BeautifulSoup(resp.text, 'html.parser')

    table = soup.find('table', class_='b-fight-details__table')
    if not table:
        raise ValueError("Fight table not found")

    rows = table.find('tbody').find_all('tr')

    fight_links = []
    data = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 7:
            continue

        fight_link_tag = cols[0].find('a')
        fight_link = fight_link_tag['href'] if fight_link_tag else None

        fighter_name = cols[1].text.strip()
        opponent_name = cols[2].text.strip()
        result = cols[3].text.strip().lower()
        method_main = cols[4].text.strip()
        time_str = cols[5].text.strip()
        round_ = cols[6].text.strip()

        if fight_link:
            fight_links.append(fight_link)

        data.append({
            'fight_link': fight_link,
            'fighter_name': fighter_name,
            'opponent_name': opponent_name,
            'result': result,
            'method_main': method_main,
            'TimeFormat': time_str + " Rnd " + round_
        })

    df = pd.DataFrame(data)
    return fight_links, df


def parse_fight_details(fight_link, fighter_name, opponent_name):
    # Scrape fight details page for advanced stats

    retries = 3
    for i in range(retries):
        try:
            resp = requests.get(fight_link)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException:
            time.sleep(2)
    else:
        return {}

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Grab details like Fight of the Night, etc.
    details_div = soup.find('div', class_='b-fight-details__fight-title')
    details_text = details_div.text.strip() if details_div else ""

    # Find stats tables for fighter and opponent
    tables = soup.find_all('table', class_='b-fight-details__table')

    # Initialize stats dict
    stats = {
        'fight_link': fight_link,
        'Details': details_text,
        'TOT_fighter_SigStr_landed': 0,
        'TOT_opponent_SigStr_landed': 0
    }

    try:
        # First table: fighter stats, second: opponent stats
        fighter_table = tables[0]
        opponent_table = tables[1]

        # Find significant strikes landed for fighter
        fighter_rows = fighter_table.find_all('tr')
        for row in fighter_rows:
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            stat_name = cols[0].text.strip()
            if stat_name == 'Sig. Strikes Landed':
                val = cols[1].text.strip()
                stats['TOT_fighter_SigStr_landed'] = int(val) if val.isdigit() else 0
                break

        # Find significant strikes landed for opponent
        opponent_rows = opponent_table.find_all('tr')
        for row in opponent_rows:
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            stat_name = cols[0].text.strip()
            if stat_name == 'Sig. Strikes Landed':
                val = cols[1].text.strip()
                stats['TOT_opponent_SigStr_landed'] = int(val) if val.isdigit() else 0
                break

    except Exception:
        pass

    return stats


def transform_columns(df):
    # Make sure 'TimeFormat' is string, etc.
    if 'TimeFormat' in df.columns:
        df['TimeFormat'] = df['TimeFormat'].astype(str)
    if 'Details' not in df.columns:
        df['Details'] = ""

    # Fill missing sig strikes with 0
    if 'TOT_fighter_SigStr_landed' in df.columns:
        df['TOT_fighter_SigStr_landed'] = pd.to_numeric(df['TOT_fighter_SigStr_landed'], errors='coerce').fillna(0)
    else:
        df['TOT_fighter_SigStr_landed'] = 0

    if 'TOT_opponent_SigStr_landed' in df.columns:
        df['TOT_opponent_SigStr_landed'] = pd.to_numeric(df['TOT_opponent_SigStr_landed'], errors='coerce').fillna(0)
    else:
        df['TOT_opponent_SigStr_landed'] = 0

    return df


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
    if 'TOT_fighter_SigStr_landed' in row.index and 'TOT_opponent_SigStr_landed' in row.index:
        sig_str_fighter = row['TOT_fighter_SigStr_landed']
        sig_str_opponent = row['TOT_opponent_SigStr_landed']

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights
    if 'TimeFormat' in row.index and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Details' in row.index and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax


# ------------------------
# Main data processing pipeline
# ------------------------

@st.cache_data(show_spinner=True)
def process_fighter(fighter_url):
    fight_links, main_fights_df = get_fight_links(fighter_url)
    fighter_fight_details = []
    for fl in fight_links:
        row_index = main_fights_df.index[main_fights_df['fight_link'] == fl].tolist()
        if not row_index:
            continue
        row = main_fights_df.loc[row_index[0]]

        main_fighter_name = row['fighter_name']
        opp_name = row['opponent_name']
        details = parse_fight_details(fl, main_fighter_name, opp_name)
        fighter_fight_details.append(details)

    if not fighter_fight_details:
        return None, None

    advanced_df = pd.DataFrame(fighter_fight_details)
    combined_df = pd.merge(main_fights_df, advanced_df, on='fight_link', how='left')
    combined_df = transform_columns(combined_df)
    combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)
    total_rax = combined_df['rax_earned'].sum()

    return main_fighter_name, total_rax


@st.cache_resource(show_spinner=True)
def build_leaderboard():
    fighter_links = get_all_fighter_links()
    all_fighters_data = []

    for fighter_url in tqdm(fighter_links, desc="Processing fighters"):
        try:
            fighter_name, total_rax = process_fighter(fighter_url)
            if fighter_name and total_rax is not None:
                all_fighters_data.append({'fighter_name': fighter_name, 'total_rax': total_rax})
        except Exception:
            # Ignore errors for now
            continue

    leaderboard_df = pd.DataFrame(all_fighters_data)
    return leaderboard_df.sort_values(by='total_rax', ascending=False).reset_index(drop=True)


# ------------------------
# Streamlit UI
# ------------------------

def main():
    st.title("UFC Fighter RAX Leaderboard")
    st.write("Leaderboard ranks fighters by their total calculated RAX score based on fight outcomes and stats.")

    with st.spinner("Building leaderboard... This may take several minutes on first run."):
        leaderboard_df = build_leaderboard()

    search_name = st.text_input("Search fighter by name:", "").strip().lower()

    if search_name:
        filtered_df = leaderboard_df[leaderboard_df['fighter_name'].str.lower().str.contains(search_name)]
    else:
        filtered_df = leaderboard_df

    st.dataframe(filtered_df.style.highlight_max(subset=['total_rax'], color='lightgreen'))


if __name__ == "__main__":
    main()
