import os
import argparse
import csv
import sys
import json
import re

# Add project root directory to path for package resolution
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import modular agent components
from Code.table_agent import config
from Code.table_agent.client import call_finix_api
from Code.table_agent.tools import layout, slicer, merger, validator

Image.MAX_IMAGE_PIXELS = None

def clean_markdown(text):
    """
    Strips raw API code block wrappers like ```markdown and ```.
    """
    if not text:
        return ""
    text = text.strip()
    while True:
        original = text
        if text.lower().startswith("```markdown"):
            text = text[11:].strip()
        elif text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        if text == original:
            break
    return text

def parse_block_adaptive(block_img_path, y_start, y_end, cache_dir, base_name, split_suffix, user_id, attempt=1):
    """
    Parses an image block. If the API output is truncated (e.g. contains <table> but no closing </table>),
    it appends a closing tag. Empty blocks (None) are skipped immediately.
    """
    if block_img_path is None:
        return ""
        
    block_filename = os.path.basename(block_img_path)
    txt_cache_path = block_img_path + ".txt"
    
    if os.path.exists(txt_cache_path):
        print(f"  [Attempt {attempt}] Loading block from cache: {block_filename}")
        try:
            with open(txt_cache_path, 'r', encoding='utf-8') as f:
                result_md = f.read()
        except Exception as e:
            print(f"  [Error] Failed to read cached response for {block_filename}: {e}")
            result_md = None
    else:
        print(f"  [Attempt {attempt}] Parsing block: {block_filename} using {user_id}")
        result_md = call_finix_api(block_img_path, user_id=user_id)
        if result_md:
            try:
                with open(txt_cache_path, 'w', encoding='utf-8') as f:
                    f.write(result_md)
            except Exception as e:
                print(f"  [Warning] Failed to write cache for {block_filename}: {e}")
                
    if not result_md:
        print(f"  [Error] API call returned empty or failed for block {block_filename}.")
        return ""
        
    result_md = clean_markdown(result_md)
    
    has_table_start = bool(re.search(r'<table[^>]*>', result_md, re.IGNORECASE))
    has_table_end = bool(re.search(r'</table>', result_md, re.IGNORECASE))
    
    if has_table_start and not has_table_end:
        print(f"  [Warning] Table truncated in block {block_filename}. Appending closing tag.")
        return result_md + "\n</table>"
        
    return result_md

