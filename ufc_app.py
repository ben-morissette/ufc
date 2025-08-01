import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import time

CACHE_FILE = 'ufc_rax_leaderboard.csv'
FIGHTER_LIMIT = 10
RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

def get_last_tuesday():
    today = datetime.today()
    offset = (today.weekday() - 1) % 7
    return (today - timedelta(days=offset)).date()

def cache_is_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    return datetime.fromtimestamp(os.path.getmtime(CACHE_FILE)).date() == get_last_tuesday()

def get_fighter_urls(limit=FIGHTER_LIMIT):
    url = "http://ufcstats.com/statistics/fighters"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    rows = soup.select('table.b-statistics__table tbody tr.b-statistics__table-row')
    urls = []
    for row in rows[:limit]:
        a = row.select_one('td a.b-link_style_black')
        if a and a.has_attr('href'):
            urls.append(a['href'])
    return urls

def get_fight_data(u):
    resp = requests.get(u)
    squad = BeautifulSoup(resp.text, 'html.parser')
    name_el = squad.select_one('span.b-content__title-highlight')
    if not name_el:
        return None
    name = name_el.text.strip()
    fights = squad.select('table.b-fight-details__table_type_event-details tr.b-fight-details__table-row__hover')
    total = 0
    for tr in fights:
        cols = tr.select('td')
        result = cols[0].get_text(strip=True).lower()
        method = cols[7].get_text(strip=True)
        # Simplified RAX calculation example:
        if result == 'win':
            if method == 'KO/TKO':
                total += 100
            elif 'submiss' in method.lower():
                total += 90
            elif 'decision' in method.lower():
                total += 80
            else:
                total += 70
        elif result == 'loss':
            total += 25
    return {"Fighter Name": name, "Base Rax": total}

def generate_leaderboard():
    fighters = []
    for u in get_fighter_urls():
        try:
            f = get_fight_data(u)
            if f:
                fighters.append(f)
            time.sleep(0.2)  # be polite to server
        except:
            continue
    df = pd.DataFrame(fighters)
    df = df.sort_values(by='Base Rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', df.index + 1)

    # Add all rarity RAX columns precomputed
    for rarity, mult in RARITY_MULTIPLIERS.items():
        df[f'Rax_{rarity}'] = (df['Base Rax'] * mult).round(1)

    # Default rarity column
    df['Rarity'] = 'Uncommon'
    return df

def cache_and_load():
    if cache_is_fresh():
        df = pd.read_csv(CACHE_FILE)
        # Make sure 'Rank' is correct in case index shifted
        if 'Rank' in df.columns:
            df.drop(columns=['Rank'], inplace=True)
        df.insert(0, 'Rank', df.index + 1)
        # Ensure Rarity column exists
        if 'Rarity' not in df.columns:
            df['Rarity'] = 'Uncommon'
        return df
    else:
        df = generate_leaderboard()
        df.to_csv(CACHE_FILE, index=False)
        return df

def render_editable_rows(df):
    st.markdown("""
    <style>
      .row-box {
        border: 1px solid #ccc;
        border-radius: 6px;
        padding: 10px 15px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        background-color: #fafafa;
      }
      .col-rank { flex: 0.5; font-weight: 700; }
      .col-name { flex: 3; font-weight: 600; font-size: 18px; }
      .col-rarity, .col-rax { flex: 1.5; text-align: center; }
      select {
        font-size: 16px;
        padding: 4px 6px;
        border-radius: 4px;
      }
    </style>
    """, unsafe_allow_html=True)
    
    rarities = []
    for idx, row in df.iterrows():
        cols = st.columns([0.5, 3, 1.5, 1.5])
        with cols[0]:
            st.markdown(f"<div class='row-box'>{row['Rank']}</div>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"<div class='row-box'>{row['Fighter Name']}</div>", unsafe_allow_html=True)
        with cols[2]:
            rarity = st.selectbox("", list(RARITY_MULTIPLIERS.keys()),
                                  index=list(RARITY_MULTIPLIERS.keys()).index(row['Rarity']),
                                  key=f"rarity_{idx}", label_visibility="collapsed")
        with cols[3]:
            # Show precomputed RAX from selected rarity column
            rax_value = row[f"Rax_{rarity}"]
            st.markdown(f"<div class='row-box'>{rax_value}</div>", unsafe_allow_html=True)
        rarities.append(rarity)
    return rarities

def main():
    st.set_page_config(layout="wide", page_title="UFC RAX Leaderboard")
    st.title("🏆 UFC Fighter RAX Leaderboard")

    df = cache_and_load()

    if "rarities" not in st.session_state:
        st.session_state.rarities = list(df['Rarity'])

    df['Rarity'] = st.session_state.rarities

    # Sort by selected rarity RAX values
    df['Total Rax'] = [row[f"Rax_{rar}"] for row, rar in zip(df.itertuples(index=False), df['Rarity'])]
    df = df.sort_values(by='Total Rax', ascending=False).reset_index(drop=True)
    if 'Rank' in df.columns:
        df.drop(columns=['Rank'], inplace=True)
    df.insert(0, 'Rank', df.index + 1)

    st.markdown("### Final Leaderboard (Sorted by Adjusted RAX)")
    st.dataframe(df[['Rank', 'Fighter Name', 'Total Rax', 'Rarity']], use_container_width=True)

    st.markdown("---")
    st.markdown("### Edit Rarity per Fighter Below")

    new_rarities = render_editable_rows(df)

    if new_rarities != st.session_state.rarities:
        st.session_state.rarities = new_rarities
        st.experimental_rerun()

if __name__ == "__main__":
    main()
