import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from difflib import get_close_matches

# --- Fighter Search Helpers ---

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

# --- Fight Data Scraping ---

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

        # Convert time_val to seconds if mm:ss
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

def parse_totals_table(soup, main_fighter_name):
    totals_heading = soup.find('p', class_='b-fight-details__collapse-link_tot', string=lambda x: x and 'Totals' in x)
    if not totals_heading:
        return {}
    totals_section = totals_heading.find_next('section', class_='b-fight-details__section')
    if not totals_section:
        return {}
    totals_table = totals_section.find('table')
    if not totals_table:
        return {}

    rows = totals_table.find('tbody').find_all('tr', class_='b-fight-details__table-row')
    if len(rows) == 0:
        return {}

    def get_two_val(cell):
        ps = cell.find_all('p', class_='b-fight-details__table-text')
        if len(ps) == 2:
            return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
        return None, None

    first_row = rows[0]
    cols = first_row.find_all('td')
    if len(cols) < 10:
        return {}

    fighter_col = cols[0]
    fighter1, fighter2 = get_two_val(fighter_col)
    if fighter1 is None or fighter2 is None:
        return {}

    main_is_first = (main_fighter_name.lower() == fighter1.lower())

    kd_f1, kd_f2 = get_two_val(cols[1])
    str_f1, str_f2 = get_two_val(cols[2])
    str_pct_f1, str_pct_f2 = get_two_val(cols[3])
    total_str_f1, total_str_f2 = get_two_val(cols[4])
    td_f1, td_f2 = get_two_val(cols[5])
    td_pct_f1, td_pct_f2 = get_two_val(cols[6])
    sub_f1, sub_f2 = get_two_val(cols[7])
    rev_f1, rev_f2 = get_two_val(cols[8])
    ctrl_f1, ctrl_f2 = get_two_val(cols[9])

    ctrl_f1 = ctrl_to_seconds(ctrl_f1)
    ctrl_f2 = ctrl_to_seconds(ctrl_f2)

    data = {}
    if main_is_first:
        data['TOT_fighter_KD'] = kd_f1
        data['TOT_opponent_KD'] = kd_f2
        data['TOT_fighter_SigStr'] = str_f1
        data['TOT_opponent_SigStr'] = str_f2
        data['TOT_fighter_SigStr_pct'] = str_pct_f1
        data['TOT_opponent_SigStr_pct'] = str_pct_f2
        data['TOT_fighter_Str'] = total_str_f1
        data['TOT_opponent_Str'] = total_str_f2
        data['TOT_fighter_Td'] = td_f1
        data['TOT_opponent_Td'] = td_f2
        data['TOT_fighter_Td_pct'] = td_pct_f1
        data['TOT_opponent_Td_pct'] = td_pct_f2
        data['TOT_fighter_SubAtt'] = sub_f1
        data['TOT_opponent_SubAtt'] = sub_f2
        data['TOT_fighter_Rev'] = rev_f1
        data['TOT_opponent_Rev'] = rev_f2
        data['TOT_fighter_Ctrl'] = ctrl_f1
        data['TOT_opponent_Ctrl'] = ctrl_f2
    else:
        data['TOT_fighter_KD'] = kd_f2
        data['TOT_opponent_KD'] = kd_f1
        data['TOT_fighter_SigStr'] = str_f2
        data['TOT_opponent_SigStr'] = str_f1
        data['TOT_fighter_SigStr_pct'] = str_pct_f2
        data['TOT_opponent_SigStr_pct'] = str_pct_f1
        data['TOT_fighter_Str'] = total_str_f2
        data['TOT_opponent_Str'] = total_str_f1
        data['TOT_fighter_Td'] = td_f2
        data['TOT_opponent_Td'] = td_f1
        data['TOT_fighter_Td_pct'] = td_pct_f2
        data['TOT_opponent_Td_pct'] = td_pct_f1
        data['TOT_fighter_SubAtt'] = sub_f2
        data['TOT_opponent_SubAtt'] = sub_f1
        data['TOT_fighter_Rev'] = rev_f2
        data['TOT_opponent_Rev'] = rev_f1
        data['TOT_fighter_Ctrl'] = ctrl_f2
        data['TOT_opponent_Ctrl'] = ctrl_f1

    return data

