import os
import argparse
import csv
import sys
import re

# Ensure local packages (like rapidfuzz) in the Code folder can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import rapidfuzz
except ImportError:
    rapidfuzz = None
    import difflib

# APTED imports for TEDS
try:
    from apted import APTED, Config
    from apted.helpers import Tree
except ImportError:
    APTED = None
    class Config:
        pass
    Tree = object

class TableTree(Tree):
    def __init__(self, tag, colspan=1, rowspan=1, content="", *children):
        self.tag = tag
        self.colspan = int(colspan) if colspan else 1
        self.rowspan = int(rowspan) if rowspan else 1
        self.content = content if content else ""
        self.children = list(children)

    def bracket(self):
        """Show tree using brackets notation"""
        if self.tag in ('td', 'th'):
            # Clean content of curly braces which break apted bracket parsing
            clean_content = self.content.replace('{', '').replace('}', '').replace('[', '').replace(']', '')
            result = '"tag": "%s", "colspan": %d, "rowspan": %d, "text": "%s"' % \
                     (self.tag, self.colspan, self.rowspan, clean_content)
        else:
            result = '"tag": "%s"' % self.tag
        for child in self.children:
            result += child.bracket()
        return "{{{}}}".format(result)

class CustomConfig(Config):
    def rename(self, node1, node2):
        """Compares attributes of trees"""
        if (node1.tag != node2.tag) or (node1.colspan != node2.colspan) or (node1.rowspan != node2.rowspan):
            return 1.0
        if node1.tag in ('td', 'th'):
            if node1.content or node2.content:
                if not node1.content or not node2.content:
                    return 1.0
                max_len = max(len(node1.content), len(node2.content))
                if max_len == 0:
                    return 0.0
                # Calculate Levenshtein distance
                if rapidfuzz:
                    dist = rapidfuzz.distance.Levenshtein.distance(node1.content, node2.content)
                else:
                    import difflib
                    matcher = difflib.SequenceMatcher(None, node1.content, node2.content)
                    dist = max_len - matcher.find_longest_match(0, len(node1.content), 0, len(node2.content)).size
                return float(dist) / max_len
        return 0.0

def html_to_table_tree(html_str, max_rows=15, max_cols=15):
    from lxml import etree
    parser = etree.HTMLParser()
    try:
        # Wrap in <html><body> if not present
        if not html_str.strip().startswith('<html'):
            html_str = f"<html><body>{html_str}</body></html>"
        tree = etree.fromstring(html_str.encode('utf-8'), parser)
    except Exception as e:
        print(f"Failed to parse HTML string with lxml: {e}")
        return None
        
    table_elem = tree.find('.//table')
    if table_elem is None:
        return None
        
    # Downsample rows if they exceed max_rows
    trs = table_elem.findall('.//tr')
    n_rows = len(trs)
    if n_rows > max_rows:
        keep_indices = set(list(range(max_rows - 5)) + list(range(n_rows - 5, n_rows)))
        for idx, tr in enumerate(trs):
            if idx not in keep_indices:
                tr.getparent().remove(tr)
                
    # Downsample columns if they exceed max_cols
    for tr in table_elem.findall('.//tr'):
        cells = tr.findall('./td') + tr.findall('./th')
        n_cols = len(cells)
        if n_cols > max_cols:
            keep_col_indices = set(list(range(max_cols - 5)) + list(range(n_cols - 5, n_cols)))
            for idx, cell in enumerate(cells):
                if idx not in keep_col_indices:
                    cell.getparent().remove(cell)
        
    def to_table_tree(elem):
        tag = elem.tag.lower()
        if tag not in ('table', 'thead', 'tbody', 'tr', 'th', 'td'):
            # Flatten non-table children (like b, span, etc.)
            children = []
            for child in elem:
                child_tree = to_table_tree(child)
                if isinstance(child_tree, list):
                    children.extend(child_tree)
                elif child_tree:
                    children.append(child_tree)
            return children
            
        colspan = elem.get('colspan', '1')
        rowspan = elem.get('rowspan', '1')
        
        # Content extraction
        content_parts = []
        if elem.text:
            content_parts.append(elem.text.strip())
        for child in elem:
            if child.tail:
                content_parts.append(child.tail.strip())
        content = " ".join([p for p in content_parts if p])
        
        children = []
        for child in elem:
            child_tree = to_table_tree(child)
            if isinstance(child_tree, list):
                children.extend(child_tree)
            elif child_tree:
                children.append(child_tree)
                
        return TableTree(tag, colspan, rowspan, content, *children)
        
    res = to_table_tree(table_elem)
    if isinstance(res, list):
        if len(res) > 0:
            return res[0]
        return None
    return res

