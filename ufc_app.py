import streamlit as st
import pandas as pd

# Replace this with your actual data loading
# For example, load from a CSV:
# df = pd.read_csv('fights_data.csv')

# Sample data to illustrate format - replace with your real dataset
data = [
    {'fighter': 'Aalon Cruz', 'result': 'loss', 'method_main': 'KO/TKO', 'TOT_fighter_SigStr_landed': 10, 'TOT_opponent_SigStr_landed': 20, 'TimeFormat': '3 Rnd', 'Details': ''},
    {'fighter': 'Aalon Cruz', 'result': 'loss', 'method_main': 'KO/TKO', 'TOT_fighter_SigStr_landed': 15, 'TOT_opponent_SigStr_landed': 30, 'TimeFormat': '3 Rnd', 'Details': ''},
    {'fighter': 'Aalon Cruz', 'result': 'win', 'method_main': 'KO/TKO', 'TOT_fighter_SigStr_landed': 40, 'TOT_opponent_SigStr_landed': 10, 'TimeFormat': '5 Rnd', 'Details': 'Fight of the Night'},
    {'fighter': 'Jeff Molina', 'result': 'win', 'method_main': 'Decision - Unanimous', 'TOT_fighter_SigStr_landed': 50, 'TOT_opponent_SigStr_landed': 45, 'TimeFormat': '3 Rnd', 'Details': ''},
]

df = pd.DataFrame(data)

def calculate_rax(row):
    rax = 0

    result = str(row.get('result', '')).strip().lower()
    method = str(row.get('method_main', '')).strip().lower()

    # Debug prints
    print(f"Fighter: {row.get('fighter', 'N/A')} | Result: {result} | Method: {method}")

    if result == 'win':
        if 'ko/tko' in method:
            rax += 100
        elif 'submission' in method:
            rax += 90
        elif 'decision - unanimous' in method:
            rax += 80
        elif 'decision - majority' in method:
            rax += 75
        elif 'decision - split' in method:
            rax += 70
        else:
            rax += 60
    elif result == 'loss':
        rax += 25

    try:
        sig_str_fighter = int(float(row.get('TOT_fighter_SigStr_landed', 0)))
    except (ValueError, TypeError):
        sig_str_fighter = 0

    try:
        sig_str_opponent = int(float(row.get('TOT_opponent_SigStr_landed', 0)))
    except (ValueError, TypeError):
        sig_str_opponent = 0

    print(f"Strikes - Fighter: {sig_str_fighter}, Opponent: {sig_str_opponent}")

    if sig_str_fighter > sig_str_opponent:
        rax += (sig_str_fighter - sig_str_opponent)

    time_format = str(row.get('TimeFormat', '')).lower()
    if '5 rnd' in time_format:
        rax += 25

    details_text = str(row.get('Details', '')).lower()
    if 'fight of the night' in details_text:
        rax += 50

    print(f"Total RAX calculated: {rax}")
    return rax

# Calculate RAX per fight
df['RAX'] = df.apply(calculate_rax, axis=1)

st.title("Fighter RAX Calculation")

st.write("### Fight Data with RAX")
st.dataframe(df[['fighter', 'result', 'method_main', 'TOT_fighter_SigStr_landed', 
                 'TOT_opponent_SigStr_landed', 'TimeFormat', 'Details', 'RAX']])

# Sum total RAX per fighter
rax_totals = df.groupby('fighter')['RAX'].sum().reset_index()
rax_totals = rax_totals.sort_values(by='RAX', ascending=False)

st.write("### Total RAX per Fighter")
st.dataframe(rax_totals)
