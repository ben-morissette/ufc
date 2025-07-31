import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import string
import time
from tqdm import tqdm
import numpy as np
import os
from datetime import datetime
from difflib import get_close_matches

LEADERBOARD_FILE = "rax_leaderboard.csv"
TEST_MODE = True  # Set to False in production

# -------------------------------
# RAX calculation logic
# -------------------------------
def calculate_rax(row):
    rax = 0
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

    if 'TOT_fighter_SigStr_landed' in row.index and 'TOT_opponent_SigStr_landed' in row.index:
        diff = row['TOT_fighter_SigStr_landed'] - row['TOT_opponent_SigStr_landed']
        if diff > 0:
            rax += diff

    if 'TimeFormat' in row.index and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row.index and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# -------------------------------
def get_fighter_url_by_name(name):
    url = f"http://ufcstats.com/statistics/fighters?char={name[0].lower()}&page=all"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    if not table:
        raise ValueError("No fighter statistics table found")

    fighter_urls = {}
    rows = table.find('tbody').find_all('tr')
    for row in rows:
        fighter_name = row.find_all('td')[0].text.strip()
        fighter_link = row.find('a')['href']
        fighter_urls[fighter_name] = fighter_link

    match = get_close_matches(name, fighter_urls.keys(), n=1, cutoff=0.6)
    if match:
        return fighter_urls[match[0]]
    else:
        raise ValueError("Fighter not found")

# -------------------------------
def get_fight_links(fighter_url):
    res = requests.get(fighter_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table', class_='b-fight-details__table')
    if not table:
        return [], pd.DataFrame()

    fight_links = []
    fighter_names = []
    opponent_names = []
    results = []
    methods = []

    for row in table.find('tbody').find_all('tr'):
        columns = row.find_all('td')
        result = columns[0].text.strip().lower()
        opponent = columns[1].text.strip()
        method = columns[6].text.strip()
        link_tag = columns[6].find('a')
        link = link_tag['href'] if link_tag else ''

        fight_links.append(link)
        results.append(result)
        opponent_names.append(opponent)
        methods.append(method)

    fighter_name_tag = soup.find('span', class_='b-content__title-highlight')
    fighter_name = fighter_name_tag.text.strip() if fighter_name_tag else ''

    df = pd.DataFrame({
        'fighter_name': fighter_name,
        'opponent_name': opponent_names,
        'result': results,
        'method_main': methods,
        'fight_link': fight_links
    })

    return fight_links, df

# -------------------------------
def parse_fight_details(fight_link, fighter_name, opponent_name):
    res = requests.get(fight_link)
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
                except Exception:
                    continue

                details['TOT_fighter_SigStr_landed'] = fighter_sig
                details['TOT_opponent_SigStr_landed'] = opponent_sig
                break

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
    is_tuesday = now.weekday() == 1  # Monday=0, Tuesday=1 ...
    is_morning = now.hour < 12

    if not os.path.exists(LEADERBOARD_FILE):
        return True

    last_mod_time = datetime.fromtimestamp(os.path.getmtime(LEADERBOARD_FILE))
    return is_tuesday and is_morning and last_mod_time.date() < now.date()

# -------------------------------
def get_all_fighter_links():
    all_links = []
    for char in string.ascii_lowercase:
        url = f"http://ufcstats.com/statistics/fighters?char={char}&page=all"
        res = requests.get(url)
        if res.status_code != 200:
            print(f"Warning: Failed to fetch page for char '{char}', status code {res.status_code}")
            continue

        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table', class_='b-statistics__table')
        if not table:
            print(f"Warning: No statistics table found for char '{char}'")
            continue

        rows = table.find('tbody').find_all('tr')
        for row in rows:
            anchor = row.find('a')
            if anchor and anchor.has_attr('href'):
                link = anchor['href']
                all_links.append(link)
            else:
                print(f"Warning: No anchor with href found in row: {row}")

        time.sleep(0.5)  # polite delay between requests

    return all_links

# -------------------------------
def build_leaderboard():
    all_links = get_all_fighter_links()
    if TEST_MODE:
        all_links = all_links[:10]

    all_fighters_data = []

    for fighter_url in tqdm(all_links, desc="Processing fighters"):
        try:
            fight_links, main_df = get_fight_links(fighter_url)
            if main_df.empty:
                continue

            details = [parse_fight_details(f, main_df.loc[main_df['fight_link'] == f]['fighter_name'].values[0],
                                           main_df.loc[main_df['fight_link'] == f]['opponent_name'].values[0])
                       for f in fight_links]

            adv_df = pd.DataFrame(details)
            combined = pd.merge(main_df, adv_df, on='fight_link', how='left')
            combined = transform_columns(combined)
            combined['rax_earned'] = combined.apply(calculate_rax, axis=1)
            total_rax = combined['rax_earned'].sum()
            all_fighters_data.append({'fighter_name': main_df['fighter_name'].iloc[0], 'total_rax': total_rax})
        except Exception as e:
            print(f"Error processing fighter URL {fighter_url}: {e}")
            continue

    leaderboard = pd.DataFrame(all_fighters_data)
    leaderboard = leaderboard.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    leaderboard.insert(0, "Rank", leaderboard.index + 1)
    return leaderboard

# -------------------------------
def main():
    st.set_page_config(page_title="UFC RAX Leaderboard", layout="wide")
    st.title("🏆 UFC RAX Leaderboard")

    if not os.path.exists(LEADERBOARD_FILE) or should_refresh():
        st.info("Refreshing leaderboard... This may take a few minutes.")
        leaderboard_df = build_leaderboard()
        leaderboard_df.to_csv(LEADERBOARD_FILE, index=False)
    else:
        leaderboard_df = pd.read_csv(LEADERBOARD_FILE)

    search_name = st.text_input("🔍 Search for a fighter:", "").strip().lower()
    if search_name:
        filtered = leaderboard_df[leaderboard_df['fighter_name'].str.lower().str.contains(search_name)]
    else:
        filtered = leaderboard_df

    st.dataframe(filtered, use_container_width=True)

if __name__ == "__main__":
    main()
