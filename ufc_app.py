import sys
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from difflib import get_close_matches

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# --- Fighter search and URL retrieval ---

def search_fighter_by_name_part(query):
    url = "http://ufcstats.com/statistics/fighters/search"
    params = {"query": query}
    response = requests.get(url, params=params)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    if not table:
        return []
    rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
    candidates = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        first_name_col = cols[0].find('a', class_='b-link_style_black')
        last_name_col = cols[1].find('a', class_='b-link_style_black')
        if not first_name_col or not last_name_col:
            continue
        first_name = first_name_col.get_text(strip=True)
        last_name = last_name_col.get_text(strip=True)
        fighter_link = last_name_col['href']
        full_name = f"{first_name} {last_name}".strip()
        candidates.append((full_name, fighter_link))
    return candidates

def get_fighter_url_by_name(fighter_name):
    print(f"\nAttempting to find URL for fighter: {fighter_name}")
    name_parts = fighter_name.strip().split()
    fighter_name_clean = fighter_name.strip().lower()

    if len(name_parts) > 1:
        last_name = name_parts[-1]
        first_name = name_parts[0]
        candidates = search_fighter_by_name_part(last_name)
        if not candidates:
            candidates = search_fighter_by_name_part(first_name)
        if not candidates:
            for part in name_parts:
                candidates = search_fighter_by_name_part(part)
                if candidates:
                    break
        if not candidates:
            raise ValueError(f"No suitable match found for fighter: {fighter_name_clean}")
        all_names = [c[0].lower() for c in candidates]
        close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.0)
        if close:
            best = close[0]
            for c in candidates:
                if c[0].lower() == best:
                    return c[1]
            return candidates[0][1]
        else:
            return candidates[0][1]
    else:
        query = name_parts[0]
        candidates = search_fighter_by_name_part(query)
        if not candidates:
            raise ValueError(f"No suitable match found for fighter: {fighter_name_clean}")
        all_names = [c[0].lower() for c in candidates]
        close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.0)
        if close:
            best = close[0]
            for c in candidates:
                if c[0].lower() == best:
                    return c[1]
            return candidates[0][1]
        else:
            return candidates[0][1]

# --- Get fight links and base data ---

def get_two_values_from_col(col):
    ps = col.find_all('p', class_='b-fight-details__table-text')
    if len(ps) == 2:
        return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
    return None, None

def ctrl_to_seconds(x):
    if x and ':' in x:
        m,s = x.split(':')
        if m.isdigit() and s.isdigit():
            return str(int(m)*60 + int(s))
    return x

