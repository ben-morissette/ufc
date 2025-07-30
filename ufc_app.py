import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# --- Search fighters safely ---
def search_fighter_by_name_part(name_part):
    url = f"http://ufcstats.com/statistics/fighters?char={name_part[0].upper()}&page=all"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="b-statistics__table")

    results = []
    if not table:
        return results

    for row in table.find_all("tr")[1:]:  # skip header
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

# --- Get fighter's fight links and main fight info ---
def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Parse fight table
    table = soup.find("table", class_="b-fight-details__table")
    if not table:
        return [], pd.DataFrame()

    fight_links = []
    rows = table.find_all("tr")[1:]  # skip header

    data = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 7:
            continue
        fight_link_tag = cols[0].find("a")
        if not fight_link_tag:
            continue
        fight_link = fight_link_tag.get("href")
        fight_links.append(fight_link)

        # Extract basic info
        data.append({
            'fight_link': fight_link,
            'fighter_name': cols[1].text.strip(),
            'opponent_name': cols[2].text.strip(),
            'result': cols[5].text.strip().lower(),  # 'win' or 'loss' (sometimes 'draw')
            'method_main': cols[6].text.strip(),
            'TimeFormat': cols[7].text.strip() if len(cols) > 7 else '',
            'Details': cols[8].text.strip() if len(cols) > 8 else ''
        })

    df = pd.DataFrame(data)
    return fight_links, df

# --- Parse fight details for advanced stats (stub, you may need to customize) ---
def parse_fight_details(fight_link, fighter_name, opponent_name):
    # Example: scrape significant strikes landed for fighter and opponent
    response = requests.get(fight_link)
    soup = BeautifulSoup(response.text, "html.parser")

    # Placeholder selectors - adjust as needed based on actual UFC stats page structure
    stats = {
        'fight_link': fight_link,
        'TOT_fighter_SigStr_landed': 0,
        'TOT_opponent_SigStr_landed': 0
    }

    # Find stats table or specific data — this part depends on site layout.
    # For example, find stats for fighter:
    try:
        stats_table = soup.find("table", class_="b-fight-details__table")
        # You would parse rows and columns here to fill in stats
        # Dummy example:
        # stats['TOT_fighter_SigStr_landed'] = int(...)
        # stats['TOT_opponent_SigStr_landed'] = int(...)
    except Exception:
        pass

    return stats

# --- Transform columns if needed ---
def transform_columns(df):
    # Implement any needed cleaning or type conversion here
    return df

# --- Calculate RAX score ---
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

    sig_str_fighter = row.get('TOT_fighter_SigStr_landed', 0) or 0
    sig_str_opponent = row.get('TOT_opponent_SigStr_landed', 0) or 0

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    if 'TimeFormat' in row and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# --- Main Streamlit app ---
def main():
    st.title("UFC Fighter RAX Calculator")

    fighter_name_input = st.text_input("Enter fighter name (or part of it):")
    if not fighter_name_input:
        st.info("Please enter a fighter name to search.")
        return

    matches = search_fighter_by_name_part(fighter_name_input)

    if not matches:
        st.warning("No fighters found matching that name.")
        return

    # Select fighter from matches
    selected_fighter = st.selectbox("Select fighter", [name for name, url in matches])

    fighter_url = None
    for name, url in matches:
        if name == selected_fighter:
            fighter_url = url
            break

    if not fighter_url:
        st.error("Could not find fighter URL.")
        return

    st.write(f"Fetching fights for **{selected_fighter}** ...")

    fight_links, main_fights_df = get_fight_links(fighter_url)

    if main_fights_df.empty:
        st.warning("No fights found for this fighter.")
        return

    all_fight_details = []
    for fl in fight_links:
        row = main_fights_df.loc[main_fights_df['fight_link'] == fl].iloc[0]
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

if __name__ == "__main__":
    main()
