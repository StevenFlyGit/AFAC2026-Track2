import re
import difflib
import sys
import os

# Add project root directory to path for package resolution
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Code.table_agent.tools import validator

def split_text_to_blocks(text):
    pattern = re.compile(r'(<table[^>]*>.*?</table>)', re.DOTALL | re.IGNORECASE)
    parts = pattern.split(text)
    blocks = []
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        if i % 2 == 1:
            blocks.append({'type': 'table', 'content': part})
        else:
            blocks.append({'type': 'text', 'content': part})
    return blocks

def blocks_match(b1, b2):
    if b1['type'] != b2['type']:
        return False
    if b1['type'] == 'text':
        ratio = difflib.SequenceMatcher(None, b1['content'].strip(), b2['content'].strip()).ratio()
        return ratio > 0.7
    else:
        rows1 = re.findall(r'<tr[^>]*>.*?</tr>', b1['content'], re.DOTALL | re.IGNORECASE)
        rows2 = re.findall(r'<tr[^>]*>.*?</tr>', b2['content'], re.DOTALL | re.IGNORECASE)
        if not rows1 or not rows2: return False
        
        # --- Strip prepended header rows from rows2 ---
        max_h_len = min(5, len(rows1))
        norm_H = [validator.normalize_row(r) for r in rows1[:max_h_len]]
        max_m = min(max_h_len, len(rows2))
        match_m = 0
        for m in range(max_m, 0, -1):
            match = True
            for i in range(m):
                r2_norm = validator.normalize_row(rows2[i])
                h_norm = norm_H[i]
                if not r2_norm and not h_norm:
                    ratio = 1.0
                elif not r2_norm or not h_norm:
                    ratio = 0.0
                else:
                    ratio = difflib.SequenceMatcher(None, r2_norm, h_norm).ratio()
                if ratio < 0.85:
                    match = False
                    break
            if match:
                match_m = m
                break
        if match_m > 0:
            rows2 = rows2[match_m:]
            if not rows2: return False
        # ---------------------------------------------
        
        norm1 = [validator.normalize_row(r) for r in rows1]
        norm2 = [validator.normalize_row(r) for r in rows2]
        max_search = min(8, len(rows1), len(rows2))
        for k in range(max_search, 0, -1):
            match = True
            for i in range(k):
                r1_idx = len(rows1) - k + i
                r2_idx = i
                if norm1[r1_idx] != norm2[r2_idx]:
                    ratio = difflib.SequenceMatcher(None, norm1[r1_idx], norm2[r2_idx]).ratio()
                    if ratio < 0.85:
                        match = False
                        break
            if match:
                return True
        return False

def merge_block_lists(A_blocks, B_blocks):
    best_d = None
    best_matches_count = 0
    # Try perfect match alignment
    for d in range(len(A_blocks)):
        matches = 0
        total_compared = 0
        for j in range(len(B_blocks)):
            i = d + j
            if i >= len(A_blocks):
                break
            total_compared += 1
            if blocks_match(A_blocks[i], B_blocks[j]):
                matches += 1
        if matches > 0 and matches == total_compared:
            return d, matches
            
    # Fallback to maximum matches alignment
    for d in range(len(A_blocks)):
        matches = 0
        for j in range(len(B_blocks)):
            i = d + j
            if i >= len(A_blocks):
                break
            if blocks_match(A_blocks[i], B_blocks[j]):
                matches += 1
        if matches > best_matches_count:
            best_matches_count = matches
            best_d = d
            
    if best_matches_count > 0:
        return best_d, best_matches_count
    return None, 0

