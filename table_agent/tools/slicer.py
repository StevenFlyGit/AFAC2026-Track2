from PIL import Image
import os
import numpy as np

Image.MAX_IMAGE_PIXELS = None

def find_optimal_cut_table(img, y_target, y_min, y_max):
    """
    Finds the optimal horizontal split point near y_target within [y_min, y_max].
    Uses raw horizontal projection (no dilation) to locate actual row gaps (minima).
    """
    width, height = img.size
    crop_left = int(width * 0.05)
    crop_right = int(width * 0.95)
    
    window = img.crop((crop_left, y_min, crop_right, y_max)).convert('L')
    arr = np.array(window)
    
    median_val = np.median(arr)
    if median_val > 127:
        text_pixels = arr < (median_val - 20)
    else:
        text_pixels = arr > (median_val + 20)
        
    row_sums = np.sum(text_pixels, axis=1)
    
    min_sum = np.min(row_sums)
    max_sum = np.max(row_sums)
    
    threshold = min_sum + (max_sum - min_sum) * 0.05
    candidate_indices = np.where(row_sums <= threshold)[0]
    
    if len(candidate_indices) > 0:
        distances = np.abs((y_min + candidate_indices) - y_target)
        best_idx = candidate_indices[np.argmin(distances)]
        return y_min + best_idx
    else:
        min_indices = np.where(row_sums == min_sum)[0]
        distances = np.abs((y_min + min_indices) - y_target)
        best_idx = min_indices[np.argmin(distances)]
        return y_min + best_idx

