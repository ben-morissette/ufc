import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# Constants
CACHE_FILE = 'ufc_rax_leaderboard.csv'
FIGHTER_LIMIT = 10  # Limit fighters in test mode
RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

# Utility Functions
def get_last_tuesday():
    today = datetime.today()
    offset = (today.weekday() - 1) % 7
    return (today - timedelta(days=offset)).date()

def cache_is_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    last_modified = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE)).date()
    return last_modified == get_last_tuesday()

# Scraping Functions
def get_fighter_urls(limit=None):
    url = 'http://ufcstats.com/statistics/fighters?char=a&page=all'
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    links = ['http://ufcstats.com' + a['href'] for a in table.find_all('a', href=True) if '/fighter-details/' in a['href']]
    return links[:limit] if limit else links

def get_fight_data(fighter_url):
    r = requests.get(fighter_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    name_tag = soup.find('span', class_='b-content__title-highlight')
    if not name_tag:
        return None

    name = name_tag.text.strip()
    fight_rows = soup.find_all('tr', class_='b-fight-details__table-row')[1:]
    wins = 0
    losses = 0

    for row in fight_rows:
        result = row.find_all('td')[0].text.strip()
        if result == 'win':
            wins += 1
        elif result == 'loss':
            losses += 1

    return {'Fighter Name': name, 'Wins': wins, 'Losses': losses, 'Fight Count': wins + losses}

def calculate_rax(fighter):
    return fighter['Wins'] * 100 + fighter['Fight Count'] * 10

def generate_leaderboard(limit=FIGHTER_LIMIT):
    fighter_urls = get_fighter_urls(limit=limit)
    data = []

    for url in fighter_urls:
        try:
            fighter = get_fight_data(url)
            if fighter:
                fighter['Base Rax'] = calculate_rax(fighter)
                data.append(fighter)
            time.sleep(0.2)
        except Exception as e:
            print(f"Error processing {url}: {e}")

    df = pd.DataFrame(data)
    df = df.sort_values(by='Base Rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', df.index + 1)
    df['Rarity'] = 'Uncommon'  # default value
    return df

def cache_and_load_leaderboard():
    if cache_is_fresh():
        return pd.read_csv(CACHE_FILE)
    df = generate_leaderboard()
    df.to_csv(CACHE_FILE, index=False)
    return df

# UI Rendering
def render_table_with_dropdowns(df):
    st.markdown("""
    <style>
    .custom-table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    .custom-table th, .custom-table td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: center;
    }
    .custom-table th { background-color: #f5f5f5; font-weight: 600; }
    .custom-table tr:hover { background-color: #f1f1f1; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<table class="custom-table">', unsafe_allow_html=True)
    st.markdown("""
        <tr>
            <th>#</th>
            <th>Fighter</th>
            <th>Base Rax</th>
            <th>Rarity</th>
            <th>Total Rax</th>
        </tr>
    """, unsafe_allow_html=True)

    selected_rarities = []
    for idx, row in df.iterrows():
        rarity_key = f"rarity_{idx}"
        selected_rarity = st.selectbox(
            "", list(RARITY_MULTIPLIERS.keys()),
            index=list(RARITY_MULTIPLIERS.keys()).index(row.get('Rarity', 'Uncommon')),
            key=rarity_key, label_visibility="collapsed"
        )
        selected_rarities.append(selected_rarity)

        total = round(row["Base Rax"] * RARITY_MULTIPLIERS[selected_rarity], 1)

        st.markdown(f"""
        <tr>
            <td>{row['Rank']}</td>
            <td>{row['Fighter Name']}</td>
            <td>{row['Base Rax']}</td>
            <td>{selected_rarity}</td>
            <td>{total}</td>
        </tr>
        """, unsafe_allow_html=True)

    st.markdown("</table>", unsafe_allow_html=True)
    return selected_rarities

# Main App
def main():
    st.set_page_config(layout="wide", page_title="UFC RAX Leaderboard")
    st.title("🏆 UFC Fighter RAX Leaderboard")

    leaderboard_df = cache_and_load_leaderboard()
    selected_rarities = render_table_with_dropdowns(leaderboard_df)

    # Recalculate RAX based on user-selected rarity
    updated_df = leaderboard_df.copy()
    updated_df['Rarity'] = selected_rarities
    updated_df['Total Rax'] = updated_df.apply(
        lambda row: round(row['Base Rax'] * RARITY_MULTIPLIERS[row['Rarity']], 1), axis=1
    )
    updated_df = updated_df.sort_values(by="Total Rax", ascending=False).reset_index(drop=True)
    updated_df.insert(0, 'Rank', updated_df.index + 1)

    st.markdown("---")
    st.markdown("### 📊 Final Leaderboard")
    st.dataframe(updated_df[['Rank', 'Fighter Name', 'Total Rax', 'Rarity', 'Fight Count']], use_container_width=True)

if __name__ == "__main__":
    main()