def merge_table_html_pair(t1_html, t2_html):
    rows1 = re.findall(r'<tr[^>]*>.*?</tr>', t1_html, re.DOTALL | re.IGNORECASE)
    rows2 = re.findall(r'<tr[^>]*>.*?</tr>', t2_html, re.DOTALL | re.IGNORECASE)
    if not rows1: return t2_html
    if not rows2: return t1_html
    
    # --- Row Prefix Matching (m) ---
    max_h_len = min(5, len(rows1))
    norm_H = [validator.normalize_row(r) for r in rows1[:max_h_len]]
    
    max_m = min(max_h_len, len(rows2))
    match_m = 0
    
    for m in range(max_m, 0, -1):
        match = True
        for i in range(m):
            r2_norm = validator.normalize_row(rows2[i])
            h_norm = norm_H[i]
            if not r2_norm and not h_norm:
                ratio = 1.0
            elif not r2_norm or not h_norm:
                ratio = 0.0
            else:
                ratio = difflib.SequenceMatcher(None, r2_norm, h_norm).ratio()
            
            if ratio < 0.85:
                match = False
                break
        if match:
            match_m = m
            break
            
    if match_m > 0:
        print(f"  [Row Prefix Match] Found m={match_m} matching header rows. Stripping them.")
        rows2 = rows2[match_m:]
        if not rows2:
            return t1_html
    # --------------------------------
    
    cols1 = [validator.get_row_col_count(r) for r in rows1]
    cols2 = [validator.get_row_col_count(r) for r in rows2]
    max_cols = max(max(cols1) if cols1 else 0, max(cols2) if cols2 else 0)
    
    rows1_padded = [validator.pad_row(r, max_cols) for r in rows1]
    rows2_padded = [validator.pad_row(r, max_cols) for r in rows2]
    
    norm1 = [validator.normalize_row(r) for r in rows1_padded]
    norm2 = [validator.normalize_row(r) for r in rows2_padded]
    
    overlap_size = 0
    max_search = min(8, len(rows1_padded), len(rows2_padded))
    for k in range(max_search, 0, -1):
        match = True
        for i in range(k):
            r1_idx = len(rows1_padded) - k + i
            r2_idx = i
            if norm1[r1_idx] != norm2[r2_idx]:
                ratio = difflib.SequenceMatcher(None, norm1[r1_idx], norm2[r2_idx]).ratio()
                if ratio < 0.85:
                    match = False
                    break
        if match:
            overlap_size = k
            break
            
    if overlap_size > 0:
        start_idx = overlap_size
        while start_idx < len(rows2_padded):
            first_row = rows2_padded[start_idx]
            if validator.normalize_row(first_row) == norm1[0]:
                start_idx += 1
            else:
                break
        combined_rows = rows1_padded + rows2_padded[start_idx:]
        table_start_match = re.search(r'<table[^>]*>', t1_html, re.IGNORECASE)
        table_start = table_start_match.group(0) if table_start_match else '<table border="1" cellpadding="8" cellspacing="0">'
        return table_start + "\n" + "\n".join(combined_rows) + "\n</table>"
    else:
        combined_rows = rows1_padded + rows2_padded
        table_start_match = re.search(r'<table[^>]*>', t1_html, re.IGNORECASE)
        table_start = table_start_match.group(0) if table_start_match else '<table border="1" cellpadding="8" cellspacing="0">'
        return table_start + "\n" + "\n".join(combined_rows) + "\n</table>"

def merge_markdown_pair(text1, text2, max_overlap_chars=1200):
    if not text1: return text2
    if not text2: return text1
    s1 = text1[-max_overlap_chars:]
    s2 = text2[:max_overlap_chars]
    matcher = difflib.SequenceMatcher(None, s1, s2)
    blocks = [b for b in matcher.get_matching_blocks() if b.size >= 4]
    if not blocks:
        return text1 + "\n\n" + text2
    best_k = None
    best_ratio = 0.0
    candidate_ks = set()
    for b in blocks:
        k = len(s1) - (b.a - b.b)
        if 10 <= k <= len(s2) and k <= len(s1):
            candidate_ks.add(k)
    for k in sorted(candidate_ks):
        sub_s1 = s1[-k:]
        sub_s2 = s2[:k]
        ratio = difflib.SequenceMatcher(None, sub_s1, sub_s2).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_k = k
    if best_ratio > 0.8 and best_k is not None:
        return text1.rstrip() + "\n\n" + text2[best_k:].lstrip()
    return text1 + "\n\n" + text2

