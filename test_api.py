import requests

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    r = requests.get(f"{BASE_URL}/")
    print("Health:", r.status_code, r.json())

payload = {
        "before": "r2qk2r/ppp2ppp/2n5/3n4/Q1B5/P1P1BP2/5P1P/R3K2R w KQkq - 0 14",
        "after":  "r2qk2r/ppp2ppp/2n5/3B4/Q7/P1P1BP2/5P1P/R3K2R b KQkq - 0 14"
    }

def test_single():
    

    r = requests.post(f"{BASE_URL}/single", json=payload)
    print("Single:", r.status_code)
    print(r.json())


def test_chain():

    r = requests.post(f"{BASE_URL}/chain", json=payload)
    print("Chain:", r.status_code)
    print(r.json())


if __name__ == "__main__":
    test_health()
    test_single()
    test_chain()
