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
        if result == 'win':
            total += 100
        elif result == 'loss':
            total += 25
    return {"Fighter Name": name, "Base Rax": total}

def generate_leaderboard():
    fighters = []
    for u in get_fighter_urls():
        try:
            f = get_fight_data(u)
            if f:
                fighters.append({**f, "Rarity": "Uncommon"})
            time.sleep(0.2)
        except:
            continue
    df = pd.DataFrame(fighters)
    df = df.sort_values(by='Base Rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', df.index + 1)
    return df

def cache_and_load():
    if cache_is_fresh():
        df = pd.read_csv(CACHE_FILE)
        if 'Rank' in df.columns:
            df.drop(columns=['Rank'], inplace=True)
        if 'Total Rax' in df.columns and 'Base Rax' not in df.columns:
            df.rename(columns={'Total Rax': 'Base Rax'}, inplace=True)
        if 'Rarity' not in df.columns:
            df['Rarity'] = 'Uncommon'
        df.insert(0, 'Rank', df.index + 1)
        return df
    else:
        df = generate_leaderboard()
        df.to_csv(CACHE_FILE, index=False)
        return df

def render_editable_rows(df):
    st.markdown("""
    <style>
      .row-box {
        border: 1px solid #999;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        background-color: #f9f9f9;
      }
      .col-rank { flex: 0.5; font-weight: 700; }
      .col-name { flex: 3.5; font-weight: 600; font-size: 18px; }
      .col-rarity, .col-rax { flex: 1.5; text-align: center; }
      select {
        font-size: 16px;
        padding: 4px 6px;
        border-radius: 4px;
      }
    </style>
    """, unsafe_allow_html=True)
    
    rarities = []
    for idx, r in df.iterrows():
        cols = st.columns([0.5, 3.5, 1.5, 1.5])
        with cols[0]:
            st.markdown(f"<div class='row-box'>{r['Rank']}</div>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"<div class='row-box'>{r['Fighter Name']}</div>", unsafe_allow_html=True)
        with cols[2]:
            rarity = st.selectbox("", list(RARITY_MULTIPLIERS.keys()),
                                  index=list(RARITY_MULTIPLIERS.keys()).index(r['Rarity']),
                                  key=f"rarity_{idx}", label_visibility="collapsed")
        with cols[3]:
            total_rax = round(r['Base Rax'] * RARITY_MULTIPLIERS[rarity], 1)
            st.markdown(f"<div class='row-box'>{total_rax}</div>", unsafe_allow_html=True)
        rarities.append(rarity)
    return rarities

def main():
    st.set_page_config(layout="wide", page_title="UFC RAX Leaderboard")
    st.title("🏆 UFC Fighter RAX Leaderboard")

    df = cache_and_load()
    
    # If this is first load, initialize session state rarity list
    if "rarities" not in st.session_state:
        st.session_state.rarities = list(df['Rarity'])

    # Apply current rarities from session_state (updated with user selections)
    df['Rarity'] = st.session_state.rarities
    df['Total Rax'] = df.apply(lambda r: round(r['Base Rax'] * RARITY_MULTIPLIERS[r['Rarity']], 1), axis=1)
    df = df.sort_values(by='Total Rax', ascending=False).reset_index(drop=True)
    if 'Rank' in df.columns:
        df.drop(columns=['Rank'], inplace=True)
    df.insert(0, 'Rank', df.index + 1)

    # Display the final leaderboard on top
    st.markdown("### Final Leaderboard (Sorted by Adjusted RAX)")
    st.dataframe(df[['Rank','Fighter Name','Total Rax','Rarity']], use_container_width=True)

    st.markdown("---")
    st.markdown("### Edit Rarity per Fighter Below")
    
    # Editable rows with dropdowns below, update session_state on changes
    new_rarities = render_editable_rows(df)
    if new_rarities != st.session_state.rarities:
        st.session_state.rarities = new_rarities
        st.experimental_rerun()

if __name__ == "__main__":
    main()
