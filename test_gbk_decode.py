import requests
import json
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

print("Calling API with 180s timeout...")
try:
    r = requests.post(url, data=data, files=files, timeout=180)
    print(f"Status Code: {r.status_code}")
    
    # Try GBK
    try:
        decoded = r.content.decode('gbk')
        res_json = json.loads(decoded)
        nested = json.loads(res_json['result']['result'])
        content = nested['choices'][0]['message']['content']
        print("\n=== SUCCESS WITH GBK ===")
        print(content[:300])
        with open("f:/ProgramProject/AFAC2026/Track2/Code/Cache/out_gbk.md", "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e_gbk:
        print("GBK decode failed:", e_gbk)
        
    # Try UTF-8
    try:
        decoded = r.content.decode('utf-8')
        res_json = json.loads(decoded)
        nested = json.loads(res_json['result']['result'])
        content = nested['choices'][0]['message']['content']
        print("\n=== UTF-8 (just for comparison) ===")
        print(content[:300])
    except Exception as e_utf8:
        print("UTF-8 decode failed:", e_utf8)

except Exception as e:
    print("API call failed:", e)
