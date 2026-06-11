import os
import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import slice_image
from api_client import call_finix_api

def process_single_slice(slice_idx, total_slices, slice_path):
    """
    Worker function to call API for a single slice.
    """
    print(f"  [Start] Chunk {slice_idx+1}/{total_slices}: {os.path.basename(slice_path)}")
    chunk_md = call_finix_api(slice_path)
    if chunk_md:
        print(f"  [Success] Chunk {slice_idx+1}/{total_slices} completed successfully.")
    else:
        print(f"  [Failure] Chunk {slice_idx+1}/{total_slices} failed to parse.")
    return slice_idx, chunk_md

def main():
    parser = argparse.ArgumentParser(description="AFAC2026 Track 2 Baseline Pipeline")
    parser.add_argument("--img_dir", type=str, required=True, help="Directory containing input images")
    parser.add_argument("--output", type=str, default="f:/ProgramProject/AFAC2026/Track2/Code/submission.csv", help="Path to output CSV file")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of images to process (useful for testing)")
    parser.add_argument("--chunk_height", type=int, default=3000, help="Height of vertical slices")
    parser.add_argument("--overlap_pct", type=float, default=0.15, help="Overlap percentage between slices")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of parallel workers for API calls")
    
    args = parser.parse_args()
    
    # Configure stdout to output UTF-8 to prevent console print errors on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    
    cache_dir = "f:/ProgramProject/AFAC2026/Track2/Code/Cache"
    
    if not os.path.exists(args.img_dir):
        print(f"Error: Input directory {args.img_dir} does not exist.")
        sys.exit(1)
        
    # Find all images (.jpg, .jpeg, .png)
    supported_exts = ('.jpg', '.jpeg', '.png')
    img_files = sorted([f for f in os.listdir(args.img_dir) if f.lower().endswith(supported_exts)])
    
    if args.limit:
         img_files = img_files[:args.limit]
         print(f"Limiting execution to the first {args.limit} images.")
         
    print(f"Found {len(img_files)} images to process.")
    
    results = []
    
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
                
        # 2. Stitch chunks (Baseline: simple concatenation)
        final_markdown = "\n\n".join(chunk_texts)
        results.append((img_name, final_markdown))
        
    # 3. Write results to CSV with RFC 4180 compliant quoting (QUOTE_ALL)
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    print(f"\nWriting results to {args.output}...")
    try:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            # Write header
            writer.writerow(["file_name", "ground_truth"])
            for fname, md in results:
                writer.writerow([fname, md])
        print("CSV writing completed successfully!")
    except Exception as e:
        print(f"Failed to write CSV: {e}")

if __name__ == "__main__":
    main()
