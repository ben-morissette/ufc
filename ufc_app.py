import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import string
import time
from datetime import datetime
import os

LEADERBOARD_FILE = "rax_leaderboard.csv"

# -------------------------------
# RAX calculation logic
# -------------------------------
def calculate_rax(row):
    rax = 0
    if row.get('result') == 'win':
        if row.get('method_main') == 'KO/TKO':
            rax += 100
        elif row.get('method_main') == 'Submission':
            rax += 90
        elif row.get('method_main') == 'Decision - Unanimous':
            rax += 80
        elif row.get('method_main') == 'Decision - Majority':
            rax += 75
        elif row.get('method_main') == 'Decision - Split':
            rax += 70
    elif row.get('result') == 'loss':
        rax += 25

    if 'TOT_fighter_SigStr_landed' in row and 'TOT_opponent_SigStr_landed' in row:
        diff = row['TOT_fighter_SigStr_landed'] - row['TOT_opponent_SigStr_landed']
        if diff > 0:
            rax += diff

    if 'TimeFormat' in row and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# -------------------------------
def get_all_fighter_links():
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="

    progress_fighters = st.progress(0)
    status_fighters = st.empty()

    total_fighters_estimate = 0
    fighters_collected = 0

    # Estimate total fighters for progress bar
    for letter in string.ascii_lowercase:
        url = f"{base_url}{letter}&page=all"
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            fighter_table = soup.find('table', class_='b-statistics__table')
            if fighter_table:
                rows = fighter_table.find('tbody').find_all('tr', class_='b-statistics__table-row')
                total_fighters_estimate += len(rows)
        except requests.RequestException:
            pass

    if total_fighters_estimate == 0:
        total_fighters_estimate = len(string.ascii_lowercase) * 10  # fallback guess

    # Actual scraping with progress update
    for letter in string.ascii_lowercase:
        url = f"{base_url}{letter}&page=all"
        retries = 3
        for i in range(retries):
            try:
                response = requests.get(url)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                st.warning(f"Error fetching {url}: {e}. Retrying ({i+1}/{retries})...")
                time.sleep(2)
        else:
            st.error(f"Failed to fetch {url} after {retries} retries.")
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
                fighters_collected += 1
                progress_fighters.progress(min(fighters_collected / total_fighters_estimate, 1.0))
                status_fighters.text(f"Fighter links collected: {fighters_collected} / {total_fighters_estimate}")

    return list(set(all_links))

# -------------------------------
def get_fight_links(fighter_url):
    try:
        res = requests.get(fighter_url)
        res.raise_for_status()
    except Exception as e:
        st.warning(f"Failed to get fight links for {fighter_url}: {e}")
        return [], pd.DataFrame()

    soup = BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table', class_='b-fight-details__table')

    if not table:
        st.warning(f"No fights table found for {fighter_url}")
        return [], pd.DataFrame()

    fight_links = []
    opponent_names = []
    results = []
    methods = []

    for row in table.find('tbody').find_all('tr'):
        columns = row.find_all('td')
        if len(columns) < 7:
            continue
        result = columns[0].text.strip().lower()
        opponent = columns[1].text.strip()
        method = columns[6].text.strip()
        link_tag = columns[6].find('a')
        if link_tag and 'href' in link_tag.attrs:
            link = link_tag['href']
        else:
            link = None

        if link is None:
            continue

        fight_links.append(link)
        results.append(result)
        opponent_names.append(opponent)
        methods.append(method)

    fighter_name_tag = soup.find('span', class_='b-content__title-highlight')
    fighter_name = fighter_name_tag.text.strip() if fighter_name_tag else "Unknown"

    df = pd.DataFrame({
        'fighter_name': [fighter_name]*len(fight_links),
        'opponent_name': opponent_names,
        'result': results,
        'method_main': methods,
        'fight_link': fight_links
    })

    return fight_links, df

