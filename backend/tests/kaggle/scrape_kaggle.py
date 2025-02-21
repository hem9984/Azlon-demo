import requests
from bs4 import BeautifulSoup

def scrape_kaggle_challenge_text(url):
    """
    Scrapes the text content from a Kaggle challenge description page.

    Args:
        url (str): The URL of the Kaggle challenge page.

    Returns:
        str: The extracted text content, or None if an error occurs.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Adjust the selector based on Kaggle's current page structure
        challenge_description = soup.select_one('#evaluation > div > div:nth-child(2) > div > div')

        if challenge_description:
            return challenge_description.get_text(separator='\n', strip=True)
        else:
             print("Challenge description element not found on the page.")
             return None
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == '__main__':
    challenge_url = 'https://www.kaggle.com/competitions/just-the-basics-the-after-party/overview/evaluation' 
    scraped_text = scrape_kaggle_challenge_text(challenge_url)

    if scraped_text:
        print(scraped_text)
    else:
        print("Failed to scrape challenge text.")
