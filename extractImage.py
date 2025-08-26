import fitz  # PyMuPDF
import cv2
import numpy as np
import os

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_DIR = "extracted_diagrams"

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

diagram_count = 0
padding_ratio = 0.15  # 15% extra on each side
min_w, min_h = 80, 80  # allow slightly smaller diagrams

def rect_area(r):
    return r[2] * r[3]

def intersect_area(a, b):
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])
    w = max(0, x2 - x1)
    h = max(0, y2 - y1)
    return w * h

def merge_two(a, b):
    x1 = min(a[0], b[0])
    y1 = min(a[1], b[1])
    x2 = max(a[0] + a[2], b[0] + b[2])
    y2 = max(a[1] + a[3], b[1] + b[3])
    return (x1, y1, x2 - x1, y2 - y1)

def merge_rects(rects, iou_thresh=0.1):
    if not rects:
        return []
    merged = True
    while merged:
        merged = False
        used = [False] * len(rects)
        new_rects = []
        for i in range(len(rects)):
            if used[i]:
                continue
            a = rects[i]
            for j in range(i + 1, len(rects)):
                if used[j]:
                    continue
                b = rects[j]
                inter = intersect_area(a, b)
                if inter > 0:
                    union_area = rect_area(a) + rect_area(b) - inter
                    iou = inter / union_area if union_area > 0 else 0
                    if iou > iou_thresh:
                        a = merge_two(a, b)
                        used[j] = True
                        merged = True
            used[i] = True
            new_rects.append(a)
        rects = new_rects
    return rects

for page_num in range(len(doc)):
    # Skip first page entirely (instructions page)
    if page_num == 0:
        continue

    page = doc[page_num]

    # Render page at 300 DPI
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    # Make image array
    img = np.frombuffer(pix.samples, dtype=np.uint8)
    # reshape depends on number of channels
    img = img.reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:  # RGBA -> RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    elif pix.n == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h_img, w_img = gray.shape

    # --- Method A: adaptive threshold + morphological closing (good for filled shapes) ---
    th_adapt = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(th_adapt, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours_a, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # --- Method B: Canny edges + dilation (good for outlines / faint circles) ---
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, kernel, iterations=2)
    contours_b, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Collect bounding boxes from both methods
    boxes = []
    for cnt in contours_a + contours_b:
        x, y, w, h = cv2.boundingRect(cnt)
        if w >= min_w and h >= min_h:
            boxes.append((x, y, w, h))

    # Merge overlapping / near-duplicate boxes
    boxes = merge_rects(boxes, iou_thresh=0.08)

    # If this is page 2, we avoided the previous hard top-crop.
    # But we still want to ignore header-like regions (wide, short regions spanning most of page width)
    cutoff = int(0.25 * h_img)  # top 25% considered header zone
    final_boxes = []
    for (x, y, w, h) in boxes:
        # Heuristic: if box sits in the top area AND spans almost full width AND is relatively short,
        # assume it's the instructions header and skip it.
        if page_num == 1 and y < cutoff and w > 0.85 * w_img and h < 0.25 * h_img:
            # skip header-ish block
            continue
        final_boxes.append((x, y, w, h))

    # If nothing found (robust fallback): try relaxed detection (lower min size)
    if not final_boxes:
        fallback_min = 50
        boxset = []
        for cnt in contours_a + contours_b:
            x, y, w, h = cv2.boundingRect(cnt)
            if w >= fallback_min and h >= fallback_min:
                boxset.append((x, y, w, h))
        boxset = merge_rects(boxset, iou_thresh=0.05)
        # apply same header heuristic
        for (x, y, w, h) in boxset:
            if page_num == 1 and y < cutoff and w > 0.85 * w_img and h < 0.25 * h_img:
                continue
            final_boxes.append((x, y, w, h))

    # Save crops with relative padding
    for i, (x, y, w, h) in enumerate(final_boxes, start=1):
        pad_w = int(w * padding_ratio)
        pad_h = int(h * padding_ratio)

        x1 = max(x - pad_w, 0)
        y1 = max(y - pad_h, 0)
        x2 = min(x + w + pad_w, w_img)
        y2 = min(y + h + pad_h, h_img)

        crop = img[y1:y2, x1:x2]

        out_path = os.path.join(OUTPUT_DIR, f"page{page_num+1}_diagram{i}.png")
        cv2.imwrite(out_path, crop)
        diagram_count += 1

print(f"✅ Extracted {diagram_count} diagrams into '{OUTPUT_DIR}' (smart header filtering, padding={int(padding_ratio*100)}%)")