def calculate_teds_score(pred_md, gt_md, structure_only=False):
    if APTED is None:
        print("  [Warning] APTED library not imported. TEDS metric cannot be evaluated accurately.")
        return 0.0
        
    # Extract all HTML tables from prediction and ground truth
    pred_tables = re.findall(r'<table[^>]*>.*?</table>', pred_md, re.DOTALL | re.IGNORECASE)
    gt_tables = re.findall(r'<table[^>]*>.*?</table>', gt_md, re.DOTALL | re.IGNORECASE)
    
    if not pred_tables and not gt_tables:
        return 1.0
    if not pred_tables or not gt_tables:
        return 0.0
        
    teds_scores = []
    max_len = max(len(pred_tables), len(gt_tables))
    
    for i in range(max_len):
        if i >= len(pred_tables) or i >= len(gt_tables):
            teds_scores.append(0.0)
            continue
            
        pred_t_html = pred_tables[i]
        gt_t_html = gt_tables[i]
        
        pred_tt = html_to_table_tree(pred_t_html)
        gt_tt = html_to_table_tree(gt_t_html)
        
        if pred_tt is None or gt_tt is None:
            if pred_tt is None and gt_tt is None:
                teds_scores.append(1.0)
            else:
                teds_scores.append(0.0)
            continue
            
        try:
            if structure_only:
                class StructuralConfig(Config):
                    def rename(self, node1, node2):
                        if (node1.tag != node2.tag) or (node1.colspan != node2.colspan) or (node1.rowspan != node2.rowspan):
                            return 1.0
                        return 0.0
                config = StructuralConfig()
            else:
                config = CustomConfig()
                
            apted = APTED(pred_tt, gt_tt, config)
            ted = apted.compute_edit_distance()
            
            def count_nodes(node):
                return 1 + sum(count_nodes(child) for child in node.children)
                
            n_pred = count_nodes(pred_tt)
            n_gt = count_nodes(gt_tt)
            max_nodes = max(n_pred, n_gt)
            
            if max_nodes == 0:
                score = 1.0
            else:
                score = 1.0 - (float(ted) / max_nodes)
            teds_scores.append(score)
        except Exception as e:
            print(f"Error computing TEDS for table index {i}: {e}")
            teds_scores.append(0.0)
            
    return sum(teds_scores) / max_len

def split_to_blocks(text):
    raw_blocks = text.split("\n\n")
    cleaned_blocks = []
    for b in raw_blocks:
        b = b.strip()
        if b:
            cleaned_blocks.append(b)
    return cleaned_blocks

def list_levenshtein_distance(seq1, seq2):
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i-1] == seq2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(
                    dp[i-1][j] + 1,    # deletion
                    dp[i][j-1] + 1,    # insertion
                    dp[i-1][j-1] + 1   # substitution
                )
    return dp[m][n]

def calculate_read_order_score(pred_text, gt_text):
    pred_blocks = split_to_blocks(pred_text)
    gt_blocks = split_to_blocks(gt_text)
    
    if not pred_blocks and not gt_blocks:
        return 1.0
    if not pred_blocks or not gt_blocks:
        return 0.0
        
    gt_ids = list(range(1, len(gt_blocks) + 1))
    pred_ids = []
    next_id = len(gt_blocks) + 1
    
    for pb in pred_blocks:
        best_match_idx = -1
        best_sim = 0.0
        for idx, gb in enumerate(gt_blocks):
            if rapidfuzz:
                sim = rapidfuzz.fuzz.ratio(pb, gb) / 100.0
            else:
                import difflib
                sim = difflib.SequenceMatcher(None, pb, gb).ratio()
            if sim > best_sim:
                best_sim = sim
                best_match_idx = idx
                
        if best_sim >= 0.8:
            pred_ids.append(gt_ids[best_match_idx])
        else:
            pred_ids.append(next_id)
            next_id += 1
            
    # Calculate list-level Levenshtein distance
    if rapidfuzz:
        dist = rapidfuzz.distance.Levenshtein.distance(pred_ids, gt_ids)
    else:
        dist = list_levenshtein_distance(pred_ids, gt_ids)
        
    max_len = max(len(pred_ids), len(gt_ids))
    if max_len == 0:
        return 1.0
    loss = dist / max_len
    return max(0.0, 1.0 - loss)

