import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import string
import time
from tqdm import tqdm
from datetime import datetime
from difflib import get_close_matches

# RAX calculation logic (your original)
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

    if 'TOT_fighter_SigStr_landed' in row and 'TOT_opponent_SigStr_landed' in row:
        diff = row['TOT_fighter_SigStr_landed'] - row['TOT_opponent_SigStr_landed']
        if diff > 0:
            rax += diff

    if 'TimeFormat' in row and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# Get all fighter links for first 10 fighters only
def get_all_fighter_links():
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="
    
    for letter in string.ascii_lowercase:
        url = f"{base_url}{letter}&page=all"
        try:
            response = requests.get(url)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        fighter_table = soup.find('table', class_='b-statistics__table')
        if not fighter_table:
            continue
        
        fighter_rows = fighter_table.find('tbody').find_all('tr', class_='b-statistics__table-row')
        for row in fighter_rows:
            link_tag = row.find('a', class_='b-link_style_black')
            if link_tag and 'href' in link_tag.attrs:
                all_links.append(link_tag['href'])
            if len(all_links) >= 10:
                return all_links
    return all_links

def get_fight_links(fighter_url):
    res = requests.get(fighter_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table', class_='b-fight-details__table')

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
        link = columns[6].find('a')['href']

        fight_links.append(link)
        results.append(result)
        opponent_names.append(opponent)
        methods.append(method)

    fighter_name = soup.find('span', class_='b-content__title-highlight').text.strip()

    df = pd.DataFrame({
        'fighter_name': fighter_name,
        'opponent_name': opponent_names,
        'result': results,
        'method_main': methods,
        'fight_link': fight_links
    })

    return fight_links, df

def parse_fight_details(fight_link):
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
                except:
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

def transform_columns(df):
    df['TOT_fighter_SigStr_landed'] = pd.to_numeric(df.get('TOT_fighter_SigStr_landed', 0), errors='coerce').fillna(0)
    df['TOT_opponent_SigStr_landed'] = pd.to_numeric(df.get('TOT_opponent_SigStr_landed', 0), errors='coerce').fillna(0)
    return df

def main():
    st.set_page_config(page_title="UFC RAX Leaderboard (First 10 Fighters)", layout="wide")
    st.title("🏆 UFC RAX Leaderboard (First 10 Fighters)")

    fighter_links = get_all_fighter_links()
    total_fighters = len(fighter_links)
    st.write(f"Total Fighters to Process: {total_fighters}")

    all_fights_data = []
    completed_fighters = 0
    rax_fights_count = 0

    # Progress bar for fighters
    progress_fighters = st.progress(0)
    # Text to show fighters processed
    fighters_text = st.empty()

    # Progress bar for fights with full RAX data
    progress_rax_fights = st.progress(0)
    rax_text = st.empty()

    for i, fighter_url in enumerate(fighter_links):
        try:
            fight_links, main_df = get_fight_links(fighter_url)
            details = [parse_fight_details(f) for f in fight_links]
            adv_df = pd.DataFrame(details)
            combined = pd.merge(main_df, adv_df, on='fight_link', how='left')
            combined = transform_columns(combined)
            combined['rax_earned'] = combined.apply(calculate_rax, axis=1)
            all_fights_data.append(combined)

            # Update counters
            completed_fighters += 1
            # Count fights with complete RAX info (sig strikes > 0 and rax > 0)
            rax_fights_count += combined[(combined['TOT_fighter_SigStr_landed'] > 0) & (combined['rax_earned'] > 0)].shape[0]

        except Exception as e:
            print(f"Error processing {fighter_url}: {e}")

        # Update progress bars and texts
        progress_fighters.progress((i + 1) / total_fighters)
        fighters_text.text(f"Fighters processed: {i + 1} / {total_fighters}")
        progress_rax_fights.progress(min(1.0, rax_fights_count / 50))  # Assuming 50 as a visible max scale
        rax_text.text(f"Fights with full RAX data: {rax_fights_count}")

    # Concatenate all fight dataframes
    if all_fights_data:
        final_df = pd.concat(all_fights_data, ignore_index=True)
    else:
        final_df = pd.DataFrame()

    st.write("### All fights with RAX calculated:")
    st.dataframe(final_df)

if __name__ == "__main__":
    main()