def slice_image_table(image_path, cache_dir, chunk_height=400, overlap_pct=0.15, region_coords=None, region_idx=0):
    """
    Slices an image horizontally into vertical chunks using our optimal cut algorithm.
    Also handles vertical splitting into Left and Right halves if active width > 2000px.
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
    img_l = img.convert('L')
    
    if region_coords:
        active_y_start, active_y_end = region_coords
    else:
        arr = np.array(img_l)
        median_val = np.median(arr)
        if median_val > 127:
            text_mask = arr < (median_val - 20)
        else:
            text_mask = arr > (median_val + 20)
            
        row_sums = np.sum(text_mask, axis=1)
        text_rows = np.where(row_sums >= 3)[0]
        
        if len(text_rows) == 0:
            print(f"  [Slicing] No text found in image {image_path}. Skipping.")
            return []
            
        active_y_start = max(0, text_rows[0] - 20)
        active_y_end = min(height - 1, text_rows[-1] + 20)

    active_height = active_y_end - active_y_start
    print(f"  [Slicing] Region Y range: {active_y_start} to {active_y_end} (active height: {active_height}px)")
    
    arr = np.array(img_l)
    median_val = np.median(arr)
    if median_val > 127:
        text_mask = arr < (median_val - 20)
    else:
        text_mask = arr > (median_val + 20)
        
    col_sums = np.sum(text_mask[active_y_start:active_y_end, :], axis=0)
    text_cols = np.where(col_sums >= 3)[0]
    if len(text_cols) == 0:
        print(f"  [Slicing] No columns found in region. Skipping.")
        return []
        
    col_min = max(0, text_cols[0] - 20)
    col_max = min(width - 1, text_cols[-1] + 20)
    active_w = col_max - col_min
    
    should_vsplit = active_w > 2000
    print(f"  [Slicing] Region active column range: {col_min} to {col_max} (width: {active_w}px). should_vsplit={should_vsplit}")
    
    row_sums_region = np.sum(text_mask[active_y_start:active_y_end, :], axis=1)
    is_blank_region = row_sums_region <= 3
    text_blocks_region = []
    curr_start_region = None
    for y in range(len(row_sums_region)):
        if not is_blank_region[y]:
            if curr_start_region is None:
                curr_start_region = y
        else:
            if curr_start_region is not None:
                text_blocks_region.append(y - curr_start_region)
                curr_start_region = None
    if curr_start_region is not None:
        text_blocks_region.append(len(row_sums_region) - curr_start_region)
    
    small_blocks_region = [h for h in text_blocks_region if h < 100]
    if len(small_blocks_region) > 0:
        avg_row_height = np.median(small_blocks_region)
    else:
        avg_row_height = 18.0
        
    header_height = max(60, min(100, int(avg_row_height * 2.5)))
    actual_header_height = min(header_height, active_height)
    header_img = img_l.crop((0, active_y_start, width, active_y_start + actual_header_height))

    def prepare_slice(chunk_img, idx, y_start, y_end):
        is_first_slice = (y_start == active_y_start)
        
        if not is_first_slice:
            combined_h = actual_header_height + chunk_img.height
            working_img = Image.new('L', (width, combined_h))
            working_img.paste(header_img, (0, 0))
            working_img.paste(chunk_img, (0, actual_header_height))
        else:
            working_img = chunk_img
            
        w_c, h_c = working_img.size
        
        if not should_vsplit:
            scale = min(3000.0 / w_c, 1500.0 / h_c)
            new_w = int(w_c * scale)
            new_h = int(h_c * scale)
            resized = working_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            out_path = os.path.join(cache_dir, f"{base_name}_region_{region_idx}_chunk_{idx}.jpg")
            resized.save(out_path, 'JPEG', quality=85, optimize=True)
            return {'path': out_path, 'y_start': y_start, 'y_end': y_end}
        else:
            split_x = col_min + active_w // 2
            left_img = working_img.crop((col_min, 0, min(w_c, split_x + 50), h_c))
            
            row_header_w = min(300, active_w // 3)
            row_header = working_img.crop((col_min, 0, col_min + row_header_w, h_c))
            
            right_img = working_img.crop((max(0, split_x - 50), 0, col_max, h_c))
            
            right_w_actual = right_img.size[0]
            combined_right = Image.new('L', (row_header_w + right_w_actual, h_c))
            combined_right.paste(row_header, (0, 0))
            combined_right.paste(right_img, (row_header_w, 0))
            
            wl, hl = left_img.size
            scale_l = min(2048.0 / wl, 1500.0 / hl)
            left_resized = left_img.resize((int(wl * scale_l), int(hl * scale_l)), Image.Resampling.LANCZOS)
            
            wr, hr = combined_right.size
            scale_r = min(2048.0 / wr, 1500.0 / hr)
            right_resized = combined_right.resize((int(wr * scale_r), int(hr * scale_r)), Image.Resampling.LANCZOS)
            
            out_left = os.path.join(cache_dir, f"{base_name}_region_{region_idx}_chunk_{idx}_left.jpg")
            out_right = os.path.join(cache_dir, f"{base_name}_region_{region_idx}_chunk_{idx}_right.jpg")
            
            left_resized.save(out_left, 'JPEG', quality=85, optimize=True)
            right_resized.save(out_right, 'JPEG', quality=85, optimize=True)
            
            return {
                'path_left': out_left,
                'path_right': out_right,
                'y_start': y_start,
                'y_end': y_end
            }

    if active_height <= chunk_height:
        v_cropped = img_l.crop((0, active_y_start, width, active_y_end))
        slice_info = prepare_slice(v_cropped, "noslice", active_y_start, active_y_end)
        print(f"  [Noslice] Generated slice_info: {list(slice_info.keys())}")
        return [slice_info]
        
    slices = []
    overlap_height = int(chunk_height * overlap_pct)
    y_curr = active_y_start
    chunk_idx = 0
    
    while y_curr < active_y_end:
        y_target_end = y_curr + chunk_height
        
        if y_target_end < active_y_end:
            search_range = min(150, int(chunk_height * 0.3))
            y_min = max(y_curr + int(chunk_height * 0.5), y_target_end - search_range)
            y_max = min(active_y_end - 50, y_target_end + search_range)
            
            if y_min < y_max:
                y_actual_end = find_optimal_cut_table(img, y_target_end, y_min, y_max)
            else:
                y_actual_end = y_target_end
        else:
            y_actual_end = active_y_end
            
        if active_y_end - y_actual_end < overlap_height and chunk_idx > 0:
            y_actual_end = active_y_end
            
        box = (0, y_curr, width, y_actual_end)
        chunk_img = img_l.crop(box)
        
        slice_info = prepare_slice(chunk_img, chunk_idx, y_curr, y_actual_end)
        slices.append(slice_info)
        print(f"  [Slice {chunk_idx}] Generated slice_info: {list(slice_info.keys())}, rows {y_curr} to {y_actual_end}")
        
        if y_actual_end >= active_y_end:
            break
            
        y_curr = y_actual_end - overlap_height
        chunk_idx += 1
        
    return slices
