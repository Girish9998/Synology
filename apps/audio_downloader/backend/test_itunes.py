import requests
import urllib.parse
import json

def search_itunes(query):
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"
    response = requests.get(url)
    data = response.json()
    if data['resultCount'] > 0:
        result = data['results'][0]
        print(json.dumps(result, indent=2))
    else:
        print("No results found.")

search_itunes("Never Gonna Give You Up Rick Astley")
