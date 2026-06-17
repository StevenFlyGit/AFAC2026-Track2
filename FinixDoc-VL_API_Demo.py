import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")

from api_client import call_finix_api

DATASET_DIR = r"F:\ProgramProject\AFAC2026\Track2\Code\Cache"
OUTPUT_DIR = r"F:\ProgramProject\AFAC2026\Track2\Demo"
API_USER_ID = "finixC3003"
API_KEY = "F935A5503983FB19F26FA3F00A94EBF9"
MAX_WORKERS = 4


def process_one(img_name):
    img_path = os.path.join(DATASET_DIR, img_name)
    md = call_finix_api(img_path, user_id=API_USER_ID, api_key=API_KEY)
    if md is None:
        return img_name, False
    base = os.path.splitext(img_name)[0]
    out_path = os.path.join(OUTPUT_DIR, base + ".md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return img_name, True


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    imgs = sorted(f for f in os.listdir(DATASET_DIR) if f.lower().endswith(("01ac6c2a-a9ce-4a19-bb55-096f62222450_chunk_0.jpg")))
    print(f"Found {len(imgs)} images, starting with {MAX_WORKERS} workers.\n")
    t0 = time.time()
    ok, fail = 0, []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(process_one, n): n for n in imgs}
        for fut in as_completed(futs):
            name, success = fut.result()
            tag = "OK" if success else "FAIL"
            print(f"[{tag}] {name}")
            if success:
                ok += 1
            else:
                fail.append(name)
    elapsed = time.time() - t0
    print(f"\nDone. {ok}/{len(imgs)} succeeded, {len(fail)} failed. Elapsed {elapsed:.1f}s")
    if fail:
        print("Failed files:", fail)


if __name__ == "__main__":
    main()
