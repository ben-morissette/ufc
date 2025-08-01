import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode

# Sample static data simulating UFC fighters leaderboard
# Replace with your scraping code or API data
data = [
    {"Rank": 1, "Fighter Name": "Conor McGregor", "Base Rax": 1500, "Fight Count": 30, "Rarity": "Uncommon"},
    {"Rank": 2, "Fighter Name": "Israel Adesanya", "Base Rax": 1400, "Fight Count": 25, "Rarity": "Uncommon"},
    {"Rank": 3, "Fighter Name": "Amanda Nunes", "Base Rax": 1350, "Fight Count": 28, "Rarity": "Uncommon"},
    {"Rank": 4, "Fighter Name": "Jon Jones", "Base Rax": 1300, "Fight Count": 26, "Rarity": "Uncommon"},
    {"Rank": 5, "Fighter Name": "Valentina Shevchenko", "Base Rax": 1250, "Fight Count": 29, "Rarity": "Uncommon"},
]

RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

df = pd.DataFrame(data)
df["Total Rax"] = df["Base Rax"] * RARITY_MULTIPLIERS["Uncommon"]

highlight_top_3 = JsCode("""
function(params) {
    if (params.node.rowIndex === 0) return 'top1';
    if (params.node.rowIndex === 1) return 'top2';
    if (params.node.rowIndex === 2) return 'top3';
    return '';
}
""")

st.markdown(
    """
    <style>
    .css-1d391kg { max-width: 900px !important; margin: auto; }
    .title { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 2.5rem; font-weight: 700; margin-bottom: 1rem; text-align: center; }
    .ag-row.top1 .ag-cell { background-color: #FFD700 !important; font-weight: 700 !important; color: black !important; }
    .ag-row.top2 .ag-cell { background-color: #C0C0C0 !important; font-weight: 700 !important; color: black !important; }
    .ag-row.top3 .ag-cell { background-color: #cd7f32 !important; font-weight: 700 !important; color: black !important; }
    .rank-cell { text-align: center !important; font-weight: 600; }
    .ag-header { background-color: #f0f0f0 !important; font-weight: 600 !important; font-size: 1.1rem !important; }
    .ag-row:hover { background-color: #eef6f9 !important; }
    .ag-cell-editable { background-color: #fef9f9 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">🏆 UFC Fighter RAX Leaderboard</div>', unsafe_allow_html=True)

gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_column("Rank", editable=False, width=70, cellClass="rank-cell", sortable=True)
gb.configure_column("Fighter Name", editable=False, width=200)
gb.configure_column("Fight Count", editable=False, width=110)
gb.configure_column("Base Rax", editable=False, hide=True)
gb.configure_column(
    "Rarity",
    editable=True,
    cellEditor="agSelectCellEditor",
    cellEditorParams={"values": list(RARITY_MULTIPLIERS.keys())},
    width=140,
)
gb.configure_column("Total Rax", editable=False, width=110, sort="desc")

gb.configure_grid_options(getRowClass=highlight_top_3)

grid_options = gb.build()

grid_response = AgGrid(
    df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.MODEL_CHANGED,
    fit_columns_on_grid_load=True,
    theme="alpine",
    allow_unsafe_jscode=True,
    enable_enterprise_modules=False,
    height=600,
)

updated_df = pd.DataFrame(grid_response["data"])

# Recalculate Total Rax on rarity change
updated_df["Total Rax"] = updated_df.apply(
    lambda row: round(row["Base Rax"] * RARITY_MULTIPLIERS.get(row["Rarity"], 1.4), 1), axis=1
)

# Resort and re-rank
updated_df = updated_df.sort_values("Total Rax", ascending=False).reset_index(drop=True)
updated_df["Rank"] = updated_df.index + 1

# Show recalculated sorted leaderboard again with highlight
st.dataframe(
    updated_df[["Rank", "Fighter Name", "Total Rax", "Rarity", "Fight Count"]],
    use_container_width=True,
    height=600,
)
