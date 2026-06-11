import requests
import os

url = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
user_id = "finixC3003"
api_key = "F935A5503983FB19F26FA3F00A94EBF9"
small_slice = "f:/ProgramProject/AFAC2026/Track2/Code/Cache/83d34cf6-5d3f-4407-97f8-910646b07218_chunk_0.jpg"

data = {
    'userId': user_id,
    'apiKey': api_key,
    'fileName': os.path.basename(small_slice)
}
files = {
    'file': (os.path.basename(small_slice), open(small_slice, 'rb'), 'image/jpeg')
}

print("Calling API...")
r = requests.post(url, data=data, files=files, timeout=60)
print(f"Status Code: {r.status_code}")

with open("f:/ProgramProject/AFAC2026/Track2/Code/Cache/response_raw.bin", "wb") as f:
    f.write(r.content)
print("Saved raw bytes to response_raw.bin")
