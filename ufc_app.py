import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from difflib import get_close_matches
import sys

# --- Utility functions for scraping and parsing ---

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

def transform_columns(df):
    df.replace('---', np.nan, inplace=True)

    if 'round_x' in df.columns and 'round_y' in df.columns:
        df['round'] = df['round_y'].combine_first(df['round_x'])
        df.drop(columns=['round_x','round_y'], inplace=True)
    if 'Time_x' in df.columns and 'Time_y' in df.columns:
        df['Time'] = df['Time_y'].combine_first(df['Time_x'])
        df.drop(columns=['Time_x','Time_y'], inplace=True)

    if 'method_main_x' in df.columns and 'method_main_y' in df.columns:
        df['method_main'] = df['method_main_y'].combine_first(df['method_main_x'])
        df.drop(columns=['method_main_x','method_main_y'], inplace=True, errors='ignore')
    elif 'method_main_x' in df.columns:
        df.rename(columns={'method_main_x':'method_main'}, inplace=True)
    elif 'method_main_y' in df.columns:
        df.rename(columns={'method_main_y':'method_main'}, inplace=True)

    if 'method_detail_x' in df.columns and 'method_detail_y' in df.columns:
        df['method_detail'] = df['method_detail_y'].combine_first(df['method_detail_x'])
        df.drop(columns=['method_detail_x','method_detail_y'], inplace=True, errors='ignore')
    elif 'method_detail_x' in df.columns:
        df.rename(columns={'method_detail_x':'method_detail'}, inplace=True)
    elif 'method_detail_y' in df.columns:
        df.rename(columns={'method_detail_y':'method_detail'}, inplace=True)

    df = df.astype(str)
    of_cols = [col for col in df.columns if df[col].str.contains(' of ', na=False).any()]

    new_cols = {}
    for col in of_cols:
        split_values = df[col].str.split(' of ', expand=True)
        new_landed_col = col + '_landed'
        new_attempted_col = col + '_attempted'
        new_percentage_col = col + '_percentage'

        landed = pd.to_numeric(split_values[0], errors='coerce')
        attempted = pd.to_numeric(split_values[1], errors='coerce')
        percentage = (landed / attempted) * 100
        percentage = percentage.round(2)

        new_cols[new_landed_col] = landed.astype(str)
        new_cols[new_attempted_col] = attempted.astype(str)
        new_cols[new_percentage_col] = percentage.astype(str)

    if of_cols:
        df.drop(columns=of_cols, inplace=True)

    if new_cols:
        df = pd.concat([df, pd.DataFrame(new_cols)], axis=1)

    for col in df.columns:
        if df[col].str.endswith('%', na=False).any():
            df[col] = df[col].str.replace('%', '', regex=False)

    textual_cols = ['fighter_name','opponent_name','event_name','event_date',
                    'method_main','method_detail','Details','Referee','Event','TimeFormat',
                    'result','fight_link','round']
    for col in df.columns:
        if col not in textual_cols:
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except:
                pass

    float_cols = df.select_dtypes(include=['float64','float32','float'])
    if not float_cols.empty:
        df[float_cols.columns] = float_cols.round(2)

    return df

def calculate_rax(row):
    rax = 0
    # Rule 1: Rax based on method_main
    if row['result'] and row['result'].lower() == 'win':
        method = row['method_main'].upper() if row['method_main'] else ""
        if 'KO' in method or 'TKO' in method:
            rax += 100
        elif 'SUB' in method:
            rax += 90
        elif 'DECISION - UNANIMOUS' in method:
            rax += 80
        elif 'DECISION - MAJORITY' in method:
            rax += 75
        elif 'DECISION - SPLIT' in method:
            rax += 70
    elif row['result'] and row['result'].lower() == 'loss':
        rax += 25

    sig_str_fighter = 0
    sig_str_opponent = 0
    if 'TOT_fighter_SigStr_landed' in row.index and 'TOT_opponent_SigStr_landed' in row.index:
        try:
            sig_str_fighter = float(row['TOT_fighter_SigStr_landed'])
            sig_str_opponent = float(row['TOT_opponent_SigStr_landed'])
        except:
            pass

    if sig_str_fighter > sig_str_opponent:
        rax += (sig_str_fighter - sig_str_opponent)

    if 'TimeFormat' in row.index and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row.index and row['Details'] and 'Fight of the Night' in row['Details']:
        rax += 50

    return round(rax, 2)

