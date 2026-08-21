import requests

url = "http://127.0.0.1:8000/analyze"

files = [
    ("files", open("NDA.pdf", "rb"))
]

data = {"prompt": "check contradictions"}

print("Starting request...")
response = requests.post(url, files=files, data=data)
print("Got response!")
print(response.status_code)
print(response.json())