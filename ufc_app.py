import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
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
        df.insert(0, 'Rank', df.index + 1)
        if 'Base Rax' not in df.columns and 'Total Rax' in df.columns:
            df.rename(columns={'Total Rax': 'Base Rax'}, inplace=True)
        if 'Rarity' not in df.columns:
            df['Rarity'] = 'Uncommon'
        return df
    else:
        df = generate_leaderboard()
        df.to_csv(CACHE_FILE, index=False)
        return df

def render_rows(df):
    st.markdown("""
    <style>
      .row-box {border:1px solid #ccc; padding:8px; margin-bottom:4px;}
    </style>
    """, unsafe_allow_html=True)
    selections = []
    for idx, r in df.iterrows():
        col1, col2, col3 = st.columns([4, 2, 2])
        with col1:
            st.markdown(f"<div class='row-box'><strong>{r['Fighter Name']}</strong></div>", unsafe_allow_html=True)
        with col2:
            sel = st.selectbox("", list(RARITY_MULTIPLIERS.keys()), index=list(RARITY_MULTIPLIERS.keys()).index(r['Rarity']),
                               key=f"rarity_{idx}", label_visibility="collapsed")
        with col3:
            trax = round(r['Base Rax'] * RARITY_MULTIPLIERS[sel], 1)
            st.markdown(f"<div class='row-box'>{trax}</div>", unsafe_allow_html=True)
        selections.append(sel)
    return selections

def main():
    st.set_page_config(layout="wide", page_title="UFC RAX Leaderboard")
    st.title("🏆 UFC Fighter RAX Leaderboard")
    df = cache_and_load()
    selections = render_rows(df)
    df['Rarity'] = selections
    df['Total Rax'] = df.apply(lambda r: round(r['Base Rax'] * RARITY_MULTIPLIERS[r['Rarity']], 1), axis=1)
    df = df.sort_values(by='Total Rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', df.index + 1)
    st.markdown("---")
    st.markdown("### Final Leaderboard")
    st.dataframe(df[['Rank','Fighter Name','Total Rax','Rarity']], use_container_width=True)

if __name__ == "__main__":
    main()
