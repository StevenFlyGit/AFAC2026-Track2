import os
import argparse
import csv
import sys

# Ensure local packages (like rapidfuzz) in the Code folder can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import rapidfuzz

def main():
    parser = argparse.ArgumentParser(description="AFAC2026 Track 2 Local Evaluation (Text Edit)")
    parser.add_argument("--csv_path", type=str, default="f:/ProgramProject/AFAC2026/Track2/Code/submission.csv", help="Path to predicted CSV file")
    parser.add_argument("--gt_dir", type=str, required=True, help="Directory containing Ground Truth .md files")
    
    args = parser.parse_args()
    
    sys.stdout.reconfigure(encoding='utf-8')
    
    if not os.path.exists(args.csv_path):
        print(f"Error: Predicted CSV file {args.csv_path} does not exist.")
        sys.exit(1)
        
    if not os.path.exists(args.gt_dir):
        print(f"Error: Ground Truth directory {args.gt_dir} does not exist.")
        sys.exit(1)
        
    print(f"Reading predictions from {args.csv_path}...")
    print(f"Reading ground truth from {args.gt_dir}...")
    
    predictions = {}
    try:
        with open(args.csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header or len(header) < 2:
                print("Error: CSV must have at least 2 columns with header (file_name, ground_truth)")
                sys.exit(1)
                
            for row in reader:
                if len(row) >= 2:
                    file_name = row[0]
                    content = row[1]
                    predictions[file_name] = content
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        sys.exit(1)
        
    print(f"Loaded {len(predictions)} predictions.")
    
    total_text_edit = 0.0
    evaluated_count = 0
    
    print("\n--- Starting Evaluation ---")
    for file_name, pred_text in sorted(predictions.items()):
        # Ground truth file matches the UUID name, but has .md extension
        base_name = os.path.splitext(file_name)[0]
        gt_file_path = os.path.join(args.gt_dir, f"{base_name}.md")
        
        if not os.path.exists(gt_file_path):
            print(f"Warning: Ground truth file {gt_file_path} not found. Skipping.")
            continue
            
        try:
            with open(gt_file_path, "r", encoding="utf-8") as f:
                gt_text = f.read()
        except Exception as e:
            print(f"Error reading ground truth {gt_file_path}: {e}. Skipping.")
            continue
            
        # Compute Levenshtein distance
        dist = rapidfuzz.distance.Levenshtein.distance(pred_text, gt_text)
        
        # Normalize by Ground Truth length
        gt_len = len(gt_text)
        if gt_len == 0:
            text_edit = 0.0 if len(pred_text) == 0 else 1.0
        else:
            text_edit = dist / gt_len
            
        text_score = max(0.0, (1.0 - text_edit) * 100.0)
        
        print(f"File: {file_name} | GT Length: {gt_len} | Pred Length: {len(pred_text)} | Distance: {dist} | Text Edit (Loss): {text_edit:.4f} | Score: {text_score:.2f}")
        
        total_text_edit += text_edit
        evaluated_count += 1
        
    if evaluated_count == 0:
        print("\nNo predictions were evaluated against ground truth.")
        sys.exit(1)
        
    avg_text_edit = total_text_edit / evaluated_count
    avg_score = (1.0 - avg_text_edit) * 100.0
    
    print("\n--- Final Evaluation Summary ---")
    print(f"Evaluated Files: {evaluated_count}")
    print(f"Average Text Edit (Normalized Loss): {avg_text_edit:.6f}")
    print(f"Average Text Score (1 - Loss) * 100: {avg_score:.2f}")

if __name__ == "__main__":
    main()
