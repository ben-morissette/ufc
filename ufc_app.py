import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import string
import time
from tqdm import tqdm

# ----------------------------
# Helper Functions (Replace these stubs with your real implementations)
# ----------------------------

def search_fighter_by_name_part(name_part):
    """Search fighters whose name contains the name_part, return list of (name, url)."""
    base_url = "http://ufcstats.com/statistics/fighters?char="
    matched = []
    # Scrape all letters to find matches (simplified: search all fighters once)
    for letter in string.ascii_lowercase:
        url = f"{base_url}{letter}&page=all"
        try:
            res = requests.get(url)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            table = soup.find("table", class_="b-statistics__table")
            if not table:
                continue
            rows = table.find("tbody").find_all("tr", class_="b-statistics__table-row")
            for row in rows:
                fighter_cell = row.find("a", class_="b-link_style_black")
                if fighter_cell:
                    fighter_name = fighter_cell.text.strip()
                    fighter_url = fighter_cell['href']
                    if name_part.lower() in fighter_name.lower():
                        matched.append((fighter_name, fighter_url))
        except Exception:
            continue
    return matched

def get_fighter_url_by_name(fighter_name):
    """Find fighter url exactly matching the name."""
    fighters = search_fighter_by_name_part(fighter_name)
    for name, url in fighters:
        if name.lower() == fighter_name.lower():
            return url
    raise ValueError(f"Fighter '{fighter_name}' not found.")

def get_fight_links(fighter_url):
    """Return (list_of_fight_links, DataFrame of fights summary) for a fighter."""
    try:
        res = requests.get(fighter_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table", class_="b-fight-details__table")
        if not table:
            return [], pd.DataFrame()
        fight_links = []
        data = []
        rows = table.find_all("tr", class_="b-fight-details__table-row")
        for row in rows:
            fight_link = row.find("a", class_="b-link")
            if not fight_link:
                continue
            fight_url = fight_link['href']
            fight_links.append(fight_url)

            cols = row.find_all("td")
            if len(cols) >= 7:
                data.append({
                    "fight_link": fight_url,
                    "fighter_name": cols[1].text.strip(),
                    "opponent_name": cols[2].text.strip(),
                    "result": cols[3].text.strip().lower(),
                    "method_main": cols[4].text.strip(),
                    "details": cols[5].text.strip(),
                    "timeformat": cols[6].text.strip()
                })
        df = pd.DataFrame(data)
        return fight_links, df
    except Exception:
        return [], pd.DataFrame()

def parse_fight_details(fight_link, main_fighter_name, opponent_name):
    """Scrape advanced fight stats; simplified stub returns empty dict."""
    # For demo, just return some placeholder dict with fight_link key
    return {"fight_link": fight_link}

def transform_columns(df):
    """Do any data transformation needed; here, pass-through."""
    return df

def calculate_rax(row):
    rax = 0
    # Rule 1: Rax based on method_main
    if row.get('result', '') == 'win':
        if row.get('method_main', '') == 'KO/TKO':
            rax += 100
        elif row.get('method_main', '') == 'Submission':
            rax += 90
        elif row.get('method_main', '') == 'Decision - Unanimous':
            rax += 80
        elif row.get('method_main', '') == 'Decision - Majority':
            rax += 75
        elif row.get('method_main', '') == 'Decision - Split':
            rax += 70
    elif row.get('result', '') == 'loss':
        rax += 25

    # Rule 2: Rax based on significant strike difference (dummy example)
    sig_str_fighter = row.get('TOT_fighter_SigStr_landed', 0)
    sig_str_opponent = row.get('TOT_opponent_SigStr_landed', 0)
    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights
    if '5 Rnd' in str(row.get('timeformat', '')):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Fight of the Night' in str(row.get('details', '')):
        rax += 50

    return rax

def get_all_fighter_links():
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="
    for letter in tqdm(string.ascii_lowercase, desc="Scraping fighter links"):
        url = f"{base_url}{letter}&page=all"
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            fighter_table = soup.find('table', class_='b-statistics__table')
            if not fighter_table:
                continue
            fighter_rows = fighter_table.find('tbody').find_all('tr', class_='b-statistics__table-row')
            for row in fighter_rows:
                link_tag = row.find('a', class_='b-link_style_black')
                if link_tag and 'href' in link_tag.attrs:
                    all_links.append(link_tag['href'])
        except Exception:
            continue
    return list(set(all_links))

def calculate_leaderboard():
    all_fighter_links = get_all_fighter_links()
    all_fighters_data = []

    for fighter_url in tqdm(all_fighter_links, desc="Processing fighters"):
        try:
            fight_links, main_fights_df = get_fight_links(fighter_url)
            if fight_links == [] or main_fights_df.empty:
                continue
            fighter_fight_details = []
            for fl in fight_links:
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

        except Exception:
            continue

    leaderboard_df = pd.DataFrame(all_fighters_data)
    leaderboard_df = leaderboard_df.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    return leaderboard_df

# ----------------------------
# Streamlit App
# ----------------------------

@st.cache_data(ttl=43200)
def get_cached_leaderboard():
    return calculate_leaderboard()

def main():
    st.title("UFC Fighter Rax Calculator & Leaderboard")

    # --- Fighter search ---
    fighter_name_input = st.text_input("Enter fighter name (or part of it):")

    if fighter_name_input:
        with st.spinner("Searching fighters..."):
            matches = search_fighter_by_name_part(fighter_name_input)

        if not matches:
            st.error("No fighters found matching that name.")
        else:
            if len(matches) > 1:
                fighter_options = [name for name, url in matches]
                selected_fighter = st.selectbox("Select fighter:", fighter_options)
            else:
                selected_fighter = matches[0][0]

            if selected_fighter:
                try:
                    with st.spinner(f"Loading fights for {selected_fighter}..."):
                        fighter_url = get_fighter_url_by_name(selected_fighter)
                        fight_links, main_fights_df = get_fight_links(fighter_url)

                        all_fight_details = []
                        for fl in fight_links:
                            details = parse_fight_details(fl, "", "")
                            all_fight_details.append(details)

                        advanced_df = pd.DataFrame(all_fight_details)
                        combined_df = pd.merge(main_fights_df, advanced_df, on='fight_link', how='left')
                        combined_df = transform_columns(combined_df)
                        combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)
                        total_rax = combined_df['rax_earned'].sum()

                        total_row = pd.DataFrame({
                            'fighter_name': ['Total'],
                            'opponent_name': [''],
                            'result': [''],
                            'method_main': [''],
                            'rax_earned': [total_rax]
                        })

                        final_df = pd.concat([combined_df[['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']], total_row], ignore_index=True)
                        st.dataframe(final_df)

                except ValueError as e:
                    st.error(str(e))

    # --- Leaderboard ---
    st.header("Rax Leaderboard")
    if st.button("Refresh Leaderboard (Slow, several minutes)"):
        st.warning("Recalculating leaderboard, please wait...")
        leaderboard_df = calculate_leaderboard()
        st.session_state['leaderboard'] = leaderboard_df
    else:
        if 'leaderboard' not in st.session_state:
            leaderboard_df = get_cached_leaderboard()
            st.session_state['leaderboard'] = leaderboard_df
        else:
            leaderboard_df = st.session_state['leaderboard']

    if leaderboard_df is not None and not leaderboard_df.empty:
        st.dataframe(leaderboard_df)

if __name__ == "__main__":
    main()
