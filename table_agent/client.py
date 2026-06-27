import requests
import json
import time
import os
import threading
import sys

# Add project root directory to path for package resolution
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Code.table_agent import config

_user_locks = {}
_user_locks_lock = threading.Lock()
_last_request_times = {}

def get_user_lock_and_time(user_id):
    with _user_locks_lock:
        if user_id not in _user_locks:
            _user_locks[user_id] = threading.Lock()
            _last_request_times[user_id] = 0.0
        return _user_locks[user_id]

def call_finix_api(image_path, user_id="finixC3003", max_retries=5, backoff_factor=3):
    """
    Calls the FinixDoc-VL API to parse an image to Markdown text.
    Handles retries with exponential backoff and rate limiting per user.
    """
    url = config.API_URL
    api_key = config.API_KEY
    
    if not os.path.exists(image_path):
        print(f"Error: Image path does not exist: {image_path}")
        return None
        
    try:
        with open(image_path, 'rb') as f:
            img_bytes = f.read()
    except Exception as e:
        print(f"Error reading image file {image_path}: {e}")
        return None

    data = {
        'userId': user_id,
        'apiKey': api_key,
        'fileName': os.path.basename(image_path)
    }
    
    for attempt in range(1, max_retries + 1):
        files = {
            'file': (os.path.basename(image_path), img_bytes, 'image/jpeg')
        }
        
        try:
            user_lock = get_user_lock_and_time(user_id)
            with user_lock:
                now = time.time()
                elapsed = now - _last_request_times.get(user_id, 0.0)
                # Enforce at least 6 seconds between any two API requests for the same user
                if elapsed < 6.0:
                    time.sleep(6.0 - elapsed)
                _last_request_times[user_id] = time.time()
                
            print(f"Calling FinixDoc-VL API for {os.path.basename(image_path)} using {user_id} (Attempt {attempt}/{max_retries})...")
            
            response = requests.post(url, data=data, files=files, timeout=240)
            
            if response.status_code == 200:
                response.encoding = 'utf-8'
                res_json = response.json()
                
                if res_json.get('success') is True:
                    nested_str = res_json['result']['result']
                    nested_json = json.loads(nested_str)
                    markdown_content = nested_json['choices'][0]['message']['content']
                    return markdown_content
                else:
                    err_msg = res_json.get('message')
                    print(f"[Attempt {attempt}/{max_retries}] API returned success=False: {err_msg}")
            else:
                print(f"[Attempt {attempt}/{max_retries}] HTTP error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"[Attempt {attempt}/{max_retries}] API connection/request failed: {e}")
            
        if attempt < max_retries:
            sleep_time = backoff_factor ** attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
            
    return None