def process_single_image(img_name, img_dir, cache_dir, chunk_height, overlap_pct, max_workers):
    """
    Worker function to process a single image using modular tools.
    """
    img_path = os.path.join(img_dir, img_name)
    base_name = os.path.splitext(os.path.basename(img_name))[0]
    
    try:
        img = Image.open(img_path)
    except Exception as e:
        print(f"Error opening image {img_path}: {e}")
        return ""
        
    width, height = img.size
    print(f"Image dimensions: {width}x{height}")
    
    user_ids = config.USER_IDS
    
    # 1. Detect vertical split layout (左右分栏)
    gutter_x = layout.detect_vertical_gutter(img)
    
    if gutter_x is not None:
        print(f"  [Layout] Left-Right Split layout detected.")
        left_img_path, right_img_path = layout.split_left_right_images(img_path, cache_dir, gutter_x)
        columns_to_process = [
            {"path": left_img_path, "suffix": "left"},
            {"path": right_img_path, "suffix": "right"}
        ]
    else:
        print(f"  [Layout] Single column layout detected.")
        columns_to_process = [
            {"path": img_path, "suffix": "single"}
        ]
        
    column_markdowns = []
    
    for col in columns_to_process:
        print(f"  Processing column: {col['suffix']}")
        
        try:
            col_img = Image.open(col['path'])
        except Exception as e:
            print(f"Error opening column image {col['path']}: {e}")
            continue
            
        # 2. Segment column vertically into K regions
        regions = layout.segment_table_regions(col_img)
        print(f"  [Regions] Segmented column {col['suffix']} into {len(regions)} regions.")
        
        # 3. Horizontal slicing
        flat_slices = []
        region_slices = {r_idx: [] for r_idx in range(len(regions))}
        
        slice_counter = 0
        for r_idx, r_coords in enumerate(regions):
            slices = slicer.slice_image_table(
                col['path'], 
                cache_dir, 
                chunk_height=chunk_height, 
                overlap_pct=overlap_pct, 
                region_coords=r_coords, 
                region_idx=r_idx
            )
            for slc in slices:
                flat_slices.append(slc)
                region_slices[r_idx].append(slice_counter)
                slice_counter += 1
                
        print(f"  Total flat slices generated for column {col['suffix']}: {len(flat_slices)}")
        
        total_slices = len(flat_slices)
        slice_left_texts = ["" for _ in range(total_slices)]
        slice_right_texts = ["" for _ in range(total_slices)]
        slice_texts = ["" for _ in range(total_slices)]
        
        # 4. Call API in parallel
        future_to_info = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for idx, slice_info in enumerate(flat_slices):
                if 'path' in slice_info:
                    fut = executor.submit(
                        parse_block_adaptive,
                        slice_info['path'],
                        slice_info['y_start'],
                        slice_info['y_end'],
                        cache_dir,
                        base_name,
                        col['suffix'],
                        user_ids[idx % len(user_ids)]
                    )
                    future_to_info[fut] = (idx, 'single')
                else:
                    fut_l = executor.submit(
                        parse_block_adaptive,
                        slice_info['path_left'],
                        slice_info['y_start'],
                        slice_info['y_end'],
                        cache_dir,
                        base_name,
                        col['suffix'] + "_left",
                        user_ids[(idx * 2) % len(user_ids)]
                    )
                    future_to_info[fut_l] = (idx, 'left')
                    
                    fut_r = executor.submit(
                        parse_block_adaptive,
                        slice_info['path_right'],
                        slice_info['y_start'],
                        slice_info['y_end'],
                        cache_dir,
                        base_name,
                        col['suffix'] + "_right",
                        user_ids[(idx * 2 + 1) % len(user_ids)]
                    )
                    future_to_info[fut_r] = (idx, 'right')
            
            for future in as_completed(future_to_info):
                idx, side = future_to_info[future]
                try:
                    res_text = future.result()
                    if side == 'single':
                        slice_texts[idx] = res_text
                    elif side == 'left':
                        slice_left_texts[idx] = res_text
                    elif side == 'right':
                        slice_right_texts[idx] = res_text
                except Exception as exc:
                    print(f"  Slice {idx+1} ({side}) generated an exception: {exc}")
                    
        # 5. Merge Left and Right halves
        for idx, slice_info in enumerate(flat_slices):
            if 'path' not in slice_info:
                l_txt = slice_left_texts[idx]
                r_txt = slice_right_texts[idx]
                slice_texts[idx] = merger.merge_left_right_html_smart(l_txt, r_txt)
                
        # 6. Single-threaded retry for failed blocks
        failed_indices = [i for i, text in enumerate(slice_texts) if not text]
        if failed_indices:
            print(f"  [Warning] {len(failed_indices)} slice(s) failed. Starting single-threaded retry...")
            for idx in failed_indices:
                slice_info = flat_slices[idx]
                if 'path' in slice_info:
                    slice_texts[idx] = parse_block_adaptive(
                        slice_info['path'],
                        slice_info['y_start'],
                        slice_info['y_end'],
                        cache_dir,
                        base_name,
                        col['suffix'],
                        user_ids[idx % len(user_ids)],
                        attempt=2
                    )
                else:
                    l_txt = slice_left_texts[idx]
                    r_txt = slice_right_texts[idx]
                    if not l_txt:
                        print(f"  [Retry Left] Retrying left chunk for slice {idx+1}")
                        l_txt = parse_block_adaptive(
                            slice_info['path_left'],
                            slice_info['y_start'],
                            slice_info['y_end'],
                            cache_dir,
                            base_name,
                            col['suffix'] + "_left",
                            user_ids[(idx * 2) % len(user_ids)],
                            attempt=2
                        )
                        slice_left_texts[idx] = l_txt
                    if not r_txt:
                        print(f"  [Retry Right] Retrying right chunk for slice {idx+1}")
                        r_txt = parse_block_adaptive(
                            slice_info['path_right'],
                            slice_info['y_start'],
                            slice_info['y_end'],
                            cache_dir,
                            base_name,
                            col['suffix'] + "_right",
                            user_ids[(idx * 2 + 1) % len(user_ids)],
                            attempt=2
                        )
                        slice_right_texts[idx] = r_txt
                    slice_texts[idx] = merger.merge_left_right_html_smart(l_txt, r_txt)
                
        # 7. Merge and stitch slices within each region
        region_markdowns = []
        for r_idx in range(len(regions)):
            indices = region_slices[r_idx]
            r_slice_texts = [slice_texts[i] for i in indices]
            r_markdown = merger.merge_table_slices(r_slice_texts)
            region_markdowns.append(r_markdown)
            
        col_markdown = "\n\n".join(region_markdowns)
        column_markdowns.append(col_markdown)
        
    final_markdown = "\n\n".join(column_markdowns)
    return final_markdown

