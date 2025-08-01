import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import string

def fetch_all_fighters():
    base_url = "http://ufcstats.com/statistics/fighters"
    fighters = []

    for char in string.ascii_uppercase:
        url = f"{base_url}?char={char}"
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="b-statistics__table")
        if not table:
            continue
        rows = table.find("tbody").find_all("tr")
        for row in rows:
            link = row.find_all("td")[0].find("a", class_="b-link_style_black")
            if link:
                name = link.text.strip()
                href = link['href']
                fighters.append({"name": name, "url": href})
    return fighters

@st.cache_data(show_spinner=False)
def get_fighters_cached():
    return fetch_all_fighters()

def get_fighter_url(name, fighters):
    name_lower = name.lower()
    for f in fighters:
        if f["name"].lower() == name_lower:
            return f["url"]
    return None

def get_fight_data(fighter_url):
    resp = requests.get(fighter_url)
    soup = BeautifulSoup(resp.text, "html.parser")
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
        event_name = cols[6].find_all("p")[0].get_text(strip=True)
        method = cols[7].find_all("p")[0].get_text(strip=True)
        round_val = cols[8].find("p").get_text(strip=True)

        fights.append({
            "Result": result,
            "Fighter Name": fighter_name,
            "Opponent Name": opponent_name,
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

    if row["Round"] == "5":
        rax += 25

    ev = row["Event Name"].lower()
    if "fight of the night" in ev or "fight of night" in ev:
        rax += 50
    if "championship" in ev:
        rax += 25

    return rax

st.title("UFC Fighter RAX Search")

# Cache all fighters once
fighters = get_fighters_cached()

fighter_name_input = st.text_input("Enter full fighter name (e.g., Conor McGregor)")

if fighter_name_input:
    fighter_url = get_fighter_url(fighter_name_input.strip(), fighters)
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
