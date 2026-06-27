import re
import difflib
from lxml import html
import sys
import os

# Add project root directory to path for package resolution
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Code.table_agent import config

def normalize_row(row_str):
    # Extract cell contents to perform structural normalization
    cells = re.findall(r'<td[^>]*>(.*?)</td>|<th[^>]*>(.*?)</th>', row_str, re.DOTALL | re.IGNORECASE)
    cleaned_cells = []
    for c_tuple in cells:
        content = c_tuple[0] if c_tuple[0] else c_tuple[1]
        content = re.sub(r'<[^>]+>', '', content or '').strip()
        content = re.sub(r'\s+', '', content).lower()
        cleaned_cells.append(content)
    if not cleaned_cells:
        cleaned = re.sub(r'<[^>]+>', '', row_str)
        cleaned = re.sub(r'\s+', '', cleaned).lower()
        return cleaned
    return "|".join(cleaned_cells)

def truncate_row_columns(row_str, max_allowed_cols=None):
    if max_allowed_cols is None:
        max_allowed_cols = config.MAX_ALLOWED_COLS
        
    cells = re.findall(r'<td[^>]*>.*?</td>|<th[^>]*>.*?</th>', row_str, re.DOTALL | re.IGNORECASE)
    if not cells:
        return row_str
    
    truncated_cells = []
    curr_cols = 0
    for cell in cells:
        colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', cell, re.IGNORECASE)
        cell_width = int(colspan_match.group(1)) if colspan_match else 1
        if curr_cols + cell_width <= max_allowed_cols:
            truncated_cells.append(cell)
            curr_cols += cell_width
        else:
            remaining = max_allowed_cols - curr_cols
            if remaining > 0:
                if colspan_match:
                    cell_shrunk = re.sub(r'colspan\s*=\s*["\']?\d+["\']?', f'colspan="{remaining}"', cell, flags=re.IGNORECASE)
                    truncated_cells.append(cell_shrunk)
                else:
                    truncated_cells.append(cell)
                curr_cols = max_allowed_cols
            break
            
    tr_start_match = re.match(r'<tr[^>]*>', row_str, re.IGNORECASE)
    tr_start = tr_start_match.group(0) if tr_start_match else '<tr>'
    return tr_start + "".join(truncated_cells) + "</tr>"

def deduplicate_consecutive_rows(rows, similarity_threshold=None):
    if similarity_threshold is None:
        similarity_threshold = config.ROW_SIMILARITY_THRESHOLD
        
    if not rows:
        return rows
    deduped = [rows[0]]
    last_normalized = normalize_row(rows[0])
    for r in rows[1:]:
        norm = normalize_row(r)
        if not norm and not last_normalized:
            continue
        elif not norm or not last_normalized:
            deduped.append(r)
            last_normalized = norm
        else:
            ratio = difflib.SequenceMatcher(None, norm, last_normalized).ratio()
            if ratio < similarity_threshold:
                deduped.append(r)
                last_normalized = norm
    return deduped

def repair_table_html(text):
    if bool(re.search(r'<table[^>]*>', text, re.IGNORECASE)) and not bool(re.search(r'</table>', text, re.IGNORECASE)):
        text = text + "</table>"
    match = re.search(r'<table[^>]*>.*?</table>', text, re.DOTALL | re.IGNORECASE)
    if not match:
        return text
    table_part = match.group(0)
    try:
        wrapper = f"<div>{table_part}</div>"
        doc = html.fragment_fromstring(wrapper)
        repaired = html.tostring(doc, encoding='utf-8').decode('utf-8')
        if repaired.startswith("<div>") and repaired.endswith("</div>"):
            repaired = repaired[5:-6]
        elif repaired.startswith("<div ") and repaired.endswith("</div>"):
            first_gt = repaired.find(">")
            repaired = repaired[first_gt+1:-6]
            
        rows = re.findall(r'<tr[^>]*>.*?</tr>', repaired, re.DOTALL | re.IGNORECASE)
        # 1. Deduplicate consecutive identical/highly-similar rows (VLM row-loop prevention)
        rows_deduped = deduplicate_consecutive_rows(rows, similarity_threshold=config.ROW_SIMILARITY_THRESHOLD)
        # 2. Truncate row columns (VLM col-loop prevention)
        truncated_rows = []
        for r in rows_deduped:
            truncated_rows.append(truncate_row_columns(r, max_allowed_cols=config.MAX_ALLOWED_COLS))
            
        table_start_match = re.search(r'<table[^>]*>', repaired, re.IGNORECASE)
        table_start = table_start_match.group(0) if table_start_match else '<table>'
        repaired = table_start + "\n" + "\n".join(truncated_rows) + "\n</table>"
        
        return text[:match.start()] + repaired
    except Exception as e:
        print(f"  [Warning] HTML repair failed: {e}")
        return text

def get_row_col_count(row_str):
    """
    Counts the number of cells in a row, handling colspan.
    """
    tds = re.findall(r'<td[^>]*>|<th[^>]*>', row_str, re.IGNORECASE)
    count = 0
    for td in tds:
        colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', td, re.IGNORECASE)
        if colspan_match:
            count += int(colspan_match.group(1))
        else:
            count += 1
    return count

def pad_row(row_str, target_cols):
    """
    Appends empty <td> cells to a row if it has fewer columns than target_cols.
    """
    curr_cols = get_row_col_count(row_str)
    if curr_cols >= target_cols:
        return row_str
    pad_cells = "".join(["<td></td>"] * (target_cols - curr_cols))
    repaired = re.sub(r'</tr>\s*$', f"{pad_cells}</tr>", row_str, flags=re.IGNORECASE)
    return repaired