def main():
    parser = argparse.ArgumentParser(description="Modular Workflow Agent for Table Parsing")
    parser.add_argument("--img_dir", type=str, default=config.IMAGES_DIR, help="Directory containing table images")
    parser.add_argument("--output", type=str, default=config.SUBMISSION_PATH, help="Path to output CSV file")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images")
    parser.add_argument("--chunk_height", type=int, default=config.DEFAULT_CHUNK_HEIGHT, help="Height of horizontal slices")
    parser.add_argument("--overlap_pct", type=float, default=config.DEFAULT_OVERLAP_PCT, help="Overlap percentage")
    parser.add_argument("--max_workers", type=int, default=config.MAX_WORKERS, help="Maximum thread pool workers")
    parser.add_argument("--typical", action="store_true", help="Process only the 9 typical images")
    
    args = parser.parse_args()
    
    sys.stdout.reconfigure(encoding='utf-8')
    
    cache_dir = config.CACHE_DIR
    ledger_path = config.LEDGER_PATH
    
    if not os.path.exists(args.img_dir):
        print(f"Error: Images directory {args.img_dir} does not exist.")
        sys.exit(1)
        
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    supported_exts = ('.jpg', '.jpeg', '.png')
    img_files = sorted([f for f in os.listdir(args.img_dir) if f.lower().endswith(supported_exts)])
    
    if args.typical:
        typical_set = {
            "6c205e72-9e73-48d0-9373-f5c09b4b8207.jpg",
            "8c8c784c-5dd5-40d2-9476-0a594b85fb6c.jpg",
            "9723e972-9575-45be-81d7-35c426d3060f.jpg",
            "a1aaef73-ebc9-404b-a72f-29f2b39125bc.jpg",
            "a300a942-66a1-4beb-8aad-21b7616ae44c.jpg",
            "a4924b6d-2eb6-4ebc-828e-ee32475c9e3e.jpg",
            "bd843d61-18bf-4361-bb97-dd8ccd683de4.jpg",
            "e8b578eb-d776-48d8-8cc7-01090d0ee8b3.jpg",
            "ec745262-a617-4423-b6f0-1d57849344b5.jpg"
        }
        img_files = [f for f in img_files if f in typical_set]
        print(f"Filtering to process only the 9 typical images. Found: {len(img_files)}")
        
    if args.limit:
        img_files = img_files[:args.limit]
        
    print(f"Total images in dataset: {len(img_files)}")
    
    ledger = {"images": {}}
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, 'r', encoding='utf-8') as f:
                ledger = json.load(f)
            print(f"Loaded existing ledger from {ledger_path}. Resuming tasks...")
        except Exception as e:
            print(f"Failed to load ledger: {e}. Starting fresh...")
            
    for f in img_files:
        if f not in ledger["images"]:
            ledger["images"][f] = {"status": "pending", "output": ""}
            
    os.makedirs(cache_dir, exist_ok=True)
    with open(ledger_path, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
        
    for idx, img_name in enumerate(img_files):
        state = ledger["images"][img_name]
        if state["status"] == "success":
            print(f"[{idx+1}/{len(img_files)}] Skipping {img_name} (already processed successfully).")
            continue
            
        print(f"\n[{idx+1}/{len(img_files)}] Processing {img_name}...")
        state["status"] = "processing"
        
        with open(ledger_path, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
            
        final_markdown = process_single_image(
            img_name,
            args.img_dir,
            cache_dir,
            args.chunk_height,
            args.overlap_pct,
            args.max_workers
        )
        
        if final_markdown:
            state["status"] = "success"
            state["output"] = final_markdown
            print(f"  [Success] Finished processing {img_name}.")
        else:
            state["status"] = "failed"
            print(f"  [Failure] Failed to process {img_name}.")
            
        with open(ledger_path, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
            
    print(f"\nGenerating final CSV submission at {args.output}...")
    try:
        with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["file_name", "ground_truth"])
            for img_name in img_files:
                out_text = ledger["images"][img_name]["output"]
                writer.writerow([img_name, out_text])
        print(f"Submission CSV written successfully! Total rows: {len(img_files)}")
    except Exception as e:
        print(f"Failed to generate submission CSV: {e}")

if __name__ == "__main__":
    main()
