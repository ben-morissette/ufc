import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode

CACHE_FILE = 'ufc_rax_leaderboard.csv'
FIGHTER_LIMIT = 10
RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

# ------------- Utility & Scraper functions -------------
def get_last_tuesday(reference_date=None):
    if reference_date is None:
        reference_date = datetime.now()
    days_since_tuesday = (reference_date.weekday() - 1) % 7
    return reference_date - timedelta(days=days_since_tuesday)

def cache_is_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    return mod_time >= get_last_tuesday()

def get_fighter_urls():
    url = "http://ufcstats.com/statistics/fighters"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
    urls = []
    for row in rows:
        link = row.find_all('td')[0].find('a', class_='b-link_style_black')
        if link and link.has_attr('href'):
            urls.append(link['href'])
    return urls[:FIGHTER_LIMIT]

def get_two_values_from_col(col):
    ps = col.find_all('p', class_='b-fight-details__table-text')
    return (ps[0].get_text(strip=True), ps[1].get_text(strip=True)) if len(ps) == 2 else (None, None)

def get_fight_data(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        return pd.DataFrame()
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fights = []
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        result = cols[0].find('p').get_text(strip=True).lower()
        fighter_name = cols[1].find_all('p')[0].get_text(strip=True)
        opponent_name = cols[1].find_all('p')[1].get_text(strip=True)
        kd_f, kd_o = get_two_values_from_col(cols[2])
        str_f, str_o = get_two_values_from_col(cols[3])
        td_f, td_o = get_two_values_from_col(cols[4])
        sub_f, sub_o = get_two_values_from_col(cols[5])
        event_name = cols[6].find_all('p')[0].get_text(strip=True)
        method = cols[7].find_all('p')[0].get_text(strip=True)
        round_val = cols[8].find('p').get_text(strip=True)
        fights.append({
            'Result': result,
            'Fighter Name': fighter_name,
            'Opponent Name': opponent_name,
            'KD Fighter': kd_f,
            'KD Opponent': kd_o,
            'Strikes Fighter': str_f,
            'Strikes Opponent': str_o,
            'Takedowns Fighter': td_f,
            'Takedowns Opponent': td_o,
            'Submission Attempts Fighter': sub_f,
            'Submission Attempts Opponent': sub_o,
            'Event Name': event_name,
            'Method Main': method,
            'Round': round_val,
        })
    return pd.DataFrame(fights)

def calculate_rax(row):
    rax = 0
    if row['Result'] == 'win':
        method = row['Method Main']
        if method == 'KO/TKO':
            rax += 100
        elif method in ['Submission', 'SUB']:
            rax += 90
        elif method in ['Decision - Unanimous', 'U-DEC']:
            rax += 80
        elif method == 'Decision - Majority':
            rax += 75
        elif method == 'Decision - Split':
            rax += 70
    elif row['Result'] == 'loss':
        rax += 25
    try:
        strike_diff = int(row['Strikes Fighter']) - int(row['Strikes Opponent'])
        if strike_diff > 0:
            rax += strike_diff
    except:
        pass
    if row['Round'] == '5':
        rax += 25
    ev = row['Event Name'].lower()
    if 'fight of the night' in ev or 'fight of night' in ev:
        rax += 50
    if 'championship' in ev:
        rax += 25
    return rax

def generate_leaderboard():
    fighter_urls = get_fighter_urls()
    leaderboard = []
    for url in fighter_urls:
        try:
            fights_df = get_fight_data(url)
            if fights_df.empty:
                continue
            fights_df['Rax Earned'] = fights_df.apply(calculate_rax, axis=1)
            total_rax = fights_df['Rax Earned'].sum()
            name = fights_df.iloc[0]['Fighter Name']
            leaderboard.append({
                'Fighter Name': name,
                'Base Rax': total_rax,
                'Fight Count': len(fights_df),
                'Rarity': 'Uncommon',
            })
        except:
            continue
    df = pd.DataFrame(leaderboard)
    df = df.sort_values(by='Base Rax', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rank', df.index + 1)
    return df

highlight_top_3 = JsCode("""
    function(params) {
        if (params.node.rowIndex === 0) {
            return 'top1';
        } else if (params.node.rowIndex === 1) {
            return 'top2';
        } else if (params.node.rowIndex === 2) {
            return 'top3';
        }
        return '';
    }
""")

def main():
    st.set_page_config(page_title="UFC RAX Leaderboard", layout="wide")
    st.title("🏆 UFC Fighter RAX Leaderboard")

    if cache_is_fresh():
        leaderboard_df = pd.read_csv(CACHE_FILE)
        if 'Rank' in leaderboard_df.columns:
            leaderboard_df.drop(columns=['Rank'], inplace=True)
        leaderboard_df.insert(0, 'Rank', leaderboard_df.index + 1)
        leaderboard_df['Rarity'] = 'Uncommon'
        leaderboard_df.rename(columns={'Total Rax': 'Base Rax'}, inplace=True, errors='ignore')
    else:
        leaderboard_df = generate_leaderboard()
        leaderboard_df.to_csv(CACHE_FILE, index=False)

    # Calculate initial Total Rax column (Base Rax * default rarity multiplier)
    leaderboard_df['Total Rax'] = (leaderboard_df['Base Rax'] * RARITY_MULTIPLIERS['Uncommon']).round(1)

    gb = GridOptionsBuilder.from_dataframe(leaderboard_df)

    gb.configure_column("Rank", editable=False, width=70, cellClass='rank-cell', sortable=True)
    gb.configure_column("Fighter Name", editable=False, width=200)
    gb.configure_column("Fight Count", editable=False, width=110)
    gb.configure_column("Base Rax", editable=False, hide=True)  # internal use only
    gb.configure_column(
        "Rarity",
        editable=True,
        cellEditor='agSelectCellEditor',
        cellEditorParams={'values': list(RARITY_MULTIPLIERS.keys())},
        width=130,
    )
    gb.configure_column("Total Rax", editable=False, width=110, sort='desc')

    gb.configure_grid_options(getRowClass=highlight_top_3)

    grid_options = gb.build()

    grid_response = AgGrid(
        leaderboard_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=True,
        theme='alpine',
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        height=600,
    )

    updated_df = pd.DataFrame(grid_response['data'])

    # Recalculate Total Rax live based on rarity change - **IMPORTANT: no trailing comma here!**
    updated_df['Total Rax'] = updated_df.apply(
        lambda row: round(row['Base Rax'] * RARITY_MULTIPLIERS.get(row['Rarity'], 1.4), 1),
        axis=1,
    )

    # Sort by Total Rax descending and re-rank
    updated_df = updated_df.sort_values('Total Rax', ascending=False).reset_index(drop=True)
    updated_df['Rank'] = updated_df.index + 1

    st.markdown("### Adjusted RAX Leaderboard (Sorted by Total Rax)")
    st.dataframe(
        updated_df[['Rank', 'Fighter Name', 'Total Rax', 'Rarity', 'Fight Count']],
        use_container_width=True,
        height=600,
    )

    # Custom CSS for top rank highlights
    st.markdown(
        """
        <style>
        .ag-row.top1 .ag-cell {
            background-color: gold !important;
            font-weight: bold;
        }
        .ag-row.top2 .ag-cell {
            background-color: silver !important;
            font-weight: bold;
        }
        .ag-row.top3 .ag-cell {
            background-color: #cd7f32 !important; /* bronze */
            font-weight: bold;
        }
        .rank-cell {
            text-align: center !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
