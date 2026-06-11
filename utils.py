from PIL import Image
import os

Image.MAX_IMAGE_PIXELS = None

def slice_image(image_path, cache_dir, chunk_height=5000, overlap_pct=0.15):
    """
    Slices a long document image into multiple vertical chunks with overlap.
    If the image height is less than chunk_height, it returns the original image.
    
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
    step = chunk_height - overlap_height
    
    y_start = 0
    chunk_idx = 0
    
    while y_start < height:
        y_end = min(y_start + chunk_height, height)
        
        # Ensure we don't crop a tiny sliver at the very end
        # If the remaining part is less than overlap_height, we just expand the last slice
        if height - y_end < overlap_height and chunk_idx > 0:
            y_end = height
            
        box = (0, y_start, width, y_end)
        chunk_img = img.crop(box)
        
        # Convert to Grayscale to save file size (document text doesn't need color)
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
            'y_end': y_end
        })
        
        if y_end >= height:
            break
            
        y_start += step
        chunk_idx += 1
        
    return slices
