import streamlit as st
import pandas as pd
import os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

CACHE_FILE = "ufc_rax_leaderboard.csv"

RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

def cache_is_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    # Simplified freshness check for demo
    return True

def load_leaderboard():
    # For this example, just load CSV, ensure columns exist
    df = pd.read_csv(CACHE_FILE)
    if 'Rarity' not in df.columns:
        df['Rarity'] = 'Uncommon'
    # Make sure all Rax rarity columns exist:
    for rarity in RARITY_MULTIPLIERS.keys():
        col_name = f"Rax_{rarity}"
        if col_name not in df.columns:
            df[col_name] = df['Base Rax'] * RARITY_MULTIPLIERS[rarity]
    return df

def calculate_total_rax(df):
    # Use row-wise apply with getattr-like access to rarities
    def get_total_rax(row):
        rarity = row['Rarity']
        col_name = f"Rax_{rarity}"
        return row[col_name]
    df['Total Rax'] = df.apply(get_total_rax, axis=1)
    return df

def main():
    st.set_page_config(layout="wide")
    st.title("UFC Fighter RAX Leaderboard with Editable Rarity")

    df = load_leaderboard()

    # AgGrid setup
    gb = GridOptionsBuilder.from_dataframe(df)

    # Configure columns:
    gb.configure_column("Rank", header_name="Rank", sortable=True, filter=True, width=70)
    gb.configure_column("Fighter Name", header_name="Fighter Name", sortable=True, filter=True, width=250)
    gb.configure_column("Base Rax", header_name="Base Rax", sortable=True, filter=True, width=100)
    gb.configure_column("Total Rax", header_name="Total Rax", sortable=True, filter=True, width=120)
    
    # Rarity as editable dropdown
    gb.configure_column(
        "Rarity",
        header_name="Rarity",
        editable=True,
        cellEditor='agSelectCellEditor',
        cellEditorParams={'values': list(RARITY_MULTIPLIERS.keys())},
        width=140,
        filter=True,
    )

    grid_options = gb.build()

    # Show the grid, enable editing
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False,
        height=600,
        reload_data=False,
    )

    updated_df = pd.DataFrame(grid_response['data'])

    # Calculate Total Rax based on updated rarity selections
    updated_df = calculate_total_rax(updated_df)

    # Sort by Total Rax descending
    updated_df = updated_df.sort_values(by='Total Rax', ascending=False).reset_index(drop=True)
    updated_df.insert(0, 'Rank', updated_df.index + 1)

    st.markdown("### Updated Leaderboard (sorted by Total Rax)")
    st.dataframe(updated_df[['Rank', 'Fighter Name', 'Total Rax', 'Rarity']], use_container_width=True)

if __name__ == "__main__":
    main()
