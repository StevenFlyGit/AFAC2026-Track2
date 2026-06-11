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

print("Calling API...")
r = requests.post(url, data=data, files=files, timeout=60)
raw_bytes = r.content

print("\n--- Try UTF-8 ---")
try:
    decoded_utf8 = raw_bytes.decode('utf-8')
    res_json = json.loads(decoded_utf8)
    nested = json.loads(res_json['result']['result'])
    content_utf8 = nested['choices'][0]['message']['content']
    print("UTF-8 first 100 chars:")
    print(content_utf8[:100])
    with open('f:/ProgramProject/AFAC2026/Track2/Code/Cache/out_utf8.md', 'w', encoding='utf-8') as f:
        f.write(content_utf8)
except Exception as e:
    print("UTF-8 failed:", e)

print("\n--- Try GBK ---")
try:
    decoded_gbk = raw_bytes.decode('gbk')
    res_json = json.loads(decoded_gbk)
    nested = json.loads(res_json['result']['result'])
    content_gbk = nested['choices'][0]['message']['content']
    print("GBK first 100 chars:")
    print(content_gbk[:100])
    with open('f:/ProgramProject/AFAC2026/Track2/Code/Cache/out_gbk.md', 'w', encoding='utf-8') as f:
        f.write(content_gbk)
except Exception as e:
    print("GBK failed:", e)

print("\n--- Try GB18030 ---")
try:
    decoded_gb18030 = raw_bytes.decode('gb18030')
    res_json = json.loads(decoded_gb18030)
    nested = json.loads(res_json['result']['result'])
    content_gb18030 = nested['choices'][0]['message']['content']
    print("GB18030 first 100 chars:")
    print(content_gb18030[:100])
    with open('f:/ProgramProject/AFAC2026/Track2/Code/Cache/out_gb18030.md', 'w', encoding='utf-8') as f:
        f.write(content_gb18030)
except Exception as e:
    print("GB18030 failed:", e)
