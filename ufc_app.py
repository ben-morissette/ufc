import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from difflib import get_close_matches

# Streamlit page setup
st.set_page_config(page_title="UFC Fighter Stats", layout="wide")
st.title("🥊 UFC Fighter Stats Explorer")

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# ---------------------------
# Helper Functions
# ---------------------------

def search_fighter_by_name_part(name_part):
    url = f"http://ufcstats.com/statistics/fighters?char={name_part[0].upper()}&page=all"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="b-statistics__table")
    
    results = []
    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if not cols:
            continue
        full_name = cols[0].text.strip()
        profile_link = cols[0].find("a")["href"]
        results.append((full_name, profile_link))
    
    return results

def get_fighter_url_by_name(fighter_name):
    results = search_fighter_by_name_part(fighter_name)
    names = [r[0] for r in results]
    match = get_close_matches(fighter_name, names, n=1, cutoff=0.6)
    if not match:
        raise ValueError("Fighter not found.")
    for name, link in results:
        if name == match[0]:
            return link
    raise ValueError("Fighter not found after fuzzy matching.")

def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="b-fight-details__table")

    links = []
    opponents = []
    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if not cols:
            continue
        fight_link = cols[-1].find("a")["href"]
        opponent_name = cols[1].text.strip()
        links.append(fight_link)
        opponents.append(opponent_name)

    fight_df = pd.DataFrame({"fight_url": links, "opponent_name": opponents})
    return links, fight_df

def parse_fight_details(url, fighter_name, opponent_name):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    stats_tables = soup.find_all("table", class_="b-fight-details__table")

    rows = []
    for table in stats_tables:
        headers = [th.text.strip() for th in table.find_all("th")]
        fighters = table.find_all("tr", class_="b-fight-details__table-row")
        for f in fighters:
            cols = [td.text.strip() for td in f.find_all("td")]
            if len(cols) != len(headers):
                continue
            data = dict(zip(headers, cols))
            data["fighter_name"] = f.find("td", class_="b-fight-details__table-col l-page_align_left").text.strip()
            rows.append(data)

    df = pd.DataFrame(rows)
    df = df[df["fighter_name"] == fighter_name]
    df["opponent"] = opponent_name
    df["fight_url"] = url
    return df

def transform_columns(df):
    # Example transformation: parse strikes and convert to numbers
    if 'SIG. STR.' in df.columns:
        df[["sig_str_landed", "sig_str_attempted"]] = df["SIG. STR."].str.split(" of ", expand=True).astype(float)
    if 'TOTAL STR.' in df.columns:
        df[["total_str_landed", "total_str_attempted"]] = df["TOTAL STR."].str.split(" of ", expand=True).astype(float)
    if 'TD' in df.columns:
        df[["takedowns_landed", "takedowns_attempted"]] = df["TD"].str.split(" of ", expand=True).astype(float)
    return df

# ---------------------------
# Streamlit App UI
# ---------------------------

fighter_name = st.text_input("Enter a fighter's full name", "")

if fighter_name:
    try:
        with st.spinner("Fetching fighter profile..."):
            fighter_url = get_fighter_url_by_name(fighter_name)
            fight_links, fight_df = get_fight_links(fighter_url)

        st.success(f"Found {len(fight_links)} fights for {fighter_name}")

        all_fight_details = []
        for idx, link in enumerate(fight_links):
            with st.spinner(f"Parsing fight {idx+1}/{len(fight_links)}..."):
                fight_info = parse_fight_details(link, fighter_name, fight_df.loc[idx, 'opponent_name'])
                all_fight_details.append(fight_info)

        df = pd.concat(all_fight_details, ignore_index=True)
        df = transform_columns(df)

        st.subheader("📊 Fight Statistics")
        st.dataframe(df)

        # Download button
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download as CSV", csv, f"{fighter_name.replace(' ', '_')}_fight_stats.csv", "text/csv")

    except Exception as e:
        st.error(f"❌ Error: {e}")
else:
    st.info("Type a UFC fighter's full name (e.g., Jon Jones, Khabib Nurmagomedov)")
