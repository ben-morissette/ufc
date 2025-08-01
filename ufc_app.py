import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

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

# Utilities (same as yours)
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

# Scraping funcs (same as yours, omitted here for brevity, just reuse your versions)
# — include your get_fighter_urls(), get_fight_data(), calculate_rax(), generate_leaderboard() here —

# For brevity, I assume these functions are copied exactly from your original code.

# Load or generate leaderboard data
def cache_and_load_leaderboard():
    if cache_is_fresh():
        df = pd.read_csv(CACHE_FILE)
        if 'Rank' in df.columns:
            df.drop(columns=['Rank'], inplace=True)
        if 'Base Rax' not in df.columns and 'Total Rax' in df.columns:
            df.rename(columns={'Total Rax': 'Base Rax'}, inplace=True)
        df['Rarity'] = df.get('Rarity', 'Uncommon')
        df.insert(0, 'Rank', df.index + 1)
        return df
    else:
        df = generate_leaderboard()
        df['Rarity'] = 'Uncommon'
        df.to_csv(CACHE_FILE, index=False)
        df.insert(0, 'Rank', df.index + 1)
        return df

# Main Streamlit app
st.title("UFC Fighter RAX Leaderboard")

leaderboard_df = cache_and_load_leaderboard()

# Prepare ag-Grid options with rarity dropdown in each row
gb = GridOptionsBuilder.from_dataframe(leaderboard_df)
gb.configure_column("Rank", editable=False, width=70)
gb.configure_column("Fighter Name", editable=False, width=200)
gb.configure_column("Fight Count", editable=False, width=110)
gb.configure_column("Base Rax", editable=False, hide=True)

# Configure "Rarity" column as editable dropdown
gb.configure_column(
    "Rarity",
    editable=True,
    cellEditor="agSelectCellEditor",
    cellEditorParams={"values": list(RARITY_MULTIPLIERS.keys())},
    width=140,
)

# Total Rax column, not editable
gb.configure_column("Total Rax", editable=False, width=110, sort="desc")

grid_options = gb.build()

# Initial calculation of Total Rax based on Base Rax and rarity
def recalc_total_rax(df):
    df['Rarity'] = df['Rarity'].fillna('Uncommon')
    df['Total Rax'] = df.apply(
        lambda r: round(r['Base Rax'] * RARITY_MULTIPLIERS.get(r['Rarity'], 1.4), 1), axis=1
    )
    df.sort_values('Total Rax', ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['Rank'] = df.index + 1
    return df

leaderboard_df = recalc_total_rax(leaderboard_df)

# Show the grid with editable rarity dropdown per row
grid_response = AgGrid(
    leaderboard_df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.MODEL_CHANGED,
    allow_unsafe_jscode=True,
    theme="alpine",
    height=600,
    fit_columns_on_grid_load=True,
)

# Get updated data from grid, recalc Total Rax, sort and rank
updated_df = pd.DataFrame(grid_response["data"])
updated_df = recalc_total_rax(updated_df)

st.markdown("### Updated Leaderboard")
st.dataframe(
    updated_df[['Rank', 'Fighter Name', 'Total Rax', 'Rarity', 'Fight Count']],
    use_container_width=True,
)
