import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import string
from difflib import get_close_matches
from tqdm import tqdm

# --------------------------- Scraping and Parsing Functions ---------------------------

@st.cache_data(show_spinner="Loading all fighter links...")
def get_all_fighter_links():
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="

    for letter in tqdm(string.ascii_lowercase, desc="Scraping fighter links"):
        url = f"{base_url}{letter}&page=all"
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            fighter_table = soup.find('table', class_='b-statistics__table')
            if not fighter_table:
                continue
            fighter_rows = fighter_table.find('tbody').find_all('tr', class_='b-statistics__table-row')
            for row in fighter_rows:
                link_tag = row.find('a', class_='b-link_style_black')
                if link_tag and 'href' in link_tag.attrs:
                    all_links.append(link_tag['href'])
        except:
            continue

    return list(set(all_links))

def get_fighter_url_by_name(input_name):
    match = get_close_matches(input_name.lower(), [url.split("/")[-1].replace('-', ' ').lower() for url in all_fighter_links], n=1)
    if not match:
        raise ValueError("Fighter not found.")
    for url in all_fighter_links:
        if match[0] in url.lower():
            return url
    raise ValueError("Fighter URL not found.")

def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    fight_table = soup.find('table', class_='b-fight-details__table')
    if not fight_table:
        return [], pd.DataFrame()

    rows = fight_table.find_all('tr')[1:]
    fight_links = []
    data = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 7:
            continue
        fight_link = cols[6].find('a')['href']
        fight_links.append(fight_link)
        data.append({
            'fight_link': fight_link,
            'result': cols[0].text.strip().lower(),
            'opponent_name': cols[1].text.strip(),
            'method_main': cols[3].text.strip(),
            'fighter_name': soup.find('span', class_='b-content__title-highlight').text.strip()
        })

    return fight_links, pd.DataFrame(data)

def parse_fight_details(fight_link, fighter_name, opponent_name):
    response = requests.get(fight_link)
    soup = BeautifulSoup(response.text, 'html.parser')

    stat_sections = soup.find_all('tbody')
    row_data = {'fight_link': fight_link}

    try:
        fighter_rows = stat_sections[0].find_all('tr')
        for row in fighter_rows:
            cols = row.find_all('td')
            if len(cols) == 4:
                metric = cols[0].text.strip().replace(' ', '_')
                fighter_val = cols[1].text.strip()
                opponent_val = cols[3].text.strip()
                row_data[f'TOT_fighter_{metric}'] = parse_stat_value(fighter_val)
                row_data[f'TOT_opponent_{metric}'] = parse_stat_value(opponent_val)
    except:
        pass

    time_format_el = soup.find('i', string=lambda t: t and 'Round' in t)
    row_data['TimeFormat'] = time_format_el.text.strip() if time_format_el else ""

    bonus_el = soup.find('p', class_='b-fight-details__fight-title')
    row_data['Details'] = bonus_el.text.strip() if bonus_el else ""

    return row_data

def parse_stat_value(value):
    try:
        return int(value.split()[0]) if value else 0
    except:
        return 0

def transform_columns(df):
    for col in df.columns:
        if col.startswith('TOT_'):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --------------------------- Your Exact RAX Function ---------------------------

def calculate_rax(row):
    rax = 0
    # Rule 1: Rax based on method_main
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

    # Rule 2: Rax based on significant strike difference
    sig_str_fighter = row.get('TOT_fighter_Sig_Str_landed', 0)
    sig_str_opponent = row.get('TOT_opponent_Sig_Str_landed', 0)

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights
    if 'TimeFormat' in row.index and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Details' in row.index and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# --------------------------- Build Leaderboard ---------------------------

@st.cache_data(show_spinner="Building leaderboard...")
def build_leaderboard():
    all_data = []
    for url in tqdm(all_fighter_links, desc="Calculating RAX"):
        try:
            fight_links, main_df = get_fight_links(url)
            if main_df.empty:
                continue
            details = []
            for fl in fight_links:
                row = main_df.loc[main_df['fight_link'] == fl].iloc[0]
                fighter = row['fighter_name']
                opponent = row['opponent_name']
                d = parse_fight_details(fl, fighter, opponent)
                details.append(d)
            if not details:
                continue
            adv_df = pd.DataFrame(details)
            combined = pd.merge(main_df, adv_df, on='fight_link', how='left')
            combined = transform_columns(combined)
            combined['rax_earned'] = combined.apply(calculate_rax, axis=1)
            total = combined['rax_earned'].sum()
            all_data.append({'fighter_name': fighter, 'total_rax': total})
        except Exception as e:
            print(f"Error with {url}: {e}")
            continue

    df = pd.DataFrame(all_data)
    df = df.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', range(1, len(df) + 1))
    return df

# --------------------------- Streamlit UI ---------------------------

st.set_page_config(page_title="UFC RAX Leaderboard", layout="wide")
st.title("🥊 UFC RAX Leaderboard")

# Load fighter URLs once
all_fighter_links = get_all_fighter_links()

# Build leaderboard
leaderboard_df = build_leaderboard()

# Search box
search_name = st.text_input("Search for a fighter (partial names allowed):").strip().lower()

if search_name:
    filtered_df = leaderboard_df[leaderboard_df['fighter_name'].str.lower().str.contains(search_name)]
    st.subheader("🔍 Search Results")
    st.dataframe(filtered_df.reset_index(drop=True), use_container_width=True)
else:
    st.subheader("🏆 Full Leaderboard")
    st.dataframe(leaderboard_df, use_container_width=True)
