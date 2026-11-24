"""Check the /personal endpoints with `requests` (server.py must be running)."""
import requests

BASE = "http://127.0.0.1:5000"
TIMEOUT = 30


def all_names():
    response = requests.get(f"{BASE}/personal/all", timeout=TIMEOUT)
    return [saved["name"] for saved in response.json()]


# 1. Get a random recipe JSON from our own API.
recipe = requests.get(f"{BASE}/recipe/chicken_breast/json",
                      timeout=TIMEOUT).json()
name = recipe["name"]
print("Got recipe:", name)

# 2. Save it. requests follows the 303 redirect automatically.
response = requests.post(f"{BASE}/personal", json=recipe, timeout=TIMEOUT)
print("POST /personal ->", response.status_code,
      "redirected from", response.history[0].status_code,
      "to", response.url)

# 3. Read it back as JSON (1), as a page (0), and with a bad flag (2).
url = f"{BASE}/personal/{name}"
print("GET json=1 ->", requests.get(f"{url}/1", timeout=TIMEOUT).json()["name"])
print("GET json=0 ->", requests.get(f"{url}/0", timeout=TIMEOUT).status_code)
print("GET json=2 ->", requests.get(f"{url}/2", timeout=TIMEOUT).status_code)

# 4. List all, delete, list again, and delete again.
print("ALL before delete:", all_names())
print("DELETE ->", requests.delete(url, timeout=TIMEOUT).json())
print("ALL after delete:", all_names())
print("DELETE again ->", requests.delete(url, timeout=TIMEOUT).status_code)