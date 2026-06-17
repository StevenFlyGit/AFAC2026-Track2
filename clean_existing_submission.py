import csv
import re
import os

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

def clean_entire_text(text):
    """
    Cleans already stitched text which contains multiple ```markdown ... ``` chunks.
    Since the previous script stitched chunks directly with "\n\n",
    we can split by the start of ```markdown or ``` and clean each piece.
    """
    if not text:
        return ""
    
    # Let's split using regex to find code block wrappers and strip them.
    # A robust way is to find all occurrences of ```markdown and ``` and remove them,
    # but since there could be legitimate code blocks inside (though unlikely for these financial documents),
    # we can split by common delimiters or simply replace all ```markdown / ```.
    # In these financial documents, any ```markdown or ``` is almost certainly an API wrapper.
    cleaned = text
    cleaned = re.sub(r'(?i)```markdown\n?', '', cleaned)
    cleaned = re.sub(r'```\n?', '', cleaned)
    return cleaned.strip()

def main():
    csv_path = "f:/ProgramProject/AFAC2026/Track2/Code/submission.csv"
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    print(f"Reading and cleaning {csv_path}...")
    cleaned_rows = []
    
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        cleaned_rows.append(header)
        
        for row in reader:
            if len(row) >= 2:
                file_name = os.path.basename(row[0])
                content = row[1]
                cleaned_content = clean_entire_text(content)
                cleaned_rows.append([file_name, cleaned_content])
                
    # Overwrite the original submission.csv with the cleaned version
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(cleaned_rows)
        print("Cleaned CSV written successfully to submission.csv!")
    except PermissionError:
        fallback_path = "f:/ProgramProject/AFAC2026/Track2/Code/submission_cleaned.csv"
        print(f"Warning: submission.csv is locked. Saving cleaned results to {fallback_path} instead.")
        with open(fallback_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(cleaned_rows)

if __name__ == "__main__":
    main()