# -------------------------------
def parse_fight_details(fight_link, fighter_name, opponent_name):
    try:
        res = requests.get(fight_link)
        res.raise_for_status()
    except Exception as e:
        st.warning(f"Failed to parse fight details for {fight_link}: {e}")
        return None

    soup = BeautifulSoup(res.text, 'html.parser')

    details = {
        'fight_link': fight_link,
        'TOT_fighter_SigStr_landed': 0,
        'TOT_opponent_SigStr_landed': 0,
        'TimeFormat': '',
        'Details': ''
    }

    tables = soup.find_all('table')
    if len(tables) < 2:
        return details

    # Parse Significant Strikes table
    for table in tables:
        if 'Significant Strikes' in table.text:
            rows = table.find_all('tr')
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                fighter_cell = cells[0].text.strip()
                opponent_cell = cells[1].text.strip()

                try:
                    fighter_sig = int(fighter_cell.split('of')[0].strip())
                    opponent_sig = int(opponent_cell.split('of')[0].strip())
                    details['TOT_fighter_SigStr_landed'] = fighter_sig
                    details['TOT_opponent_SigStr_landed'] = opponent_sig
                    break
                except Exception:
                    continue

    fight_details = soup.find('p', class_='b-fight-details__text')
    if fight_details:
        details['Details'] = fight_details.text.strip()

    info_section = soup.find_all('i', class_='b-fight-details__text-item')
    for i in info_section:
        if 'Format' in i.text:
            details['TimeFormat'] = i.text.strip()

    return details

# -------------------------------
def transform_columns(df):
    df['TOT_fighter_SigStr_landed'] = pd.to_numeric(df.get('TOT_fighter_SigStr_landed', 0), errors='coerce').fillna(0)
    df['TOT_opponent_SigStr_landed'] = pd.to_numeric(df.get('TOT_opponent_SigStr_landed', 0), errors='coerce').fillna(0)
    return df

# -------------------------------
def should_refresh():
    now = datetime.now()
    is_tuesday = now.weekday() == 1
    is_morning = now.hour < 12

    if not os.path.exists(LEADERBOARD_FILE):
        return True

    last_mod_time = datetime.fromtimestamp(os.path.getmtime(LEADERBOARD_FILE))
    return is_tuesday and is_morning and last_mod_time.date() < now.date()

# -------------------------------
def build_leaderboard(limit=10):
    all_links = get_all_fighter_links()
    all_fighters_data = []

    # Limit the number of fighters processed for testing
    all_links = all_links[:limit]

    progress_processed = st.progress(0)
    status_processed = st.empty()

    total_fighters = len(all_links)
    fighters_processed = 0

    for fighter_url in all_links:
        try:
            fight_links, main_df = get_fight_links(fighter_url)
            if main_df.empty:
                st.warning(f"No fights data for fighter URL: {fighter_url}")
                continue

            details = []
            for f_link in fight_links:
                # Use fighter and opponent names from main_df for this fight
                fighter_name = main_df.loc[main_df['fight_link'] == f_link, 'fighter_name'].values
                opponent_name = main_df.loc[main_df['fight_link'] == f_link, 'opponent_name'].values
                if len(fighter_name) == 0 or len(opponent_name) == 0:
                    continue

                d = parse_fight_details(f_link, fighter_name[0], opponent_name[0])
                if d is not None:
                    details.append(d)

            if not details:
                st.warning(f"No fight details parsed for fighter URL: {fighter_url}")
                continue

            adv_df = pd.DataFrame(details)
            combined = pd.merge(main_df, adv_df, on='fight_link', how='left')
            combined = transform_columns(combined)
            combined['rax_earned'] = combined.apply(calculate_rax, axis=1)

            total_rax = combined['rax_earned'].sum()
            all_fighters_data.append({'fighter_name': main_df['fighter_name'].iloc[0], 'total_rax': total_rax})

            fighters_processed += 1
            progress_processed.progress(fighters_processed / total_fighters)
            status_processed.text(f"Fighters fully processed: {fighters_processed} / {total_fighters}")

        except Exception as e:
            st.warning(f"Error processing fighter {fighter_url}: {e}")
            continue

    if not all_fighters_data:
        st.error("No fighter data collected!")
        return pd.DataFrame(columns=['Rank', 'fighter_name', 'total_rax'])

    leaderboard = pd.DataFrame(all_fighters_data)
    if 'total_rax' not in leaderboard.columns:
        st.error("Missing 'total_rax' column in leaderboard data!")
        return pd.DataFrame(columns=['Rank', 'fighter_name', 'total_rax'])

    leaderboard = leaderboard.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    leaderboard.insert(0, "Rank", leaderboard.index + 1)
    return leaderboard

# -------------------------------
def main():
    st.set_page_config(page_title="UFC RAX Leaderboard", layout="wide")
    st.title("🏆 UFC RAX Leaderboard")

    if should_refresh():
        st.info("Refreshing leaderboard... This may take a few minutes.")
        leaderboard_df = build_leader
