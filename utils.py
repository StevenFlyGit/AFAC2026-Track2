from PIL import Image
import os
import numpy as np
import difflib


Image.MAX_IMAGE_PIXELS = None

def find_optimal_cut(img, y_target, y_min, y_max):
    """
    Finds the optimal horizontal line to cut the image between y_min and y_max
    using horizontal projection.
    
    1. First tries to find a completely blank line (pure color background).
    2. If no blank line is found, falls back to the line with the minimum text density.
    """
    width, height = img.size
    
    # Analyze the horizontal projection of the crop window.
    # To avoid vertical margins, borders, or page edges from polluting the projection,
    # we crop the middle 90% horizontally (from 5% to 95% of the width).
    crop_left = int(width * 0.05)
    crop_right = int(width * 0.95)
    
    window = img.crop((crop_left, y_min, crop_right, y_max)).convert('L')
    arr = np.array(window)
    
    # Adaptive thresholding based on the median value.
    # Text pixels will be True, background pixels will be False.
    median_val = np.median(arr)
    if median_val > 127:
        text_pixels = arr < (median_val - 20)
    else:
        text_pixels = arr > (median_val + 20)
        
    row_sums = np.sum(text_pixels, axis=1)
    
    # Blank threshold: 0.1% of the analyzed horizontal width
    analyzed_width = crop_right - crop_left
    blank_threshold = max(1, int(analyzed_width * 0.001))
    
    blank_indices = np.where(row_sums <= blank_threshold)[0]
    
    if len(blank_indices) > 0:
        # Find the blank row closest to y_target
        distances = np.abs((y_min + blank_indices) - y_target)
        best_idx = blank_indices[np.argmin(distances)]
        return y_min + best_idx
    else:
        # Fallback: find the row with the minimum text density
        min_density = np.min(row_sums)
        min_indices = np.where(row_sums == min_density)[0]
        distances = np.abs((y_min + min_indices) - y_target)
        best_idx = min_indices[np.argmin(distances)]
        return y_min + best_idx

def slice_image(image_path, cache_dir, chunk_height=5000, overlap_pct=0.15):
    """
    Slices a long document image into multiple vertical chunks with overlap,
    using smart "empty space avoidance" (避空) slicing.
    
    Args:
        image_path (str): Path to the source image.
        cache_dir (str): Directory to save slice chunks.
        chunk_height (int): Height of each slice.
        overlap_pct (float): Overlap percentage between adjacent slices (e.g., 0.15 for 15%).
        
    Returns:
        list of dict: A list containing information about each slice, e.g.,
                      [{'path': ..., 'y_start': ..., 'y_end': ...}]
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
        
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return []
        
    width, height = img.size
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    
    # If the image height is smaller than or equal to the chunk height, no slicing needed
    if height <= chunk_height:
        return [{'path': image_path, 'y_start': 0, 'y_end': height}]
        
    slices = []
    overlap_height = int(chunk_height * overlap_pct)
    
    y_start = 0
    chunk_idx = 0
    
    while y_start < height:
        y_target_end = y_start + chunk_height
        
        # Determine search range for the cut point if we are not at the very end
        if y_target_end < height:
            # We search within ±500px around y_target_end
            search_range = 500
            # Ensure search bounds do not exceed image height or crop too small a chunk
            y_min = max(y_start + 1000, y_target_end - search_range)
            y_max = min(height - 500, y_target_end + search_range)
            
            if y_min < y_max:
                y_actual_end = find_optimal_cut(img, y_target_end, y_min, y_max)
            else:
                y_actual_end = y_target_end
        else:
            y_actual_end = height
            
        # Ensure we don't crop a tiny sliver at the very end.
        # If the remaining part is less than overlap_height, we just expand the last slice
        if height - y_actual_end < overlap_height and chunk_idx > 0:
            y_actual_end = height
            
        box = (0, y_start, width, y_actual_end)
        chunk_img = img.crop(box)
        
        # Convert to Grayscale to save file size
        chunk_img = chunk_img.convert('L')
        
        # Resize width to 1000px to speed up API processing and reduce timeout rate
        w_curr, h_curr = chunk_img.size
        if w_curr > 1000:
            scale = 1000.0 / w_curr
            new_w = 1000
            new_h = int(h_curr * scale)
            chunk_img = chunk_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        chunk_filename = f"{base_name}_chunk_{chunk_idx}.jpg"
        chunk_path = os.path.join(cache_dir, chunk_filename)
        
        chunk_img.save(chunk_path, 'JPEG', quality=75, optimize=True)
        
        slices.append({
            'path': chunk_path,
            'y_start': y_start,
            'y_end': y_actual_end
        })
        
        if y_actual_end >= height:
            break
            
        # The next slice starts with overlap_height overlap from the actual end
        y_start = y_actual_end - overlap_height
        chunk_idx += 1
        
    return slices

def merge_markdown_pair(text1, text2, max_overlap_chars=1200):
    """
    Merges two markdown document chunks by aligning and removing their overlap.
    Uses SequenceMatcher to find candidate alignment offsets, and verifies them
    using a similarity ratio.
    """
    if not text1:
        return text2
    if not text2:
        return text1
        
    s1 = text1[-max_overlap_chars:]
    s2 = text2[:max_overlap_chars]
    
    matcher = difflib.SequenceMatcher(None, s1, s2)
    matching_blocks = matcher.get_matching_blocks()
    
    # Filter blocks to discard spurious tiny matches (like single spaces/commas)
    blocks = [b for b in matching_blocks if b.size >= 4]
    
    if not blocks:
        return text1 + "\n\n" + text2
        
    best_k = None
    best_ratio = 0.0
    
    # An alignment block (a, b, size) in s1 and s2 implies s2[b] aligns with s1[a].
    # This aligns s2[0] with s1[a - b].
    # So the overlap length k = len(s1) - (a - b).
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
            
    # We require a high similarity ratio (e.g. > 0.8) to consider it a valid overlap
    if best_ratio > 0.8 and best_k is not None:
        non_overlap_text2 = text2[best_k:]
        return text1.rstrip() + "\n\n" + non_overlap_text2.lstrip()
    else:
        return text1 + "\n\n" + text2