def get_fight_links(fighter_url):
    response = requests.get(fighter_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        raise Exception("No fight details table found on the fighter page.")

    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fights_data = []

    for row in rows:
        fight_url = row.get('data-link')
        if not fight_url:
            continue

        cols = row.find_all('td', class_='b-fight-details__table-col')
        result_tag = cols[0].find('p', class_='b-fight-details__table-text')
        result = result_tag.get_text(strip=True) if result_tag else None

        fighter_td = cols[1].find_all('p', class_='b-fight-details__table-text')
        fighter_name = fighter_td[0].get_text(strip=True) if len(fighter_td) > 0 else None
        opponent_name = fighter_td[1].get_text(strip=True) if len(fighter_td) > 1 else None

        kd_fighter, kd_opponent = get_two_values_from_col(cols[2])
        str_fighter, str_opponent = get_two_values_from_col(cols[3])
        td_fighter, td_opponent = get_two_values_from_col(cols[4])
        sub_fighter, sub_opponent = get_two_values_from_col(cols[5])

        event_td = cols[6].find_all('p', class_='b-fight-details__table-text')
        event_name = event_td[0].get_text(strip=True) if len(event_td) > 0 else None
        event_date = event_td[1].get_text(strip=True) if len(event_td) > 1 else None

        method_td = cols[7].find_all('p', class_='b-fight-details__table-text')
        method_main = method_td[0].get_text(strip=True) if len(method_td) > 0 else None
        method_detail = method_td[1].get_text(strip=True) if len(method_td) > 1 else None

        round_val = cols[8].find('p', class_='b-fight-details__table-text')
        round_val = round_val.get_text(strip=True) if round_val else None

        time_val = cols[9].find('p', class_='b-fight-details__table-text')
        time_val = time_val.get_text(strip=True) if time_val else None

        if time_val and ':' in time_val:
            parts = time_val.split(':')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                mm, ss = parts
                total_sec = int(mm)*60 + int(ss)
                time_val = str(total_sec)

        fight_data = {
            'result': result,
            'fighter_name': fighter_name,
            'opponent_name': opponent_name,
            'kd_fighter': kd_fighter,
            'kd_opponent': kd_opponent,
            'str_fighter': str_fighter,
            'str_opponent': str_opponent,
            'td_fighter': td_fighter,
            'td_opponent': td_opponent,
            'sub_fighter': sub_fighter,
            'sub_opponent': sub_opponent,
            'event_name': event_name,
            'event_date': event_date,
            'method_main': method_main,
            'method_detail': method_detail,
            'round': round_val,
            'Time': time_val,
            'fight_link': fight_url
        }

        fights_data.append(fight_data)

    links = [f['fight_link'] for f in fights_data]
    return links, pd.DataFrame(fights_data)

# --- Parse fight advanced stats (totals) ---

def parse_fight_details(fight_url, main_fighter_name, opponent_name):
    response = requests.get(fight_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract "Details" section text (for Fight of the Night bonuses etc)
    details_div = soup.find('div', class_='b-fight-details__fight-description')
    details_text = details_div.get_text(strip=True) if details_div else ""

    # Extract TimeFormat (e.g., '5 Rnd', '3 Rnd')
    time_format = None
    rounds_span = soup.find('span', class_='b-fight-details__rounds')
    if rounds_span:
        time_format = rounds_span.get_text(strip=True)

    # Extract advanced stats from Totals table
    totals_stats = {}

    totals_heading = soup.find('p', class_='b-fight-details__collapse-link_tot', string=lambda x: x and 'Totals' in x)
    if totals_heading:
        totals_section = totals_heading.find_next('section', class_='b-fight-details__section')
        if totals_section:
            totals_table = totals_section.find('table')
            if totals_table:
                rows = totals_table.find('tbody').find_all('tr', class_='b-fight-details__table-row')
                if rows:
                    def get_two_val(cell):
                        ps = cell.find_all('p', class_='b-fight-details__table-text')
                        if len(ps) == 2:
                            return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
                        return None, None
                    # Use first row for fighter/opponent stats
                    cols = rows[0].find_all('td')
                    if len(cols) >= 10:
                        fighter_col = cols[0]
                        fighter1, fighter2 = get_two_val(fighter_col)
                        main_is_first = (main_fighter_name.lower() == fighter1.lower())
                        kd_f1, kd_f2 = get_two_val(cols[1])
                        sig_str_f1, sig_str_f2 = get_two_val(cols[2])
                        sig_str_pct_f1, sig_str_pct_f2 = get_two_val(cols[3])
                        total_str_f1, total_str_f2 = get_two_val(cols[4])
                        td_f1, td_f2 = get_two_val(cols[5])
                        td_pct_f1, td_pct_f2 = get_two_val(cols[6])
                        sub_f1, sub_f2 = get_two_val(cols[7])
                        rev_f1, rev_f2 = get_two_val(cols[8])
                        ctrl_f1, ctrl_f2 = get_two_val(cols[9])

                        ctrl_f1 = ctrl_to_seconds(ctrl_f1)
                        ctrl_f2 = ctrl_to_seconds(ctrl_f2)

                        if main_is_first:
                            totals_stats = {
                                'TOT_fighter_KD': kd_f1,
                                'TOT_opponent_KD': kd_f2,
                                'TOT_fighter_SigStr_landed': int(sig_str_f1) if sig_str_f1 and sig_str_f1.isdigit() else 0,
                                'TOT_opponent_SigStr_landed': int(sig_str_f2) if sig_str_f2 and sig_str_f2.isdigit() else 0,
                                'TOT_fighter_SigStr_pct': sig_str_pct_f1,
                                'TOT_opponent_SigStr_pct': sig_str_pct_f2,
                                'TOT_fighter_Str_landed': int(total_str_f1) if total_str_f1 and total_str_f1.isdigit() else 0,
                                'TOT_opponent_Str_landed': int(total_str_f2) if total_str_f2 and total_str_f2.isdigit() else 0,
                                'TOT_fighter_Td_landed': int(td_f1) if td_f1 and td_f1.isdigit() else 0,
                                'TOT_opponent_Td_landed': int(td_f2) if td_f2 and td_f2.isdigit() else 0,
                                'TOT_fighter_Td_pct': td_pct_f1,
                                'TOT_opponent_Td_pct': td_pct_f2,
                                'TOT_fighter_SubAtt': sub_f1,
                                'TOT_opponent_SubAtt': sub_f2,
                                'TOT_fighter_Rev': rev_f1,
                                'TOT_opponent_Rev': rev_f2,
                                'TOT_fighter_Ctrl': ctrl_f1,
                                'TOT_opponent_Ctrl': ctrl_f2,
                            }
                        else:
                            totals_stats = {
                                'TOT_fighter_KD': kd_f2,
                                'TOT_opponent_KD': kd_f1,
                                'TOT_fighter_SigStr_landed': int(sig_str_f2) if sig_str_f2 and sig_str_f2.isdigit() else 0,
                                'TOT_opponent_SigStr_landed': int(sig_str_f1) if sig_str_f1 and sig_str_f1.isdigit() else 0,
                                'TOT_fighter_SigStr_pct': sig_str_pct_f2,
                                'TOT_opponent_SigStr_pct': sig_str_pct_f1,
                                'TOT_fighter_Str_landed': int(total_str_f2) if total_str_f2 and total_str_f2.isdigit() else 0,
                                'TOT_opponent_Str_landed': int(total_str_f1) if total_str_f1 and total_str_f1.isdigit() else 0,
                                'TOT_fighter_Td_landed': int(td_f2) if td_f2 and td_f2.isdigit() else 0,
                                'TOT_opponent_Td_landed': int(td_f1) if td_f1 and td_f1.isdigit() else 0,
                                'TOT_fighter_Td_pct': td_pct_f2,
                                'TOT_opponent_Td_pct': td_pct_f1,
                                'TOT_fighter_SubAtt': sub_f2,
                                'TOT_opponent_SubAtt': sub_f1,
                                'TOT_fighter_Rev': rev_f2,
                                'TOT_opponent_Rev': rev_f1,
                                'TOT_fighter_Ctrl': ctrl_f2,
                                'TOT_opponent_Ctrl': ctrl_f1,
                            }
    totals_stats['Details'] = details_text
    totals_stats['TimeFormat'] = time_format

    return totals_stats

# --- RAX calculation function ---

def calculate_rax(row):
    rax = 0
    # Rule 1: Rax based on method_main and result
    if row['result'] == 'win':
        method = row['method_main']
        if method == 'KO/TKO':
            rax += 100
        elif method == 'Submission':
            rax += 90
        elif method == 'Decision - Unanimous':
            rax += 80
        elif method == 'Decision - Majority':
            rax += 75
        elif method == 'Decision - Split':
            rax += 70
        elif method == 'DQ':
            rax += 50
        else:
            rax += 60  # Default for other wins
    elif row['result'] == 'loss':
        rax += 25

    # Rule 2: Rax based on significant strike difference
    sig_str_fighter = row.get('TOT_fighter_SigStr_landed', 0) or 0
    sig_str_opponent = row.get('TOT_opponent_SigStr_landed', 0) or 0

    if isinstance(sig_str_fighter, str) and sig_str_fighter.isdigit():
        sig_str_fighter = int(sig_str_fighter)
    if isinstance(sig_str_opponent, str) and sig_str_opponent.isdigit():
        sig_str_opponent = int(sig_str_opponent)

    if sig_str_fighter > sig_str_opponent:
        rax += (sig_str_fighter - sig_str_opponent)

    # Rule 3: Bonus for 5-round fights
    if 'TimeFormat' in row and row['TimeFormat'] and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Details' in row and row['Details'] and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# --- Main process ---

def main(fighter_input_name):
    try:
        fighter_url = get_fighter_url_by_name(fighter_input_name)
        print(f"Found URL for {fighter_input_name}: {fighter_url}")
    except ValueError as e:
        print(e)
        sys.exit(1)

    fight_links, main_fights_df = get_fight_links(fighter_url)
    if main_fights_df.empty:
        print(f"No fights found for {fighter_input_name}.")
        sys.exit(1)

    all_fight_details = []
    for fl in fight_links:
        row = main_fights_df.loc[main_fights_df['fight_link'] == fl].iloc[0]
        main_fighter_name = row['fighter_name']
        opp_name = row['opponent_name']
        details = parse_fight_details(fl, main_fighter_name, opp_name)
        all_fight_details.append(details)

    advanced_df = pd.DataFrame(all_fight_details)
    combined_df = pd.merge(main_fights_df, advanced_df, on='fight_link', how='left')

    combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)

    # Calculate total rax
    total_rax = combined_df['rax_earned'].sum()

    # Create a new row for the total
    total_row = pd.DataFrame({
        'fighter_name': [''],
        'opponent_name': [''],
        'result': [''],
        'method_main': ['Total Rax'],
        'rax_earned': [total_rax]
    })

    # Append the total row to the DataFrame
    final_df = pd.concat([combined_df[['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']], total_row], ignore_index=True)

    return final_df

# --- Run and display ---

if __name__ == "__main__":
    fighter_input_name = "Max Holloway"  # Change this name as needed
    df = main(fighter_input_name)
    print(df)
