from PIL import Image
import os
import numpy as np

Image.MAX_IMAGE_PIXELS = None

def detect_vertical_gutter(img, min_gutter_width=80):
    """
    Detects if the image has a vertical split layout (left and right columns)
    by analyzing the vertical projection (column sums) in the center 40%-60% region.
    Returns the X coordinate of the center of the gutter, or None if no split is found.
    """
    width, height = img.size
    left_bound = int(width * 0.40)
    right_bound = int(width * 0.60)
    
    middle_region = img.crop((left_bound, 0, right_bound, height)).convert('L')
    arr = np.array(middle_region)
    
    median_val = np.median(arr)
    if median_val > 127:
        text_pixels = arr < (median_val - 20)
    else:
        text_pixels = arr > (median_val + 20)
        
    col_sums = np.sum(text_pixels, axis=0)
    blank_threshold = max(1, int(height * 0.001))
    
    is_blank = col_sums <= blank_threshold
    
    max_len = 0
    best_start = -1
    
    curr_len = 0
    curr_start = -1
    
    for i, blank in enumerate(is_blank):
        if blank:
            if curr_len == 0:
                curr_start = i
            curr_len += 1
        else:
            if curr_len > max_len:
                max_len = curr_len
                best_start = curr_start
            curr_len = 0
            
    if curr_len > max_len:
        max_len = curr_len
        best_start = curr_start
        
    if max_len >= min_gutter_width:
        gutter_center_in_crop = best_start + max_len // 2
        gutter_center_x = left_bound + gutter_center_in_crop
        print(f"  [Gutter Detected] Found vertical gutter of width {max_len}px centered at X={gutter_center_x}")
        return gutter_center_x
        
    return None

def split_left_right_images(image_path, cache_dir, gutter_x):
    """
    Splits a side-by-side image into Left and Right column images at gutter_x.
    Saves them in cache_dir and returns paths.
    """
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return None, None
        
    width, height = img.size
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    
    left_img = img.crop((0, 0, gutter_x, height))
    right_img = img.crop((gutter_x, 0, width, height))
    
    left_path = os.path.join(cache_dir, f"{base_name}_col_left.jpg")
    right_path = os.path.join(cache_dir, f"{base_name}_col_right.jpg")
    
    left_img.convert('L').save(left_path, 'JPEG', quality=80)
    right_img.convert('L').save(right_path, 'JPEG', quality=80)
    
    return left_path, right_path

def segment_table_regions(img, min_gap_height=None, blank_threshold=3, max_merge_dist=40):
    """
    Segments a table page/column vertically into regions (stacked tables)
    using adaptive horizontal projection analysis.
    """
    width, height = img.size
    img_l = img.convert('L')
    arr = np.array(img_l)
    
    median_val = np.median(arr)
    if median_val > 127:
        text_pixels = arr < (median_val - 20)
    else:
        text_pixels = arr > (median_val + 20)
        
    row_sums = np.sum(text_pixels, axis=1)
    
    text_rows = np.where(row_sums >= blank_threshold)[0]
    if len(text_rows) == 0:
        return [(0, height)]
        
    active_y_start = max(0, text_rows[0] - 20)
    active_y_end = min(height - 1, text_rows[-1] + 20)
    
    is_blank = row_sums <= blank_threshold
    gaps = []
    text_blocks = []
    
    curr_gap_start = None
    curr_text_start = None
    
    for y in range(active_y_start, active_y_end + 1):
        if is_blank[y]:
            if curr_gap_start is None:
                curr_gap_start = y
            if curr_text_start is not None:
                text_blocks.append((curr_text_start, y))
                curr_text_start = None
        else:
            if curr_text_start is None:
                curr_text_start = y
            if curr_gap_start is not None:
                gaps.append((curr_gap_start, y))
                curr_gap_start = None
                
    if curr_gap_start is not None:
        gaps.append((curr_gap_start, active_y_end + 1))
    if curr_text_start is not None:
        text_blocks.append((curr_text_start, active_y_end + 1))
        
    if len(text_blocks) > 0:
        block_heights = [b[1] - b[0] for b in text_blocks]
        small_blocks = [h for h in block_heights if h < 100]
        if len(small_blocks) > 0:
            avg_row_height = np.median(small_blocks)
        else:
            avg_row_height = 15.0
    else:
        avg_row_height = 15.0
        
    if min_gap_height is None:
        min_gap_height = max(12, int(avg_row_height * 1.4))
        
    large_gaps = [g for g in gaps if (g[1] - g[0]) >= min_gap_height]
    
    merged_gaps = []
    if large_gaps:
        curr_gap = large_gaps[0]
        for next_gap in large_gaps[1:]:
            dist = next_gap[0] - curr_gap[1]
            if dist <= max_merge_dist:
                curr_gap = (curr_gap[0], next_gap[1])
            else:
                merged_gaps.append(curr_gap)
                curr_gap = next_gap
        merged_gaps.append(curr_gap)
        
    regions = []
    curr_start = active_y_start
    for gap_start, gap_end in merged_gaps:
        region_end = max(curr_start, gap_start)
        if region_end - curr_start > 50:
            regions.append((curr_start, region_end))
        curr_start = gap_end
        
    if active_y_end - curr_start > 50:
        regions.append((curr_start, active_y_end))
        
    if not regions:
        regions.append((active_y_start, active_y_end))
        
    return regions