def parse_per_round_totals(soup, main_fighter_name):
    totals_heading = soup.find('p', class_='b-fight-details__collapse-link_tot', string=lambda x: x and 'Totals' in x)
    if not totals_heading:
        return {}
    per_round_link = totals_heading.find_next('a', class_='b-fight-details__collapse-link_rnd', string=lambda x: x and 'Per round' in x)
    if not per_round_link:
        return {}
    per_round_table = per_round_link.find_next('table', class_='b-fight-details__table')
    if not per_round_table:
        return {}

    def get_two_vals_from_cell(cell):
        ps = cell.find_all('p', class_='b-fight-details__table-text')
        if len(ps) == 2:
            return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
        return None, None

    round_headers = per_round_table.find_all('thead', class_='b-fight-details__table-row_type_head')
    if not round_headers:
        return {}
    first_header = round_headers[0]
    first_data_row = first_header.find_next('tr', class_='b-fight-details__table-row')
    if not first_data_row:
        return {}
    first_cells = first_data_row.find_all('td', class_='b-fight-details__table-col')
    if len(first_cells) < 9:
        return {}

    first_f1_name, first_f2_name = get_two_vals_from_cell(first_cells[0])
    if not first_f1_name or first_f2_name is None:
        return {}

    main_is_first = (main_fighter_name.lower() == first_f1_name.lower())

    data = {}
    for rh in round_headers:
        round_name = rh.get_text(strip=True).replace('Round ', '')
        data_row = rh.find_next('tr', class_='b-fight-details__table-row')
        if not data_row:
            continue
        cells = data_row.find_all('td', class_='b-fight-details__table-col')
        if len(cells) < 9:
            continue

        kd = get_two_vals_from_cell(cells[1])
        sig_str = get_two_vals_from_cell(cells[2])
        sig_str_pct = get_two_vals_from_cell(cells[3])
        total_str = get_two_vals_from_cell(cells[4])
        td_pct = get_two_vals_from_cell(cells[5])
        sub_att = get_two_vals_from_cell(cells[6])
        rev = get_two_vals_from_cell(cells[7])
        ctrl = get_two_vals_from_cell(cells[8])

        if ctrl is not None:
            ctrl_f1, ctrl_f2 = ctrl
            ctrl_f1 = ctrl_to_seconds(ctrl_f1)
            ctrl_f2 = ctrl_to_seconds(ctrl_f2)
        else:
            ctrl_f1, ctrl_f2 = None, None

        def assign_vals(val_pair):
            if val_pair is None:
                return None, None
            v1, v2 = val_pair
            return (v1, v2)

        kd_f1, kd_f2 = assign_vals(kd)
        sig_str_f1, sig_str_f2 = assign_vals(sig_str)
        sig_str_pct_f1, sig_str_pct_f2 = assign_vals(sig_str_pct)
        total_str_f1, total_str_f2 = assign_vals(total_str)
        td_pct_f1, td_pct_f2 = assign_vals(td_pct)
        sub_att_f1, sub_att_f2 = assign_vals(sub_att)
        rev_f1, rev_f2 = assign_vals(rev)

        if main_is_first:
            data[f'Rnd{round_name}_fighter_KD'] = kd_f1
            data[f'Rnd{round_name}_opponent_KD'] = kd_f2
            data[f'Rnd{round_name}_fighter_SigStr'] = sig_str_f1
            data[f'Rnd{round_name}_opponent_SigStr'] = sig_str_f2
            data[f'Rnd{round_name}_fighter_SigStr_pct'] = sig_str_pct_f1
            data[f'Rnd{round_name}_opponent_SigStr_pct'] = sig_str_pct_f2
            data[f'Rnd{round_name}_fighter_Str'] = total_str_f1
            data[f'Rnd{round_name}_opponent_Str'] = total_str_f2
            data[f'Rnd{round_name}_fighter_Td_pct'] = td_pct_f1
            data[f'Rnd{round_name}_opponent_Td_pct'] = td_pct_f2
            data[f'Rnd{round_name}_fighter_SubAtt'] = sub_att_f1
            data[f'Rnd{round_name}_opponent_SubAtt'] = sub_att_f2
            data[f'Rnd{round_name}_fighter_Rev'] = rev_f1
            data[f'Rnd{round_name}_opponent_Rev'] = rev_f2
            data[f'Rnd{round_name}_fighter_Ctrl'] = ctrl_f1
            data[f'Rnd{round_name}_opponent_Ctrl'] = ctrl_f2
        else:
            data[f'Rnd{round_name}_fighter_KD'] = kd_f2
            data[f'Rnd{round_name}_opponent_KD'] = kd_f1
            data[f'Rnd{round_name}_fighter_SigStr'] = sig_str_f2
            data[f'Rnd{round_name}_opponent_SigStr'] = sig_str_f1
            data[f'Rnd{round_name}_fighter_SigStr_pct'] = sig_str_pct_f2
            data[f'Rnd{round_name}_opponent_SigStr_pct'] = sig_str_pct_f1
            data[f'Rnd{round_name}_fighter_Str'] = total_str_f2
            data[f'Rnd{round_name}_opponent_Str'] = total_str_f1
            data[f'Rnd{round_name}_fighter_Td_pct'] = td_pct_f2
            data[f'Rnd{round_name}_opponent_Td_pct'] = td_pct_f1
            data[f'Rnd{round_name}_fighter_SubAtt'] = sub_att_f2
            data[f'Rnd{round_name}_opponent_SubAtt'] = sub_att_f1
            data[f'Rnd{round_name}_fighter_Rev'] = rev_f2
            data[f'Rnd{round_name}_opponent_Rev'] = rev_f1
            data[f'Rnd{round_name}_fighter_Ctrl'] = ctrl_f2
            data[f'Rnd{round_name}_opponent_Ctrl'] = ctrl_f1

    return data

