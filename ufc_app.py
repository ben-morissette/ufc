import streamlit as st
import pandas as pd
from utils import get_all_fighter_links, scrape_fighter_data

RARITY_OPTIONS = ['Common', 'Rare', 'Epic', 'Legendary']
RARITY_MULTIPLIERS = {
    'Common': 1.0,
    'Rare': 1.2,
    'Epic': 1.5,
    'Legendary': 2.0
}

@st.cache_data(show_spinner=True)
def load_fighter_data():
    fighter_links = get_all_fighter_links(limit=10)  # Limit for faster loading
    fighter_data = []
    for link in fighter_links:
        data = scrape_fighter_data(link)
        if data:
            fighter_data.append(data)
    return pd.DataFrame(fighter_data)

def calculate_total_rax(base_rax, rarity):
    multiplier = RARITY_MULTIPLIERS.get(rarity, 1.0)
    return round(base_rax * multiplier, 1)

def main():
    st.set_page_config(page_title="UFC RAX Leaderboard", layout="wide")
    st.title("UFC RAX Leaderboard")

    df = load_fighter_data()

    # Initialize rarity column if not present
    if 'Rarity' not in df.columns:
        df['Rarity'] = ['Common'] * len(df)

    # UI rendering
    updated_rows = []
    st.markdown("<style>.row-box { border: 1px solid #ccc; padding: 10px; margin-bottom: 5px; border-radius: 8px; background-color: #111; }</style>", unsafe_allow_html=True)

    for i, row in df.iterrows():
        col1, col2, col3 = st.columns([4, 2, 2])
        with col1:
            st.markdown(f"<div class='row-box'><strong>{row['Name']}</strong></div>", unsafe_allow_html=True)
        with col2:
            rarity = st.selectbox("", RARITY_OPTIONS, index=RARITY_OPTIONS.index(row['Rarity']), key=f"rarity_{i}")
        with col3:
            total_rax = calculate_total_rax(row['Base Rax'], rarity)
            st.markdown(f"<div class='row-box'><strong>{total_rax}</strong> RAX</div>", unsafe_allow_html=True)
        updated_rows.append({"Name": row['Name'], "Base Rax": row['Base Rax'], "Rarity": rarity, "Total Rax": total_rax})

    final_df = pd.DataFrame(updated_rows)
    final_df = final_df.sort_values(by="Total Rax", ascending=False)

    st.subheader("Sorted Leaderboard")
    st.dataframe(final_df, hide_index=True)

if __name__ == "__main__":
    main()
