import requests
import os
import sys

# Ensure Code folder is in path so we can import utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import slice_image

url = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
user_id = "finixB2002"
api_key = "F935A5503983FB19F26FA3F00A94EBF9"

# We will use the long image
test_image_path = "f:/ProgramProject/AFAC2026/Track2/AFAC_DataSet/finixdocbench_huge_long_100/images/83d34cf6-5d3f-4407-97f8-910646b07218.jpg"
cache_dir = "f:/ProgramProject/AFAC2026/Track2/Code/Cache"

print("Slicing the image...")
slices = slice_image(test_image_path, cache_dir, chunk_height=3000, overlap_pct=0.15)
print(f"Created {len(slices)} slices.")

if not slices:
    print("Failed to slice image.")
    exit(1)

# Pick the first slice
first_slice = slices[0]['path']
print(f"Sending first slice: {first_slice}...")

data = {
    'userId': user_id,
    'apiKey': api_key,
    'fileName': os.path.basename(first_slice)
}

files = {
    'file': (os.path.basename(first_slice), open(first_slice, 'rb'), 'image/jpeg')
}

try:
    response = requests.post(url, data=data, files=files, timeout=90)
    print(f"Status Code: {response.status_code}")
    print("Response Headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    
    print("\nResponse Body (first 1000 chars):")
    text_content = response.text
    print(text_content[:1000])
    
    if len(text_content) > 1000:
        print("... [TRUNCATED]")
    
    try:
        json_data = response.json()
        print("\nParsed successfully as JSON! Keys:", list(json_data.keys()))
    except Exception:
        print("\nCould not parse response as JSON. It seems to be raw text/markdown.")
        
except Exception as e:
    print(f"An error occurred: {e}")
