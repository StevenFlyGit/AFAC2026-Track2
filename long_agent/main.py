import os
import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import slice_image, merge_markdown_pair
from api_client import call_finix_api

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

def process_single_slice(slice_idx, total_slices, slice_path):
    """
    Worker function to call API for a single slice.
    """
    print(f"  [Start] Chunk {slice_idx+1}/{total_slices}: {os.path.basename(slice_path)}")
    chunk_md = call_finix_api(slice_path)
    if chunk_md:
        chunk_md = clean_markdown(chunk_md)
        print(f"  [Success] Chunk {slice_idx+1}/{total_slices} completed successfully.")
    else:
        print(f"  [Failure] Chunk {slice_idx+1}/{total_slices} failed to parse.")
    return slice_idx, chunk_md

def main():
    parser = argparse.ArgumentParser(description="AFAC2026 Track 2 Baseline Pipeline")
    parser.add_argument("--img_dir", type=str, default="../../AFAC_DataSet", help="Directory containing input images")
    parser.add_argument("--output", type=str, default="../../Output/submission.csv", help="Path to output CSV file")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of images to process (useful for testing)")
    parser.add_argument("--chunk_height", type=int, default=5000, help="Height of vertical slices")
    parser.add_argument("--overlap_pct", type=float, default=0.15, help="Overlap percentage between slices")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of parallel workers for API calls")
    
    args = parser.parse_args()
    
    # Configure stdout to output UTF-8 to prevent console print errors on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    
    cache_dir = "./Cache"
    
    if not os.path.exists(args.img_dir):
        print(f"Error: Input directory {args.img_dir} does not exist.")
        sys.exit(1)
        
    # Find all images (.jpg, .jpeg, .png) recursively
    supported_exts = ('.jpg', '.jpeg', '.png')
    img_files = []
    for root, _, files in os.walk(args.img_dir):
        for f in files:
            if f.lower().endswith(supported_exts):
                # Store relative path from img_dir to keep names somewhat meaningful
                rel_path = os.path.relpath(os.path.join(root, f), args.img_dir)
                img_files.append(rel_path)
    img_files = sorted(img_files)
    
    if args.limit:
         img_files = img_files[:args.limit]
         print(f"Limiting execution to the first {args.limit} images.")
         
    print(f"Found {len(img_files)} images to process.")
    
    # Initialize CSV file with headers
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    print(f"Initializing output CSV at {args.output}...")
    try:
        with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["file_name", "ground_truth"])
    except Exception as e:
        print(f"Failed to initialize CSV: {e}")
        sys.exit(1)
        
    for idx, img_name in enumerate(img_files):
        img_path = os.path.join(args.img_dir, img_name)
        print(f"\n[{idx+1}/{len(img_files)}] Processing {img_name}...")
        
        # 1. Slice image if needed
        slices = slice_image(img_path, cache_dir, chunk_height=args.chunk_height, overlap_pct=args.overlap_pct)
        print(f"Slicing result: {len(slices)} chunk(s).")
        
        if not slices:
            print(f"Skipping {img_name} due to slicing failure.")
            results.append((img_name, ""))
            continue
            
        total_slices = len(slices)
        chunk_texts = ["" for _ in range(total_slices)]
        
        # Call API in parallel for chunks of this image
        print(f"Starting parallel processing with {args.max_workers} workers...")
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_slice = {
                executor.submit(process_single_slice, s_idx, total_slices, slice_info['path']): s_idx
                for s_idx, slice_info in enumerate(slices)
            }
            
            for future in as_completed(future_to_slice):
                s_idx = future_to_slice[future]
                try:
                    _, chunk_md = future.result()
                    if chunk_md:
                        chunk_texts[s_idx] = chunk_md
                    else:
                        chunk_texts[s_idx] = ""
                except Exception as exc:
                    print(f"  Slice {s_idx+1} generated an exception: {exc}")
                    chunk_texts[s_idx] = ""
                    
        # 2. Single-threaded cleanup retry for any failed slices
        failed_indices = [i for i, text in enumerate(chunk_texts) if not text]
        if failed_indices:
            print(f"  [Warning] {len(failed_indices)} slice(s) failed during parallel phase. Starting single-threaded retry...")
            for s_idx in failed_indices:
                slice_path = slices[s_idx]['path']
                print(f"  [Retry] Slice {s_idx+1}/{total_slices}: {os.path.basename(slice_path)}")
                _, chunk_md = process_single_slice(s_idx, total_slices, slice_path)
                if chunk_md:
                    chunk_texts[s_idx] = chunk_md
                    print(f"  [Retry Success] Slice {s_idx+1} recovered successfully.")
                else:
                    print(f"  [Retry Failure] Slice {s_idx+1} failed again.")
                
        # 3. Stitch chunks (Stage 2: LCS-based deduplication)
        final_markdown = chunk_texts[0] if chunk_texts else ""
        for next_text in chunk_texts[1:]:
            final_markdown = merge_markdown_pair(final_markdown, next_text)
        
        # 4. Append to CSV incrementally
        try:
            with open(args.output, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow([os.path.basename(img_name), final_markdown])
            print(f"  [Success] Saved result for {img_name} to CSV.")
        except Exception as e:
            print(f"  [Error] Failed to append result for {img_name} to CSV: {e}")

if __name__ == "__main__":
    main()