def merge_two_texts(text1, text2):
    t1 = validator.repair_table_html(text1)
    t2 = validator.repair_table_html(text2)
    
    A_blocks = split_text_to_blocks(t1)
    B_blocks = split_text_to_blocks(t2)
    
    first_table_A_content = None
    for b in A_blocks:
        if b['type'] == 'table':
            first_table_A_content = b['content']
            break
    if first_table_A_content:
        for b in B_blocks:
            if b['type'] == 'table':
                rows1 = re.findall(r'<tr[^>]*>.*?</tr>', first_table_A_content, re.DOTALL | re.IGNORECASE)
                rows2 = re.findall(r'<tr[^>]*>.*?</tr>', b['content'], re.DOTALL | re.IGNORECASE)
                if rows1 and rows2:
                    max_h_len = min(5, len(rows1))
                    norm_H = [validator.normalize_row(r) for r in rows1[:max_h_len]]
                    max_m = min(max_h_len, len(rows2))
                    match_m = 0
                    for m in range(max_m, 0, -1):
                        match = True
                        for i in range(m):
                            r2_norm = validator.normalize_row(rows2[i])
                            h_norm = norm_H[i]
                            if not r2_norm and not h_norm:
                                ratio = 1.0
                            elif not r2_norm or not h_norm:
                                ratio = 0.0
                            else:
                                ratio = difflib.SequenceMatcher(None, r2_norm, h_norm).ratio()
                            if ratio < 0.85:
                                match = False
                                break
                        if match:
                            match_m = m
                            break
                    if match_m > 0:
                        rows2 = rows2[match_m:]
                        table_start_match = re.search(r'<table[^>]*>', b['content'], re.IGNORECASE)
                        table_start = table_start_match.group(0) if table_start_match else '<table>'
                        b['content'] = table_start + "\n" + "\n".join(rows2) + "\n</table>"
                break
                
    d, matches = merge_block_lists(A_blocks, B_blocks)
    if d is not None and matches > 0:
        print(f"  [Merge] Alignment found at offset d={d} with matches={matches}")
        merged_blocks = []
        merged_blocks.extend(A_blocks[:d])
        for k in range(len(A_blocks) - d):
            if k < len(B_blocks):
                blk_A = A_blocks[d + k]
                blk_B = B_blocks[k]
                if blk_A['type'] == 'table':
                    merged_content = merge_table_html_pair(blk_A['content'], blk_B['content'])
                    merged_blocks.append({'type': 'table', 'content': merged_content})
                else:
                    merged_content = merge_markdown_pair(blk_A['content'], blk_B['content'])
                    merged_blocks.append({'type': 'text', 'content': merged_content})
            else:
                merged_blocks.append(A_blocks[d + k])
        overlap_len_in_B = len(A_blocks) - d
        if overlap_len_in_B < len(B_blocks):
            merged_blocks.extend(B_blocks[overlap_len_in_B:])
            
        return "\n\n".join([b['content'] for b in merged_blocks])
    else:
        last_table_idx_A = None
        for i in range(len(A_blocks) - 1, -1, -1):
            if A_blocks[i]['type'] == 'table':
                last_table_idx_A = i
                break
        first_table_idx_B = None
        for i in range(len(B_blocks)):
            if B_blocks[i]['type'] == 'table':
                first_table_idx_B = i
                break
                
        if last_table_idx_A is not None and first_table_idx_B is not None:
            print(f"  [Merge] No block-level alignment, force merging last table of A and first table of B.")
            merged_content = merge_table_html_pair(A_blocks[last_table_idx_A]['content'], B_blocks[first_table_idx_B]['content'])
            A_blocks[last_table_idx_A]['content'] = merged_content
            suffix_B = B_blocks[:first_table_idx_B] + B_blocks[first_table_idx_B + 1:]
            return "\n\n".join([b['content'] for b in A_blocks] + [b['content'] for b in suffix_B])
            
        print("  [Merge] No block-level alignment and no tables to force-merge, falling back to simple concatenation.")
        return t1 + "\n\n" + t2

