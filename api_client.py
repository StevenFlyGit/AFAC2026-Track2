import requests
import json
import time
import os

def call_finix_api(image_path, user_id="finixC3003", api_key="F935A5503983FB19F26FA3F00A94EBF9", max_retries=5, backoff_factor=3):
    """
    Calls the FinixDoc-VL API to parse an image to Markdown text.
    Handles retries with exponential backoff and passes image bytes directly to avoid read pointer reset bugs.
    
    Args:
        image_path (str): Path to the image file.
        user_id (str): Whitelisted user ID (defaults to 'finixC3003').
        api_key (str): Fixed API key.
        max_retries (int): Maximum number of retries in case of transient errors.
        backoff_factor (int): Multiplier for delay between retries.
        
    Returns:
        str: The Markdown text result, or None if failed.
    """
    url = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
    
    if not os.path.exists(image_path):
        print(f"Error: Image path does not exist: {image_path}")
        return None
        
    try:
        # Read the file bytes once so we can safely reuse them across retries
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
        # Always recreate files dict with the raw bytes
        files = {
            'file': (os.path.basename(image_path), img_bytes, 'image/jpeg')
        }
        
        try:
            print(f"Calling FinixDoc-VL API for {os.path.basename(image_path)} (Attempt {attempt}/{max_retries})...")
            print(f"========== API CALL START ==========")
            print(f"Input image path: {image_path}")
            print(f"Input URL: {url}")
            print(f"Input Data: {data}")
            
            response = requests.post(url, data=data, files=files, timeout=90)
            
            print(f"========== API CALL END ==========")
            print(f"Status Code: {response.status_code}")
            try:
                print(f"Response Content: {response.text[:200]}...")
            except Exception:
                print("Could not print response text.")

            
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
                
        except (requests.exceptions.RequestException, Exception) as e:
            print(f"[Attempt {attempt}/{max_retries}] Exception occurred: {e}")
            
        if attempt < max_retries:
            sleep_time = backoff_factor ** attempt
            print(f"Waiting {sleep_time} seconds before retrying...")
            time.sleep(sleep_time)
            
    print(f"Failed to call FinixDoc-VL API for {image_path} after {max_retries} attempts.")
    return None
