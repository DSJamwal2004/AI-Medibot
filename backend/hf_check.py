import os, json, requests
from dotenv import load_dotenv

load_dotenv()  # loads .env from current directory

token = os.getenv("HF_API_TOKEN")
model = os.getenv("HF_MODEL")

print("TOKEN PRESENT?", bool(token))
print("MODEL:", model)

url = "https://router.huggingface.co/v1/chat/completions"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "max_tokens": 30,
}

r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
print("Status:", r.status_code)
print(r.text)


