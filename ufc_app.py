import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Rarity multipliers
RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

def find_fighter_url(name):
    """Find fighter profile URL by exact name (case-insensitive). Searches pages by first letter until found or no more pages."""
    base_url = "http://ufcstats.com/statistics/fighters?char={letter}&page={page}"
    name = name.strip().lower()
    first_letter = name[0]
    page = 1
    while True:
        url = base_url.format(letter=first_letter, page=page)
        res = requests.get(url)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table", class_="b-statistics__table")
        if not table:
            return None
        rows = table.find("tbody").find_all("tr", class_="b-statistics__table-row")
        if not rows:
            return None
        found = False
        for row in rows:
            link = row.find_all("td")[0].find("a", class_="b-link_style_black")
            if link:
                fighter_name = link.text.strip().lower()
                if fighter_name == name:
                    return link["href"]
        page += 1

def get_fight_links_and_main_data(fighter_url):
    """Scrape the main fighter page for fight URLs and basic fight info."""
    res = requests.get(fighter_url)
    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.find("table", class_="b-fight-details__table_type_event-details")
    if not table:
        return [], pd.DataFrame()
    rows = table.find("tbody").find_all("tr", class_="b-fight-details__table-row__hover")
    fights = []
    for row in rows:
        cols = row.find_all("td", class_="b-fight-details__table-col")
        result = cols[0].find("p").get_text(strip=True).lower()
        fighter_name = cols[1].find_all("p")[0].get_text(strip=True)
        opponent_name = cols[1].find_all("p")[1].get_text(strip=True)
        event_name = cols[6].find_all("p")[0].get_text(strip=True)
        event_date = cols[6].find_all("p")[1].get_text(strip=True) if len(cols[6].find_all("p")) > 1 else ""
        method_main_raw = cols[7].find_all("p")[0].get_text(strip=True)
        method_detail = cols[7].find_all("p")[1].get_text(strip=True) if len(cols[7].find_all("p")) > 1 else ""
        round_val = cols[8].find("p").get_text(strip=True)
        time_val = cols[9].find("p").get_text(strip=True) if len(cols) > 9 else ""
        fight_link = fighter_url  # We'll reuse fighter_url since detailed info pages are same

        # Normalize method names
        method_map = {
            'KO/TKO': 'KO/TKO',
            'Submission': 'Submission',
            'U-DEC': 'Decision - Unanimous',
            'M-DEC': 'Decision - Majority',
            'S-DEC': 'Decision - Split',
        }
        method_main = method_map.get(method_main_raw, method_main_raw)

        fights.append({
            'result': result,
            'fighter_name': fighter_name,
            'opponent_name': opponent_name,
            'event_name': event_name,
            'event_date': event_date,
            'method_main': method_main,
            'method_detail': method_detail,
            'round': round_val,
            'Time': time_val,
            'fight_link': fight_link,
        })

    return [f['fight_link'] for f in fights], pd.DataFrame(fights)

def parse_fight_details(fight_link, fighter_name, opponent_name):
    """Scrape detailed fight info from the fight page for specific fighter/opponent."""
    res = requests.get(fight_link)
    soup = BeautifulSoup(res.text, "html.parser")

    # Find stats table rows to get significant strikes, etc.
    stats_tables = soup.find_all("table", class_="b-fight-details__table")
    # We expect two main tables, one per fighter
    # We'll locate the one for the fighter and opponent by matching names

    def parse_stats_table(table, expected_fighter):
        # Parse relevant stats from the given table
        stats = {}
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            stat_name = cols[0].get_text(strip=True)
            fighter_stat = cols[1].get_text(strip=True)
            opponent_stat = cols[2].get_text(strip=True)

            # We'll extract significant strikes landed here for RAX
            if stat_name == "SIG. STRIKES":
                try:
                    stats['TOT_fighter_SigStr_landed'] = int(fighter_stat)
                    stats['TOT_opponent_SigStr_landed'] = int(opponent_stat)
                except:
                    stats['TOT_fighter_SigStr_landed'] = 0
                    stats['TOT_opponent_SigStr_landed'] = 0
            # You can parse more stats here as needed

        return stats

    # Find which table is fighter's by matching names near stats
    fighter_stats = {}
    for table in stats_tables:
        header = table.find_previous_sibling("div")
        if not header:
            continue
        header_name = header.get_text(strip=True).lower()
        if fighter_name.lower() in header_name:
            fighter_stats = parse_stats_table(table, fighter_name)
            break

    # Extract 'TimeFormat' and 'Details' info from fight details area if possible
    time_format = ""
    details = ""

    details_div = soup.find("div", class_="b-fight-details__fight")
    if details_div:
        time_format_tag = details_div.find("i", class_="b-fight-details__text_time-format")
        if time_format_tag:
            time_format = time_format_tag.get_text(strip=True)
        details_tag = details_div.find("p", class_="b-fight-details__text_type_fight-details")
        if details_tag:
            details = details_tag.get_text(strip=True)

    fighter_stats['TimeFormat'] = time_format
    fighter_stats['Details'] = details
    fighter_stats['fight_link'] = fight_link
    return fighter_stats

def transform_columns(df):
    """Any necessary data cleanup or type conversions."""
    # For example, convert numeric fields from strings if needed
    # Currently, assume numeric fields parsed correctly
    return df

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

    if '5 Rnd' in str(row.get('TimeFormat', '')) or '5' in str(row.get('round', '')):
        rax += 25

    if 'Fight of the Night' in str(row.get('Details', '')) or 'Fight of the Night' in str(row.get('method_detail', '')):
        rax += 50

    return rax

# Streamlit UI

st.title("UFC Fighter RAX Search")

fighter_name_input = st.text_input("Enter fighter full name exactly (case insensitive)")

if fighter_name_input.strip():
    with st.spinner(f"Searching for fighter '{fighter_name_input}'..."):
        url = find_fighter_url(fighter_name_input)
    if url is None:
        st.warning(f"Fighter '{fighter_name_input}' not found. Please check spelling or try another name.")
    else:
        with st.spinner(f"Loading fights and details for {fighter_name_input}..."):
            fight_links, main_fights_df = get_fight_links_and_main_data(url)

            all_details = []
            for fl in fight_links:
                row = main_fights_df.loc[main_fights_df['fight_link'] == fl].iloc[0]
                details = parse_fight_details(fl, row['fighter_name'], row['opponent_name'])
                all_details.append(details)

            details_df = pd.DataFrame(all_details)
            combined_df = pd.merge(main_fights_df, details_df, on='fight_link', how='left')
            combined_df = transform_columns(combined_df)
            combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)

            total_rax = combined_df['rax_earned'].sum()
            rarity = st.selectbox("Select Rarity Multiplier", list(RARITY_MULTIPLIERS.keys()), index=0)
            multiplier = RARITY_MULTIPLIERS[rarity]
            adjusted_rax = round(total_rax * multiplier, 1)

            st.markdown(f"### {fighter_name_input.strip()} - Total RAX: {total_rax} (Adjusted: {adjusted_rax} × {rarity})")

            # Add total row
            total_row = pd.DataFrame({
                'fighter_name': [''],
                'opponent_name': [''],
                'result': [''],
                'method_main': ['Total Rax'],
                'rax_earned': [total_rax]
            })

            display_df = pd.concat([
                combined_df[['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']],
                total_row
            ], ignore_index=True)

            st.dataframe(display_df, use_container_width=True)
else:
    st.info("Please enter a fighter's full name above and press Enter.")
