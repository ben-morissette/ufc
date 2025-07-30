import requests
from bs4 import BeautifulSoup
from difflib import get_close_matches
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

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
    sub_att_f1, sub_att_f2 = get_two_val(cols[7])
    pass_f1, pass_f2 = get_two_val(cols[8])
    rev_f1, rev_f2 = get_two_val(cols[9])

    def parse_pct(pct):
        return float(pct.strip('%')) if pct and pct.endswith('%') else None

    data = {}
    if main_is_first:
        data = {
            'kd': int(kd_f1) if kd_f1 and kd_f1.isdigit() else None,
            'strikes': int(str_f1) if str_f1 and str_f1.isdigit() else None,
            'str_pct': parse_pct(str_pct_f1),
            'total_strikes': int(total_str_f1) if total_str_f1 and total_str_f1.isdigit() else None,
            'td': int(td_f1) if td_f1 and td_f1.isdigit() else None,
            'td_pct': parse_pct(td_pct_f1),
            'sub_att': int(sub_att_f1) if sub_att_f1 and sub_att_f1.isdigit() else None,
            'pass': int(pass_f1) if pass_f1 and pass_f1.isdigit() else None,
            'rev': int(rev_f1) if rev_f1 and rev_f1.isdigit() else None,
        }
    else:
        data = {
            'kd': int(kd_f2) if kd_f2 and kd_f2.isdigit() else None,
            'strikes': int(str_f2) if str_f2 and str_f2.isdigit() else None,
            'str_pct': parse_pct(str_pct_f2),
            'total_strikes': int(total_str_f2) if total_str_f2 and total_str_f2.isdigit() else None,
            'td': int(td_f2) if td_f2 and td_f2.isdigit() else None,
            'td_pct': parse_pct(td_pct_f2),
            'sub_att': int(sub_att_f2) if sub_att_f2 and sub_att_f2.isdigit() else None,
            'pass': int(pass_f2) if pass_f2 and pass_f2.isdigit() else None,
            'rev': int(rev_f2) if rev_f2 and rev_f2.isdigit() else None,
        }
    return data

def parse_rounds_table(soup, main_fighter_name):
    rounds_heading = soup.find('p', class_='b-fight-details__collapse-link', string=lambda x: x and 'Round' in x)
    if not rounds_heading:
        return []
    rounds_section = rounds_heading.find_next('section', class_='b-fight-details__section')
    if not rounds_section:
        return []

    rounds_table = rounds_section.find('table')
    if not rounds_table:
        return []

    rows = rounds_table.find('tbody').find_all('tr', class_='b-fight-details__table-row')
    if not rows:
        return []

    def get_two_val(cell):
        ps = cell.find_all('p', class_='b-fight-details__table-text')
        if len(ps) == 2:
            return ps[0].get_text(strip=True), ps[1].get_text(strip=True)
        return None, None

    round_stats = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 10:
            continue
        round_num = cols[0].get_text(strip=True)
        fighter_col = cols[1]
        fighter1, fighter2 = get_two_val(fighter_col)
        main_is_first = (main_fighter_name.lower() == fighter1.lower()) if fighter1 and fighter2 else True

        kd_f1, kd_f2 = get_two_val(cols[2])
        str_f1, str_f2 = get_two_val(cols[3])
        str_pct_f1, str_pct_f2 = get_two_val(cols[4])
        td_f1, td_f2 = get_two_val(cols[5])
        td_pct_f1, td_pct_f2 = get_two_val(cols[6])
        sub_att_f1, sub_att_f2 = get_two_val(cols[7])
        pass_f1, pass_f2 = get_two_val(cols[8])
        rev_f1, rev_f2 = get_two_val(cols[9])

        def parse_pct(pct):
            return float(pct.strip('%')) if pct and pct.endswith('%') else None

        data = {}
        if main_is_first:
            data = {
                'round': int(round_num) if round_num.isdigit() else round_num,
                'kd': int(kd_f1) if kd_f1 and kd_f1.isdigit() else None,
                'strikes': int(str_f1) if str_f1 and str_f1.isdigit() else None,
                'str_pct': parse_pct(str_pct_f1),
                'td': int(td_f1) if td_f1 and td_f1.isdigit() else None,
                'td_pct': parse_pct(td_pct_f1),
                'sub_att': int(sub_att_f1) if sub_att_f1 and sub_att_f1.isdigit() else None,
                'pass': int(pass_f1) if pass_f1 and pass_f1.isdigit() else None,
                'rev': int(rev_f1) if rev_f1 and rev_f1.isdigit() else None,
            }
        else:
            data = {
                'round': int(round_num) if round_num.isdigit() else round_num,
                'kd': int(kd_f2) if kd_f2 and kd_f2.isdigit() else None,
                'strikes': int(str_f2) if str_f2 and str_f2.isdigit() else None,
                'str_pct': parse_pct(str_pct_f2),
                'td': int(td_f2) if td_f2 and td_f2.isdigit() else None,
                'td_pct': parse_pct(td_pct_f2),
                'sub_att': int(sub_att_f2) if sub_att_f2 and sub_att_f2.isdigit() else None,
                'pass': int(pass_f2) if pass_f2 and pass_f2.isdigit() else None,
                'rev': int(rev_f2) if rev_f2 and rev_f2.isdigit() else None,
            }
        round_stats.append(data)

    return round_stats

def get_fight_stats(fight_url, main_fighter_name):
    response = requests.get(fight_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    totals_data = parse_totals_table(soup, main_fighter_name)
    rounds_data = parse_rounds_table(soup, main_fighter_name)
    return totals_data, rounds_data


if __name__ == '__main__':
    # Example usage:
    try:
        fighter_name = "Khabib Nurmagomedov"
        fighter_url = get_fighter_url_by_name(fighter_name)
        print(f"Fighter URL: {fighter_url}")

        fight_links, fights_df = get_fight_links(fighter_url)
        print(f"Found {len(fight_links)} fights for {fighter_name}")

        if fight_links:
            first_fight_url = fight_links[0]
            print(f"Getting stats for fight: {first_fight_url}")
            totals, rounds = get_fight_stats(first_fight_url, fighter_name)
            print("Totals stats:")
            print(totals)
            print("\nRounds stats:")
            for r in rounds:
                print(r)
    except Exception as e:
        print("Error:", e)