def parse_fight_details(fight_link, main_fighter_name, opponent_name):
    response = requests.get(fight_link)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    # Parse totals
    totals_data = parse_totals_table(soup, main_fighter_name)
    # Parse per round totals
    per_round_data = parse_per_round_totals(soup, main_fighter_name)

    # Get Details (Fight of the Night, etc)
    details_tag = soup.find('p', class_='b-fight-details__text')
    details = details_tag.get_text(strip=True) if details_tag else ''

    # Get TimeFormat (e.g. "5 Rnd")
    timeformat_tag = soup.find('p', class_='b-fight-details__text_time-format')
    timeformat = timeformat_tag.get_text(strip=True) if timeformat_tag else ''

    # Merge all details into a dict
    fight_details = {
        'Details': details,
        'TimeFormat': timeformat,
        'fighter_name': main_fighter_name,
        'opponent_name': opponent_name,
        'fight_link': fight_link,
    }
    fight_details.update(totals_data)
    fight_details.update(per_round_data)
    return fight_details

def transform_columns(df):
    # You can add any needed cleaning or transforming here
    # For example, convert rax columns to numeric if needed
    return df

def calculate_rax(row):
    rax = 0
    if row.get('result') == 'win':
        if row.get('method_main') == 'KO/TKO':
            rax += 100
        elif row.get('method_main') == 'Submission':
            rax += 90
        elif row.get('method_main') == 'Decision - Unanimous':
            rax += 80
        elif row.get('method_main') == 'Decision - Majority':
            rax += 75
        elif row.get('method_main') == 'Decision - Split':
            rax += 70
    elif row.get('result') == 'loss':
        rax += 25

    sig_str_fighter = 0
    sig_str_opponent = 0
    if 'TOT_fighter_SigStr' in row and 'TOT_opponent_SigStr' in row:
        try:
            sig_str_fighter = float(row['TOT_fighter_SigStr'])
            sig_str_opponent = float(row['TOT_opponent_SigStr'])
        except:
            pass

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    if 'TimeFormat' in row and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    if 'Details' in row and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax

# --- Streamlit UI ---

st.title("UFC Fighter RAX Calculator")

fighter_input_name = st.text_input("Enter UFC Fighter Name:", value="Max Holloway")

if fighter_input_name:
    try:
        with st.spinner("Searching fighter URL..."):
            fighter_url = get_fighter_url_by_name(fighter_input_name)
            st.success(f"Found URL for {fighter_input_name}: {fighter_url}")

        with st.spinner("Loading fights..."):
            fight_links, main_fights_df = get_fight_links(fighter_url)

        all_fight_details = []
        with st.spinner("Loading detailed fight stats..."):
            for fl in fight_links:
                row = main_fights_df.loc[main_fights_df['fight_link'] == fl].iloc[0]
                main_fighter_name = row['fighter_name']
                opp_name = row['opponent_name']
                details = parse_fight_details(fl, main_fighter_name, opp_name)
                details['fighter_name'] = main_fighter_name
                details['opponent_name'] = opp_name
                details['fight_link'] = fl
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

        display_cols = ['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']
        for col in display_cols:
            if col not in combined_df.columns:
                combined_df[col] = ""

        final_df = pd.concat([
            combined_df[display_cols],
            total_row
        ], ignore_index=True)

        st.dataframe(final_df)

    except Exception as e:
        st.error(f"Error: {e}")
        st.warning("Please check the fighter name and try again.")