def main():
    csv.field_size_limit(10**7)
    parser = argparse.ArgumentParser(description="AFAC2026 Track 2 Local Evaluation (Text Edit, Table TEDS, and Read Order)")
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
        try:
            with open(args.csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                rows = list(reader)
        except UnicodeDecodeError:
            print("  [Notice] CSV is not UTF-8 encoded. Retrying with GBK CP936 encoding...")
            with open(args.csv_path, "r", encoding="gbk", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                rows = list(reader)
                
        if not header or len(header) < 2:
            print("Error: CSV must have at least 2 columns with header (file_name, ground_truth)")
            sys.exit(1)
            
        for row in rows:
            if len(row) >= 2:
                file_name = row[0]
                content = row[1]
                predictions[file_name] = content
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        sys.exit(1)
        
    print(f"Loaded {len(predictions)} predictions.")
    
    total_text_edit = 0.0
    total_teds = 0.0
    total_read_order = 0.0
    evaluated_count = 0
    
    print("\n--- Starting Evaluation ---")
    for file_name, pred_text in sorted(predictions.items()):
        # Ground truth file matches the UUID name, but has .md extension
        base_name = os.path.splitext(os.path.basename(file_name))[0]
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
            
        # 1. Compute Text Edit Distance
        gt_len = len(gt_text)
        if rapidfuzz:
            dist = rapidfuzz.distance.Levenshtein.distance(pred_text, gt_text)
            if gt_len == 0:
                text_edit = 0.0 if len(pred_text) == 0 else 1.0
            else:
                text_edit = dist / gt_len
            text_score = max(0.0, (1.0 - text_edit) * 100.0)
        else:
            matcher = difflib.SequenceMatcher(None, pred_text, gt_text)
            ratio = matcher.ratio()  # strict ratio
            text_score = ratio * 100.0
            dist = -1  # Not Available
            text_edit = 1.0 - ratio
            
        # 2. Compute Table TEDS
        teds_sim = calculate_teds_score(pred_text, gt_text, structure_only=False)
        teds_score = teds_sim * 100.0
        
        # 3. Compute Read Order Score
        read_order_sim = calculate_read_order_score(pred_text, gt_text)
        read_order_score = read_order_sim * 100.0
        
        # 4. Compute Overall Score
        overall = (text_score + teds_score + read_order_score) / 3.0
        
        print(f"File: {file_name}")
        print(f"  -> Text Edit Loss: {text_edit:.4f} | Text Score: {text_score:.2f}")
        print(f"  -> Table TEDS: {teds_score:.2f}")
        print(f"  -> Read Order Score: {read_order_score:.2f}")
        print(f"  -> Overall File Score: {overall:.2f}")
        
        total_text_edit += text_edit
        total_teds += teds_score
        total_read_order += read_order_score
        evaluated_count += 1
        
    if evaluated_count == 0:
        print("\nNo predictions were evaluated against ground truth.")
        sys.exit(1)
        
    avg_text_edit = total_text_edit / evaluated_count
    avg_text_score = (1.0 - avg_text_edit) * 100.0
    avg_teds_score = total_teds / evaluated_count
    avg_read_order_score = total_read_order / evaluated_count
    avg_overall_score = (avg_text_score + avg_teds_score + avg_read_order_score) / 3.0
    
    print("\n--- Final Evaluation Summary ---")
    print(f"Evaluated Files: {evaluated_count}")
    print(f"Average Text Edit (Normalized Loss): {avg_text_edit:.6f}")
    print(f"Average Text Score (1 - Loss) * 100: {avg_text_score:.2f}")
    print(f"Average Table TEDS Score: {avg_teds_score:.2f}")
    print(f"Average Read Order Score: {avg_read_order_score:.2f}")
    print(f"=========================================")
    print(f"FINAL OVERALL ESTIMATED SCORE: {avg_overall_score:.2f}")
    print(f"=========================================")

if __name__ == "__main__":
    main()
