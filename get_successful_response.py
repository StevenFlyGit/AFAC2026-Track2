import requests
import json
import time
import os
import sys

url = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
api_key = "F935A5503983FB19F26FA3F00A94EBF9"
user_id = "finixC3003"
small_slice = "f:/ProgramProject/AFAC2026/Track2/Code/Cache/83d34cf6-5d3f-4407-97f8-910646b07218_chunk_0.jpg"

sys.stdout.reconfigure(encoding='utf-8')

# Read file bytes once to safely reuse across retries
with open(small_slice, 'rb') as f:
    img_bytes = f.read()

data = {
    'userId': user_id,
    'apiKey': api_key,
    'fileName': os.path.basename(small_slice)
}

success = False
for attempt in range(1, 11):
    print(f"Attempt {attempt}/10 calling API...")
    # Re-create files dict with the raw bytes each time
    files = {
        'file': (os.path.basename(small_slice), img_bytes, 'image/jpeg')
    }
    
    try:
        r = requests.post(url, data=data, files=files, timeout=90)
        print(f"Status Code: {r.status_code}")
        
        # Enforce UTF-8 encoding
        r.encoding = 'utf-8'
        res_json = r.json()
        
        if r.status_code == 200 and res_json.get('success') is True:
            raw_bytes = r.content
            with open("f:/ProgramProject/AFAC2026/Track2/Code/Cache/response_raw.bin", "wb") as f_out:
                f_out.write(raw_bytes)
            print("Successfully saved raw bytes to response_raw.bin!")
            
            nested = json.loads(res_json['result']['result'])
            content = nested['choices'][0]['message']['content']
            
            print("\n=== SUCCESS ===")
            print("UTF-8 first 300 chars:")
            print(content[:300])
            
            # Save the decoded markdown to verify
            with open("f:/ProgramProject/AFAC2026/Track2/Code/Cache/out_success.md", "w", encoding="utf-8") as f_md:
                f_md.write(content)
            
            success = True
            break
        else:
            print(f"Server returned error or success=False: {res_json.get('message')}")
    except Exception as e:
        print(f"Error on attempt {attempt}: {e}")
    
    # Wait before retrying
    print("Waiting 10 seconds before retry...")
    time.sleep(10)

if not success:
    print("All attempts failed.")