# --- Main function ---

def main(fighter_input_name):
    try:
        fighter_url = get_fighter_url_by_name(fighter_input_name)
        print(f"Found URL for {fighter_input_name}: {fighter_url}")
    except ValueError as e:
        print(e)
        sys.exit(1)

    fight_links, main_fights_df = get_fight_links(fighter_url)

    all_fight_details = []
    for fl in fight_links:
        row = main_fights_df.loc[main_fights_df['fight_link'] == fl].iloc[0]
        main_fighter_name = row['fighter_name']
        opp_name = row['opponent_name']
        details = parse_fight_details(fl, main_fighter_name, opp_name)
        all_fight_details.append(details)

    advanced_df = pd.DataFrame(all_fight_details)

    # Before merge, make sure fight_link exists in both dfs
    if 'fight_link' not in main_fights_df.columns or 'fight_link' not in advanced_df.columns:
        raise KeyError("fight_link column missing in one of the dataframes")

    combined_df = pd.merge(main_fights_df, advanced_df, on='fight_link', how='left')

    combined_df = transform_columns(combined_df)

    # Calculate rax earned
    combined_df['rax_earned'] = combined_df.apply(calculate_rax, axis=1)

    # Debug print columns after merge + transform
    print("Columns after merge and transform:", combined_df.columns.tolist())

    # Fix column names if they were merged with _x/_y suffixes
    for col in ['fighter_name', 'opponent_name', 'result', 'method_main']:
        if col not in combined_df.columns:
            for suffix in ['_x', '_y']:
                col_alt = col + suffix
                if col_alt in combined_df.columns:
                    combined_df[col] = combined_df[col_alt]
                    break

    # Confirm columns now exist, else raise error
    required_cols = ['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']
    missing_cols = [c for c in required_cols if c not in combined_df.columns]
    if missing_cols:
        raise KeyError(f"Required columns missing after fix: {missing_cols}")

    # Calculate total rax
    total_rax = combined_df['rax_earned'].sum()

    # Create a total row for display
    total_row = pd.DataFrame({
        'fighter_name': [''],
        'opponent_name': [''],
        'result': [''],
        'method_main': ['Total Rax'],
        'rax_earned': [total_rax]
    })

    final_df = pd.concat([combined_df[required_cols], total_row], ignore_index=True)

    return final_df

# --- Parsing fight details function (reuse as is) ---

def parse_fight_details(fight_url, main_fighter_name, opponent_name):
    response = requests.get(fight_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    fight_data = {}
    event_title = soup.find('h2', class_='b-content__title')
    fight_data['Event'] = event_title.get_text(strip=True) if event_title else None

    details_rows = soup.select('table.b-fight-details__table > tbody > tr')
    for row in details_rows:
        cols = row.find_all('td')
        if len(cols) != 2:
            continue
        key = cols[0].get_text(strip=True)
        val = cols[1].get_text(strip=True)
        fight_data[key] = val

    fighter_tables = soup.select('table.b-fight-details__table_type_total > tbody')
    if len(fighter_tables) >= 2:
        fighter_stats = {}
        for tr in fighter_tables[0].find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) == 2:
                key = tds[0].get_text(strip=True).replace(' ', '_')
                val = tds[1].get_text(strip=True)
                fighter_stats[f'TOT_fighter_{key}'] = val

        opponent_stats = {}
        for tr in fighter_tables[1].find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) == 2:
                key = tds[0].get_text(strip=True).replace(' ', '_')
                val = tds[1].get_text(strip=True)
                opponent_stats[f'TOT_opponent_{key}'] = val

        fight_data.update(fighter_stats)
        fight_data.update(opponent_stats)

    # Additional useful info
    fight_data['fighter_name'] = main_fighter_name
    fight_data['opponent_name'] = opponent_name

    return fight_data

# --- Streamlit UI ---

st.title("UFC Fighter RAX Calculator")

fighter_input_name = st.text_input("Enter UFC Fighter Name:", "Max Holloway")

if fighter_input_name:
    with st.spinner("Fetching data..."):
        df = main(fighter_input_name)
        if df is not None:
            st.dataframe(df)
        else:
            st.error("Error fetching or processing fighter data. Please check the fighter name and try again.")
