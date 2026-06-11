import requests
import json
import os

url = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
user_id = "finixC3003"
api_key = "F935A5503983FB19F26FA3F00A94EBF9"
small_slice = "f:/ProgramProject/AFAC2026/Track2/Code/Cache/83d34cf6-5d3f-4407-97f8-910646b07218_chunk_0.jpg"

if not os.path.exists(small_slice):
    print("Slice not found. Please run test_all_user_ids.py first.")
    exit(1)

data = {
    'userId': user_id,
    'apiKey': api_key,
    'fileName': os.path.basename(small_slice)
}
files = {
    'file': (os.path.basename(small_slice), open(small_slice, 'rb'), 'image/jpeg')
}

print("Calling API with finixC3003...")
response = requests.post(url, data=data, files=files, timeout=60)
print(f"Status Code: {response.status_code}")

response.encoding = 'utf-8'
try:
    res_json = response.json()
    print("Top-level JSON keys:", list(res_json.keys()))
    
    nested_result_str = res_json.get("result", {}).get("result", "")
    print("Nested result type:", type(nested_result_str))
    
    # Try to parse the nested string as JSON
    nested_json = json.loads(nested_result_str)
    print("Nested JSON keys:", list(nested_json.keys()))
    print("Choices count:", len(nested_json.get("choices", [])))
    
    content = nested_json["choices"][0]["message"]["content"]
    print("\nExtracted Markdown (first 300 chars):")
    print(content[:300])
    print("\nExtracted Markdown (last 100 chars):")
    print(content[-100:])
except Exception as e:
    print(f"Error parsing response: {e}")
    print("Raw text response:")
    print(response.text[:1000])
