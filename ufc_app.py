import requests
from bs4 import BeautifulSoup

def get_fighter_url_by_name(name: str) -> str | None:
    """
    Given a fighter's name (e.g., 'Conor McGregor'), search the UFC fighter directory
    and return the fighter's profile URL if found, else None.
    """

    # Base URL for UFC fighter directory (example)
    base_url = "https://www.ufc.com/athletes/all"

    # Step 1: Request the page that lists all fighters (or a searchable page)
    try:
        response = requests.get(base_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Network error fetching UFC fighters page: {e}")
        return None

    # Step 2: Parse the page content
    soup = BeautifulSoup(response.text, "html.parser")

    # Step 3: Search for the fighter's name in the list of fighters on the page
    # This example assumes fighter names are in <a> tags with hrefs containing "/athlete/"
    fighters = soup.find_all("a", href=True)

    # Normalize the input name for matching
    name_lower = name.strip().lower()

    for a_tag in fighters:
        href = a_tag['href']
        text = a_tag.get_text(strip=True).lower()

        if "/athlete/" in href and name_lower == text:
            # Found the fighter
            # Construct the full URL if href is relative
            fighter_url = href if href.startswith("http") else "https://www.ufc.com" + href
            return fighter_url

    # If we get here, fighter not found
    print(f"Fighter named '{name}' not found.")
    return None

def main():
    fighter_input_name = input("Enter UFC fighter name: ").strip()
    if not fighter_input_name:
        print("No fighter name entered.")
        return

    try:
        fighter_url = get_fighter_url_by_name(fighter_input_name)
        if fighter_url:
            print(f"Fighter URL: {fighter_url}")
        else:
            print("Fighter URL not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
