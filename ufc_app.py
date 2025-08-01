import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

RARITY_MULTIPLIERS = {
    "Uncommon": 1.4,
    "Rare": 1.6,
    "Epic": 2,
    "Legendary": 2.5,
    "Mystic": 4,
    "Iconic": 6,
}

def get_fighter_url_by_name(name):
    base_url = "http://ufcstats.com/statistics/fighters"
    page = 1
    name_lower = name.lower()

    while True:
        url = f"{base_url}/?page={page}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="b-statistics__table")
        if not table:
            break  # no table means no fighters here

        rows = table.find("tbody").find_all("tr")
        if not rows:
            break  # no rows means no fighters here

        found_url = None
        for row in rows:
            link = row.find_all("td")[0].find("a", class_="b-link_style_black")
            if link and link.text.strip().lower() == name_lower:
                found_url = link["href"]
                break

        if found_url:
            return found_url

        page += 1  # next page

    return None

def get_two_values_from_col(col):
    ps = col.find_all("p", class_="b-fight-details__table-text")
    return (ps[0].get_text(strip=True), ps[1].get_text(strip=True)) if len(ps) == 2 else (None, None)

def get_fight_data(fighter_url):
    response = requests.get(fighter_url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="b-fight-details__table_type_event-details")
    if not table:
        return pd.DataFrame()

    rows = table.find("tbody").find_all("tr", class_="b-fight-details__table-row__hover")
    fights = []
    for row in rows:
        cols = row.find_all("td", class_="b-fight-details__table-col")
        result = cols[0].find("p").get_text(strip=True).lower()
        fighter_name = cols[1].find_all("p")[0].get_text(strip=True)
        opponent_name = cols[1].find_all("p")[1].get_text(strip=True)
        kd_f, kd_o = get_two_values_from_col(cols[2])
        str_f, str_o = get_two_values_from_col(cols[3])
        td_f, td_o = get_two_values_from_col(cols[4])
        sub_f, sub_o = get_two_values_from_col(cols[5])
        event_name = cols[6].find_all("p")[0].get_text(strip=True)
        method = cols[7].find_all("p")[0].get_text(strip=True)
        round_val = cols[8].find("p").get_text(strip=True)

        fights.append({
            "Result": result,
            "Fighter Name": fighter_name,
            "Opponent Name": opponent_name,
            "KD Fighter": kd_f,
            "KD Opponent": kd_o,
            "Strikes Fighter": str_f,
            "Strikes Opponent": str_o,
            "Takedowns Fighter": td_f,
            "Takedowns Opponent": td_o,
            "Submission Attempts Fighter": sub_f,
            "Submission Attempts Opponent": sub_o,
            "Event Name": event_name,
            "Method Main": method,
            "Round": round_val,
        })
    return pd.DataFrame(fights)

def calculate_rax(row):
    rax = 0
    if row["Result"] == "win":
        method = row["Method Main"]
        if method == "KO/TKO":
            rax += 100
        elif method in ["Submission", "SUB"]:
            rax += 90
        elif method in ["Decision - Unanimous", "U-DEC"]:
            rax += 80
        elif method == "Decision - Majority":
            rax += 75
        elif method == "Decision - Split":
            rax += 70
    elif row["Result"] == "loss":
        rax += 25

    try:
        strike_diff = int(row["Strikes Fighter"]) - int(row["Strikes Opponent"])
        if strike_diff > 0:
            rax += strike_diff
    except:
        pass

    if row["Round"] == "5":
        rax += 25

    ev = row["Event Name"].lower()
    if "fight of the night" in ev or "fight of night" in ev:
        rax += 50
    if "championship" in ev:
        rax += 25

    return rax

st.title("UFC Fighter RAX Search")

fighter_name_input = st.text_input("Enter fighter full name (e.g., Conor McGregor):")

if fighter_name_input:
    with st.spinner("Fetching fighter info..."):
        fighter_url = get_fighter_url_by_name(fighter_name_input.strip())
        if fighter_url:
            fights_df = get_fight_data(fighter_url)
            if fights_df.empty:
                st.warning("No fight data found for this fighter.")
            else:
                fights_df["Rax Earned"] = fights_df.apply(calculate_rax, axis=1)
                total_rax = fights_df["Rax Earned"].sum()
                st.write(f"Total RAX for **{fighter_name_input}**: {total_rax}")
                st.dataframe(fights_df)
        else:
            st.error("Fighter not found. Please check the name and try again.")
