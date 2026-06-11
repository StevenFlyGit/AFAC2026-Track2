import requests
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import slice_image

url = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
api_key = "F935A5503983FB19F26FA3F00A94EBF9"
user_ids = ["finixA1001", "finixB2002", "finixC3003", "finixD4004", "finixE5005"]

test_image_path = "f:/ProgramProject/AFAC2026/Track2/AFAC_DataSet/finixdocbench_huge_long_100/images/83d34cf6-5d3f-4407-97f8-910646b07218.jpg"
cache_dir = "f:/ProgramProject/AFAC2026/Track2/Code/Cache"

print("Slicing a small chunk (height=1000)...")
slices = slice_image(test_image_path, cache_dir, chunk_height=1000, overlap_pct=0.15)
if not slices:
    print("Failed to slice image.")
    exit(1)

small_slice = slices[0]['path']
print(f"Small slice size: {os.path.getsize(small_slice)} bytes.")

for uid in user_ids:
    print(f"\n--- Testing User ID: {uid} ---")
    data = {
        'userId': uid,
        'apiKey': api_key,
        'fileName': os.path.basename(small_slice)
    }
    files = {
        'file': (os.path.basename(small_slice), open(small_slice, 'rb'), 'image/jpeg')
    }
    
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        print(f"Status Code: {response.status_code}")
        print("Response (first 200 chars):")
        print(response.text[:200])
        if response.status_code == 200:
            print(f"==> User ID {uid} SUCCEEDED!")
            # We can stop testing if we find one that works
            break
    except Exception as e:
        print(f"Error with {uid}: {e}")
