import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import string
import time
from datetime import datetime
from difflib import get_close_matches

TEST_MODE = False  # Set True to limit scraping/processing to 10 fighters for quick tests
LEADERBOARD_FILE = "rax_leaderboard.csv"

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

# -------------------------------
def transform_columns(df):
    df['TOT_fighter_SigStr_landed'] = pd.to_numeric(df.get('TOT_fighter_SigStr_landed', 0), errors='coerce').fillna(0)
    df['TOT_opponent_SigStr_landed'] = pd.to_numeric(df.get('TOT_opponent_SigStr_landed', 0), errors='coerce').fillna(0)
    return df

# -------------------------------
def should_refresh():
    import os
    now = datetime.now()
    is_tuesday = now.weekday() == 1
    is_morning = now.hour < 12

    if not os.path.exists(LEADERBOARD_FILE):
        return True

    last_mod_time = datetime.fromtimestamp(os.path.getmtime(LEADERBOARD_FILE))
    return is_tuesday and is_morning and last_mod_time.date() < now.date()

# -------------------------------
def get_all_fighter_links(progress_bar=None):
    import requests
    from bs4 import BeautifulSoup
    import string
    import time

    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="

    letters = list(string.ascii_lowercase)
    if TEST_MODE:
        letters = letters[:3]  # Just a few letters for test mode

    for i, letter in enumerate(letters):
        url = f"{base_url}{letter}&page=all"
        retries = 3
        for attempt in range(retries):
            try:
                response = requests.get(url)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                print(f"Error fetching {url}: {e}. Retrying ({attempt+1}/{retries})...")
                time.sleep(2)
        else:
            print(f"Failed to fetch {url} after {retries} retries.")
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

        if progress_bar:
            progress_bar.progress((i + 1) / len(letters))

    return list(set(all_links))

# -------------------------------
def build_leaderboard(progress_bar_fighters=None, progress_bar_fights=None):
    all_links = get_all_fighter_links(progress_bar=None)  # progress bar handled outside

    if TEST_MODE:
        all_links = all_links[:10]

    all_fighters_data = []
    total_fighters = len(all_links)

    for i, fighter_url in enumerate(all_links):
        if progress_bar_fighters:
            progress_bar_fighters.progress((i + 1) / total_fighters, text=f"Processing fighter {i+1} / {total_fighters}")

        try:
            fight_links, main_df = get_fight_links(fighter_url)
            total_fights = len(fight_links)

            fighter_fight_details = []

            for j, fl in enumerate(fight_links):
                if progress_bar_fights:
                    progress_bar_fights.progress((j + 1) / total_fights, text=f"Processing fight {j+1} / {total_fights}")

                row_index = main_df.index[main_df['fight_link'] == fl].tolist()
                if not row_index:
                    continue
                row = main_df.loc[row_index[0]]

                main_fighter_name = row['fighter_name']
                opp_name = row['opponent_name']

                details = parse_fight_details(fl, main_fighter_name, opp_name)
                fighter_fight_details.append(details)

            if not fighter_fight_details:
                continue

            adv_df = pd.DataFrame(fighter_fight_details)
            combined = pd.merge(main_df, adv_df, on='fight_link', how='left')
            combined = transform_columns(combined)
            combined['rax_earned'] = combined.apply(calculate_rax, axis=1)

            total_rax = combined['rax_earned'].sum()
            all_fighters_data.append({'fighter_name': main_fighter_name, 'total_rax': total_rax})
        except Exception as e:
            print(f"Error processing fighter {fighter_url}: {e}")
            continue

    if not all_fighters_data:
        st.error("No fighter data was scraped. Please check your scraping functions or test mode settings.")
        return pd.DataFrame(columns=['fighter_name', 'total_rax'])

    leaderboard = pd.DataFrame(all_fighters_data)
    print("all_fighters_data sample:", all_fighters_data[:3])  # Debug

    leaderboard = leaderboard.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    leaderboard.insert(0, "Rank", leaderboard.index + 1)
    return leaderboard


# -------------------------------
def main():
    st.set_page_config(page_title="UFC RAX Leaderboard", layout="wide")
    st.title("🏆 UFC RAX Leaderboard")

    # Add a toggle for test mode in UI for convenience
    global TEST_MODE
    TEST_MODE = st.checkbox("Enable Test Mode (limit to 10 fighters)", value=TEST_MODE)

    # Progress bars placeholders
    fighter_link_progress = st.progress(0, text="Starting fighter links scraping...")
    fight_processing_progress = st.progress(0, text="Waiting to process fights...")

    refresh_needed = should_refresh() or TEST_MODE

    if refresh_needed:
        st.info("Refreshing leaderboard... This may take a few minutes.")

        # Update fighter links progress bar during scraping
        all_links = get_all_fighter_links(progress_bar=fighter_link_progress)
        if TEST_MODE:
            all_links = all_links[:10]

        # Process fighters and fights with progress bars
        leaderboard_df = build_leaderboard(progress_bar_fighters=fighter_link_progress, progress_bar_fights=fight_processing_progress)
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
