import fitz  # PyMuPDF
import cv2
import numpy as np
import os

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_DIR = "extracted_diagrams_v3"

# Tunables
DPI = 400                       # high-res render for clean crops
TOP_SKIP_RATIO_P2 = 0.35        # skip top 35% of page 2 (instructions)
MIN_W, MIN_H = 80, 80           # ignore tiny specks
PAD_SCALE = 0.12                # 12% of max(w,h)
PAD_PX_MIN = 40                 # +40 px extra padding
KERNEL_FRACTION = 0.006         # morphology kernel ~0.6% of min(img dim)
MERGE_GAP = 40                  # px gap at which boxes are merged
IOU_TO_MERGE = 0.30             # union overlapping boxes if IoU >= 0.30
CONTAINED_RATIO = 0.90          # drop box if 90%+ area inside a bigger one

os.makedirs(OUTPUT_DIR, exist_ok=True)

def to_pix(page, dpi):
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    return page.get_pixmap(matrix=mat, alpha=False)

def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter == 0: return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / float(area_a + area_b - inter)

def contained_ratio(inner, outer):
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    if ix1 >= ox1 and iy1 >= oy1 and ix2 <= ox2 and iy2 <= oy2:
        ia = (ix2 - ix1) * (iy2 - iy1)
        oa = (ox2 - ox1) * (oy2 - oy1)
        return ia / max(oa, 1)
    return 0.0

def merge_boxes(rects):
    # Remove boxes fully contained in larger ones
    rects = sorted(rects, key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True)
    keep = []
    for i, r in enumerate(rects):
        drop = False
        for j, s in enumerate(rects):
            if j == i: continue
            if contained_ratio(r, s) >= CONTAINED_RATIO:
                drop = True
                break
        if not drop:
            keep.append(r)
    rects = keep

    # Iteratively merge overlapping/nearby rectangles
    changed = True
    while changed:
        changed = False
        new_rects = []
        used = [False]*len(rects)

        for i in range(len(rects)):
            if used[i]: continue
            ax1, ay1, ax2, ay2 = rects[i]
            merged = False
            for j in range(i+1, len(rects)):
                if used[j]: continue
                bx1, by1, bx2, by2 = rects[j]

                # Expand each box by MERGE_GAP to allow “nearby” unions
                ex1, ey1, ex2, ey2 = ax1 - MERGE_GAP, ay1 - MERGE_GAP, ax2 + MERGE_GAP, ay2 + MERGE_GAP
                fx1, fy1, fx2, fy2 = bx1 - MERGE_GAP, by1 - MERGE_GAP, bx2 + MERGE_GAP, by2 + MERGE_GAP

                # Check overlap/nearby via IoU or expanded-overlap
                if iou(rects[i], rects[j]) >= IOU_TO_MERGE or not (ex2 < bx1 or fx2 < ax1 or ex1 > bx2 or fx1 > ax2 or ey2 < by1 or fy2 < ay1 or ey1 > by2 or fy1 > ay2):
                    # Union
                    nx1, ny1 = min(ax1, bx1), min(ay1, by1)
                    nx2, ny2 = max(ax2, bx2), max(ay2, by2)
                    ax1, ay1, ax2, ay2 = nx1, ny1, nx2, ny2
                    used[j] = True
                    merged = True
                    changed = True
            used[i] = True
            new_rects.append((ax1, ay1, ax2, ay2))

        rects = new_rects

    return rects

doc = fitz.open(PDF_PATH)
diagram_count = 0

for page_idx in range(len(doc)):
    # Skip page 1 (index 0)
    if page_idx == 0:
        continue

    page = doc[page_idx]
    pix = to_pix(page, DPI)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

    # Skip top of page 2 (index 1)
    y_offset = 0
    if page_idx == 1:  # page 2
        cut = int(img.shape[0] * TOP_SKIP_RATIO_P2)
        img = img[cut:, :, :]
        y_offset = cut  # only matters if you want original coords; crops don't need it

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Adaptive threshold to catch faint lines (e.g., circle arrays in Q1)
    thr = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51, 15
    )

    # Morphology to join parts of the same diagram (prevents “per quadrant” crops)
    k = int(min(img.shape[0], img.shape[1]) * KERNEL_FRACTION)
    k = max(7, k | 1)  # odd and >=7
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)

    # Find contours on the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    rects = []
    H, W = img.shape[:2]
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < MIN_W or h < MIN_H:
            continue
        # Convert to x1,y1,x2,y2
        rects.append((x, y, x + w, y + h))

    # Merge & dedup boxes to avoid “full + quadrants” duplicates
    rects = merge_boxes(rects)

    # Sort left-to-right, top-to-bottom for nicer naming
    rects.sort(key=lambda r: (r[1], r[0]))

    for i, (x1, y1, x2, y2) in enumerate(rects, start=1):
        w, h = x2 - x1, y2 - y1
        pad = int(max(w, h) * PAD_SCALE) + PAD_PX_MIN

        # Apply generous padding on all four sides
        px1 = max(0, x1 - pad)
        py1 = max(0, y1 - pad)
        px2 = min(W, x2 + pad)
        py2 = min(H, y2 + pad)


        crop = img[py1:py2, px1:px2]
        out_path = os.path.join(OUTPUT_DIR, f"page{page_idx+1}_diagram{i}.png")
        cv2.imwrite(out_path, crop)
        diagram_count += 1

print(f"✅ Extracted {diagram_count} diagrams into '{OUTPUT_DIR}'")