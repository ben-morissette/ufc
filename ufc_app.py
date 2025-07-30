import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

def search_fighter_by_name_part(name_part):
    url = f"http://ufcstats.com/statistics/fighters?char={name_part[0].upper()}&page=all"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="b-statistics__table")

    results = []
    if not table:
        return results

    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if not cols:
            continue
        full_name = cols[0].text.strip()
        profile_link = cols[0].find("a")["href"]
        if name_part.lower() in full_name.lower():
            results.append((full_name, profile_link))

    return results

def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="b-fight-details__table")

    links = []
    opponents = []
    fighter_names = []
    results = []
    methods = []
    time_formats = []
    details_list = []

    if not table:
        return [], pd.DataFrame()

    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if not cols or not cols[-1].find("a"):
            continue
        fight_link = cols[-1].find("a")["href"]
        opponent_name = cols[1].text.strip()
        fighter_name = cols[2].text.strip()
        result = cols[0].text.strip().lower()
        method_main = cols[3].text.strip()
        time_format = cols[6].text.strip()
        details = cols[7].text.strip()

        links.append(fight_link)
        opponents.append(opponent_name)
        fighter_names.append(fighter_name)
        results.append(result)
        methods.append(method_main)
        time_formats.append(time_format)
        details_list.append(details)

    df = pd.DataFrame({
        "fight_link": links,
        "opponent_name": opponents,
        "fighter_name": fighter_names,
        "result": results,
        "method_main": methods,
        "TimeFormat": time_formats,
        "Details": details_list,
    })

    return links, df

def parse_fight_details(fight_url):
    # Fetch advanced fight details from fight page (e.g. sig strikes landed)
    response = requests.get(fight_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Example: grab significant strikes landed by fighter and opponent
    # This is a simplified example; adapt parsing based on real page structure.

    stats = {}
    try:
        sig_strike_table = soup.find("table", class_="b-fight-details__table")
        if sig_strike_table:
            rows = sig_strike_table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    stat_name = cols[0].text.strip()
                    fighter_val = cols[1].text.strip()
                    opp_val = cols[2].text.strip()
                    # For example, extract significant strikes landed
                    if "Sig. Str." in stat_name:
                        # Extract numbers from string like '55 of 100'
                        fighter_num = int(fighter_val.split(' ')[0])
                        opp_num = int(opp_val.split(' ')[0])
                        stats['TOT_fighter_SigStr_landed'] = fighter_num
                        stats['TOT_opponent_SigStr_landed'] = opp_num
    except Exception:
        pass

    return stats

def transform_columns(df):
    # Convert numeric columns to proper types if needed
    for col in ['TOT_fighter_SigStr_landed', 'TOT_opponent_SigStr_landed']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

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
    if '5 Rnd' in str(row.get('TimeFormat', '')):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Fight of the Night' in str(row.get('Details', '')):
        rax += 50

    return rax

def main():
    st.title("UFC Fighter Rax Calculator")

    fighter_name_input = st.text_input("Enter fighter name (or part):")

    if fighter_name_input:
        matches = search_fighter_by_name_part(fighter_name_input)
        if not matches:
            st.warning("No fighters found matching that name.")
            return

        fighter_options = {name: link for name, link in matches}
        selected_fighter = st.selectbox("Select a fighter:", list(fighter_options.keys()))
        fighter_url = fighter_options[selected_fighter]

        fight_links, main_fights_df = get_fight_links(fighter_url)
        if fight_links == [] or main_fights_df.empty:
            st.warning("No fight data found for this fighter.")
            return

        all_details = []
        for fight_link in fight_links:
            details = parse_fight_details(fight_link)
            all_details.append(details)

        advanced_df = pd.DataFrame(all_details)
        combined_df = pd.concat([main_fights_df.reset_index(drop=True), advanced_df.reset_index(drop=True)], axis=1)
        combined_df = transform_columns(combined_df)

        combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)

        total_rax = combined_df['rax_earned'].sum()

        total_row = {
            'fighter_name': '',
            'opponent_name': '',
            'result': '',
            'method_main': 'Total Rax',
            'rax_earned': total_rax,
            'TimeFormat': '',
            'Details': ''
        }
        final_df = combined_df[['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned', 'TimeFormat', 'Details']].copy()
        final_df = final_df.append(total_row, ignore_index=True)

        st.dataframe(final_df)

if __name__ == "__main__":
    main()
