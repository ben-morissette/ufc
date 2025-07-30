import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import string
import time

# Your existing helper functions here:
# - get_fighter_url_by_name
# - search_fighter_by_name_part
# - get_fight_links
# - parse_fight_details
# - transform_columns
# - calculate_rax
# (Make sure all these are defined exactly as you have them)

# Example of calculate_rax function:
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

    sig_str_fighter = row.get('TOT_fighter_SigStr_landed', 0)
    sig_str_opponent = row.get('TOT_opponent_SigStr_landed', 0)

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    if 'TimeFormat' in row and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# Your function to get all fighter links with retries and tqdm progress
def get_all_fighter_links():
    all_links = []
    base_url = "http://ufcstats.com/statistics/fighters?char="
    for letter in string.ascii_lowercase:
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
        for row in fighter_rows:
            link_tag = row.find('a', class_='b-link_style_black')
            if link_tag and 'href' in link_tag.attrs:
                all_links.append(link_tag['href'])

    return list(set(all_links))

@st.cache_data(show_spinner=False)
def load_leaderboard_data():
    all_fighter_links = get_all_fighter_links()
    all_fighters_data = []

    for fighter_url in all_fighter_links:
        try:
            fight_links, main_fights_df = get_fight_links(fighter_url)
            if fight_links:
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
        except Exception as e:
            print(f"Error processing fighter {fighter_url}: {e}")
            continue

    leaderboard_df = pd.DataFrame(all_fighters_data)
    leaderboard_df = leaderboard_df.sort_values(by='total_rax', ascending=False).reset_index(drop=True)
    return leaderboard_df

def main():
    st.title("UFC Fighter Rax Tracker")

    menu = ["Search Fighter", "Show Leaderboard"]
    choice = st.sidebar.selectbox("Choose Option", menu)

    if choice == "Search Fighter":
        fighter_name_input = st.text_input("Enter fighter name (or part of it):")

        if fighter_name_input:
            matches = search_fighter_by_name_part(fighter_name_input)
            if not matches:
                st.warning("No fighters found matching that name.")
            else:
                selected_fighter = st.selectbox("Select Fighter", matches)
                if selected_fighter:
                    try:
                        fighter_url = get_fighter_url_by_name(selected_fighter)
                        fight_links, main_fights_df = get_fight_links(fighter_url)

                        all_fight_details = []
                        for fl in fight_links:
                            row_index = main_fights_df.index[main_fights_df['fight_link'] == fl].tolist()
                            if not row_index:
                                continue
                            row = main_fights_df.loc[row_index[0]]
                            main_fighter_name = row['fighter_name']
                            opp_name = row['opponent_name']
                            details = parse_fight_details(fl, main_fighter_name, opp_name)
                            all_fight_details.append(details)

                        advanced_df = pd.DataFrame(all_fight_details)
                        combined_df = pd.merge(main_fights_df, advanced_df, on='fight_link', how='left')
                        combined_df = transform_columns(combined_df)
                        combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)

                        total_rax = combined_df['rax_earned'].sum()
                        total_row = pd.DataFrame({
                            'fighter_name': [''],
                            'opponent_name': [''],
                            'result': [''],
                            'method_main': ['Total Rax'],
                            'rax_earned': [total_rax]
                        })
                        final_df = pd.concat([combined_df[['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']], total_row], ignore_index=True)
                        st.dataframe(final_df)
                    except Exception as e:
                        st.error(f"Error: {e}")

    elif choice == "Show Leaderboard":
        st.header("Leaderboard: Total Rax of All Fighters")
        leaderboard_df = load_leaderboard_data()
        st.dataframe(leaderboard_df)


if __name__ == "__main__":
    main()
