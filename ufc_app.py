import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import string

# --------- Fighter Search (fixed to search all letters) ---------
def search_fighter_by_name_part(name_part):
    results = []
    for letter in string.ascii_uppercase:
        url = f"http://ufcstats.com/statistics/fighters?char={letter}&page=all"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="b-statistics__table")

        if not table:
            continue

        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if not cols:
                continue
            a_tag = cols[0].find("a")
            if not a_tag:
                continue
            full_name = cols[0].text.strip()
            profile_link = a_tag.get("href")
            if name_part.lower() in full_name.lower():
                results.append((full_name, profile_link))
    return results

# --------- Get fighter URL by exact name ---------
def get_fighter_url_by_name(name):
    matches = search_fighter_by_name_part(name)
    for full_name, url in matches:
        if full_name.lower() == name.lower():
            return url
    raise ValueError(f"No exact match found for fighter name '{name}'")

# --------- Get fight links from fighter profile ---------
def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, "html.parser")
    fights = soup.select("a.b-link.b-fight-details__link")
    fight_links = [fight['href'] for fight in fights]

    # For simplicity, mock main_fights_df with minimal data (in practice you parse real data)
    # Here just creating dummy DataFrame with fight links and placeholder columns:
    data = {
        'fight_link': fight_links,
        'fighter_name': ["" for _ in fight_links],
        'opponent_name': ["" for _ in fight_links],
        'result': ["" for _ in fight_links],
        'method_main': ["" for _ in fight_links],
        'TimeFormat': ["" for _ in fight_links],
        'Details': ["" for _ in fight_links],
        'TOT_fighter_SigStr_landed': [0 for _ in fight_links],
        'TOT_opponent_SigStr_landed': [0 for _ in fight_links]
    }
    main_fights_df = pd.DataFrame(data)
    return fight_links, main_fights_df

# --------- Placeholder for parsing fight details ---------
def parse_fight_details(fight_link, fighter_name, opponent_name):
    # This is a stub: in your app, scrape fight_link and extract fight details
    return {
        'fight_link': fight_link,
        'fighter_name': fighter_name,
        'opponent_name': opponent_name,
        'result': 'win',  # example
        'method_main': 'KO/TKO',  # example
        'TimeFormat': '3 Rnd',
        'Details': '',
        'TOT_fighter_SigStr_landed': 100,
        'TOT_opponent_SigStr_landed': 80,
    }

# --------- Transform columns placeholder ---------
def transform_columns(df):
    # Your transformation logic here, or return as-is
    return df

# --------- Calculate Rax ---------
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
    sig_str_fighter = row.get('TOT_fighter_SigStr_landed', 0)
    sig_str_opponent = row.get('TOT_opponent_SigStr_landed', 0)
    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights
    if 'TimeFormat' in row and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Details' in row and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# --------- Streamlit app ---------
def main():
    st.title("UFC Fighter Rax Calculator")

    fighter_name_input = st.text_input("Enter fighter name (or part of it):")

    if fighter_name_input:
        with st.spinner("Searching for fighters..."):
            matches = search_fighter_by_name_part(fighter_name_input)

        if not matches:
            st.error("No fighters found matching that name.")
            return

        # If multiple matches, let user select
        if len(matches) > 1:
            fighter_options = [name for name, url in matches]
            selected_fighter = st.selectbox("Select fighter:", fighter_options)
        else:
            selected_fighter = matches[0][0]

        try:
            fighter_url = get_fighter_url_by_name(selected_fighter)
        except ValueError as e:
            st.error(str(e))
            return

        st.write(f"Found fighter URL: {fighter_url}")

        fight_links, main_fights_df = get_fight_links(fighter_url)

        if len(fight_links) == 0:
            st.warning("No fights found for this fighter.")
            return

        all_fight_details = []
        for fl in fight_links:
            # For demo, using empty names; ideally get actual fighter and opponent names from main_fights_df or scraping
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

if __name__ == "__main__":
    main()
