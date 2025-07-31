import streamlit as st
import pandas as pd
import sys

# Your calculate_rax function (same as before)
def calculate_rax(row):
    rax = 0
    # Rule 1: Rax based on method_main
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

    # Rule 2: Rax based on significant strike difference
    sig_str_fighter = 0
    sig_str_opponent = 0
    if 'TOT_fighter_SigStr_landed' in row.index and 'TOT_opponent_SigStr_landed' in row.index:
        sig_str_fighter = row['TOT_fighter_SigStr_landed']
        sig_str_opponent = row['TOT_opponent_SigStr_landed']

    if sig_str_fighter > sig_str_opponent:
        rax += sig_str_fighter - sig_str_opponent

    # Rule 3: Bonus for 5-round fights
    if 'TimeFormat' in row.index and '5 Rnd' in str(row['TimeFormat']):
        rax += 25

    # Rule 4: Bonus for "Fight of the Night"
    if 'Details' in row.index and 'Fight of the Night' in str(row['Details']):
        rax += 50

    return rax


def main():
    st.title("MMA Fighter RAX Calculator")
    st.write("Enter a fighter's name to see their RAX score breakdown.")

    fighter_input_name = st.text_input("Fighter Name", value="Max Holloway")

    if st.button("Calculate RAX"):
        if not fighter_input_name.strip():
            st.error("Please enter a valid fighter name.")
            return

        st.info(f"Fetching data for fighter: {fighter_input_name} ...")

        try:
            fighter_url = get_fighter_url_by_name(fighter_input_name)
            st.success(f"Found URL for {fighter_input_name}: {fighter_url}")
        except ValueError as e:
            st.error(str(e))
            return

        # Get fight links and main fight data
        fight_links, main_fights_df = get_fight_links(fighter_url)

        all_fight_details = []
        for fl in fight_links:
            row = main_fights_df.loc[main_fights_df['fight_link'] == fl].iloc[0]
            main_fighter_name = row['fighter_name']
            opp_name = row['opponent_name']
            details = parse_fight_details(fl, main_fighter_name, opp_name)
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

        final_df = pd.concat([combined_df[['fighter_name', 'opponent_name', 'result', 'method_main', 'rax_earned']], total_row], ignore_index=True)

        st.dataframe(final_df.style.format({'rax_earned': '{:.0f}'}))

if __name__ == "__main__":
    main()