def merge_table_slices(chunk_texts):
    if not chunk_texts:
        return ""
    repaired_texts = []
    for text in chunk_texts:
        if text is not None:
            repaired_texts.append(validator.repair_table_html(text))
        else:
            repaired_texts.append("")
            
    if not repaired_texts:
        return ""
    if len(repaired_texts) == 1:
        return repaired_texts[0]
        
    final_text = repaired_texts[0]
    for next_text in repaired_texts[1:]:
        final_text = merge_two_texts(final_text, next_text)
    return final_text

def merge_left_right_html_smart(left_html, right_html):
    """
    Merges Left and Right HTML tables of a vertically split slice using index-based alignment of table rows.
    """
    if not left_html: return right_html
    if not right_html: return left_html
    
    rows_left = re.findall(r'<tr[^>]*>.*?</tr>', left_html, re.DOTALL | re.IGNORECASE)
    rows_right = re.findall(r'<tr[^>]*>.*?</tr>', right_html, re.DOTALL | re.IGNORECASE)
    
    if not rows_left: return right_html
    if not rows_right: return left_html
    
    def get_cells(row_str):
        return re.findall(r'<td[^>]*>.*?</td>|<th[^>]*>.*?</th>', row_str, re.DOTALL | re.IGNORECASE)
        
    def get_cell_similarity(c1, c2):
        t1 = re.sub(r'<[^>]+>', '', c1).strip()
        t2 = re.sub(r'<[^>]+>', '', c2).strip()
        if not t1 and not t2:
            return 1.0
        if not t1 or not t2:
            return 0.0
        return difflib.SequenceMatcher(None, t1, t2).ratio()

    max_cells_left = max(len(get_cells(r)) for r in rows_left) if rows_left else 0
    cell_threshold = max(3, int(max_cells_left * 0.5))
    
    table_idx_left = [i for i, r in enumerate(rows_left) if len(get_cells(r)) >= cell_threshold]
    table_idx_right = [i for i, r in enumerate(rows_right) if len(get_cells(r)) >= cell_threshold]
    
    if not table_idx_left or not table_idx_right:
        table_idx_left = list(range(len(rows_left)))
        table_idx_right = list(range(len(rows_right)))
        
    min_table_rows = min(len(table_idx_left), len(table_idx_right))
    
    merged_rows = []
    if table_idx_left and table_idx_left[0] > 0:
        merged_rows.extend(rows_left[:table_idx_left[0]])
        
    for k in range(min_table_rows):
        idx_l = table_idx_left[k]
        idx_r = table_idx_right[k]
        
        r_left = rows_left[idx_l]
        r_right = rows_right[idx_r]
        
        cells_left = get_cells(r_left)
        cells_right = get_cells(r_right)
        
        if not cells_left:
            merged_rows.append(r_left)
        elif not cells_right:
            merged_rows.append(r_left)
        else:
            max_k = min(4, len(cells_left), len(cells_right))
            match_k = 1
            for candidate_k in range(max_k, 0, -1):
                match = True
                for j in range(candidate_k):
                    if get_cell_similarity(cells_left[j], cells_right[j]) < 0.8:
                        match = False
                        break
                if match:
                    match_k = candidate_k
                    break
            
            merged_cells = cells_left + cells_right[match_k:]
            tr_start_match = re.match(r'<tr[^>]*>', r_left, re.IGNORECASE)
            tr_start = tr_start_match.group(0) if tr_start_match else '<tr>'
            merged_rows.append(f"  {tr_start}" + "".join(merged_cells) + "</tr>")
        
        if k < min_table_rows - 1:
            next_idx_l = table_idx_left[k+1]
            if next_idx_l > idx_l + 1:
                merged_rows.extend(rows_left[idx_l+1:next_idx_l])
            
    if table_idx_left and len(table_idx_left) > min_table_rows:
        last_table_idx = table_idx_left[min_table_rows-1]
        merged_rows.extend(rows_left[last_table_idx+1:])
    elif table_idx_left:
        last_table_idx = table_idx_left[-1]
        merged_rows.extend(rows_left[last_table_idx+1:])
        
    table_start_match = re.search(r'<table[^>]*>', left_html, re.IGNORECASE)
    table_start = table_start_match.group(0) if table_start_match else '<table border="1" cellpadding="8" cellspacing="0">'
    return table_start + "\n" + "\n".join(merged_rows) + "\n</table>"
