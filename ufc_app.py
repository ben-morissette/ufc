import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import string
import time
from tqdm import tqdm

# --- Scrape all fighter links, limited to 10 if test_mode is True ---
def get_all_fighter_links(test_mode=False):
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="
    
    for letter in tqdm(string.ascii_lowercase, desc="Scraping fighter links"):
        url = f"{base_url}{letter}&page=all"
        retries = 3
        for i in range(retries):
            try:
                response = requests.get(url)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                print(f"Error fetching {url}: {e}. Retrying ({i+1}/{retries})...")
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

        if test_mode and len(all_links) >= 10:
            break

    unique_links = list(set(all_links))
    if test_mode:
        unique_links = unique_links[:10]

    return unique_links


# --- Get all fight links and main fight info for a fighter ---
def get_fight_links(fighter_url):
    retries = 3
    for i in range(retries):
        try:
            response = requests.get(fighter_url)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching fighter page {fighter_url}: {e}. Retrying ({i+1}/{retries})...")
            time.sleep(2)
    else:
        raise Exception(f"Failed to fetch fighter page {fighter_url}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract fighter name (usually in h2 or title)
    fighter_name_tag = soup.find('span', class_='b-content__title-highlight')
    fighter_name = fighter_name_tag.text.strip() if fighter_name_tag else "Unknown"

    fight_table = soup.find('table', class_='b-fight-details__table')
    if not fight_table:
        return [], pd.DataFrame()

    rows = fight_table.find_all('tr', class_='b-fight-details__table-row')

    fight_links = []
    fight_data = []

    for row in rows:
        # fight date, opponent, result, fight link
        cells = row.find_all('td')
        if len(cells) < 5:
            continue

        fight_date = cells[0].text.strip()
        opponent_tag = cells[1].find('a')
        opponent_name = opponent_tag.text.strip() if opponent_tag else "Unknown"
        result = cells[2].text.strip()
        fight_link_tag = cells[1].find('a')
        fight_link = fight_link_tag['href'] if fight_link_tag else None
        if fight_link:
            fight_links.append(fight_link)

        fight_data.append({
            'fight_date': fight_date,
            'fighter_name': fighter_name,
            'opponent_name': opponent_name,
            'result': result,
            'fight_link': fight_link
        })

    main_fights_df = pd.DataFrame(fight_data)

    return fight_links, main_fights_df


# --- Parse detailed fight data from fight link ---
def parse_fight_details(fight_link, fighter_name, opponent_name):
    retries = 3
    for i in range(retries):
        try:
            response = requests.get(fight_link)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching fight details {fight_link}: {e}. Retrying ({i+1}/{retries})...")
            time.sleep(2)
    else:
        raise Exception(f"Failed to fetch fight details {fight_link}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Example: extract fight stats from stats tables on page
    stats = {}

    # Find stats table
    stat_tables = soup.find_all('table', class_='b-fight-details__table')
    if not stat_tables:
        return stats

    # For example, parse strikes or significant strikes
    for table in stat_tables:
        header = table.find_previous('h3')
        if header:
            header_text = header.text.strip().lower()
        else:
            header_text = ""

        # Parse rows to get relevant stats for the fighter
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                stat_name = cols[0].text.strip().lower()
                fighter_stat = cols[1].text.strip()
                opponent_stat = cols[2].text.strip()

                # Store only fighter stats keyed by stat name
                stats[f"fighter_{stat_name}"] = fighter_stat
                stats[f"opponent_{stat_name}"] = opponent_stat

    # Add fight_link for merging later
    stats['fight_link'] = fight_link
    stats['fighter_name'] = fighter_name
    stats['opponent_name'] = opponent_name

    return stats


# --- Transform columns as needed ---
def transform_columns(df):
    # Example: convert some stats to numeric, clean up %
    for col in df.columns:
        if df[col].dtype == object:
            # Remove % and convert to float if possible
            df[col] = df[col].str.replace('%', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# --- Calculate RAX points for a fight ---
def calculate_rax(row):
    # Simplified example: +10 for win, +5 for significant strikes landed (if available)
    rax = 0
    if 'result' in row and row['result'].lower() == 'win':
        rax += 10
    if 'fighter_sig. str.' in row and not pd.isna(row['fighter_sig. str.']):
        rax += row['fighter_sig. str.'] * 0.1  # Example weighting
    return rax


# --- Build leaderboard with progress bars ---
def build_leaderboard(test_mode=False, progress_bar_fighters=None, progress_bar_fights=None):
    all_fighter_links = get_all_fighter_links(test_mode=test_mode)
    all_fighters_data = []

    total_fighters = len(all_fighter_links)
    for i, fighter_url in enumerate(tqdm(all_fighter_links, desc="Processing fighters")):
        if progress_bar_fighters:
            progress_bar_fighters.progress(min((i + 1) / total_fighters, 1.0))

        try:
            fight_links, main_fights_df = get_fight_links(fighter_url)

            fighter_fight_details = []
            total_fights = len(fight_links)

            for j, fl in enumerate(fight_links):
                if progress_bar_fights:
                    progress_bar_fights.progress(min((j + 1) / total_fights, 1.0))

                row_index = main_fights_df.index[main_fights_df['fight_link'] == fl].tolist()
                if not row_index:
                    continue
                row = main_fights_df.loc[row_index[0]]
                main_fighter_name = row['fighter_name']
                opp_name = row['opponent_name']

                details = parse_fight_details(fl, main_fighter_name, opp_name)
                fighter_fight_details.append(details)

            if not fighter_fight_details:
                continue

            advanced_df = pd.DataFrame(fighter_fight_details)
            combined_df = pd.merge(main_fights_df, advanced_df, on='fight_link', how='left')
            combined_df = transform_columns(combined_df)
            combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)
            total_rax = combined_df['rax_earned'].sum()

            all_fighters_data.append({'fighter_name': main_fighter_name, 'total_rax': total_rax})

        except Exception as e:
            print(f"Error processing fighter {fighter_url}: {e}")
            continue

    leaderboard = pd.DataFrame(all_fighters_data)
    if not leaderboard.empty and 'total_rax' in leaderboard.columns:
        leaderboard = leaderboard.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    else:
        st.warning("No fighter data was scraped. Please check your scraping functions or test mode settings.")
        leaderboard = pd.DataFrame(columns=['fighter_name', 'total_rax'])

    return leaderboard


# --- Streamlit app main ---

def main():
    st.title("UFC Fighter RAX Leaderboard")

    test_mode = st.checkbox("Test Mode (Only 10 Fighters)", value=True)

    fighter_link_progress = st.progress(0)
    fight_processing_progress = st.progress(0)

    leaderboard_df = build_leaderboard(
        test_mode=test_mode,
        progress_bar_fighters=fighter_link_progress,
        progress_bar_fights=fight_processing_progress
    )

    st.dataframe(leaderboard_df)


if __name__ == "__main__":
    main()
