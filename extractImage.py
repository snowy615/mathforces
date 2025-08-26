import fitz  # PyMuPDF
import cv2
import numpy as np
import os

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_DIR = "extracted_diagrams"

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

diagram_count = 0
padding = 30  # adjust padding for larger borders

for page_num in range(len(doc)):
    # Skip first page entirely
    if page_num == 0:
        continue

    page = doc[page_num]

    # Render page at 300 DPI
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:  # RGBA → RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

    # --- Skip top part of page 2 (instructions) ---
    if page_num == 1:
        # Crop away the top 25% of page 2 before processing
        cutoff = int(img.shape[0] * 0.25)
        img = img[cutoff:, :, :]

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)

        # Filter out tiny noise (only keep reasonably big boxes)
        if w > 100 and h > 100:
            # Expand bounding box with padding
            x1 = max(x - padding, 0)
            y1 = max(y - padding, 0)
            x2 = min(x + w + padding, img.shape[1])
            y2 = min(y + h + padding, img.shape[0])

            crop = img[y1:y2, x1:x2]

            out_path = f"{OUTPUT_DIR}/page{page_num+1}_diagram{i+1}.png"
            cv2.imwrite(out_path, crop)
            diagram_count += 1

print(f"✅ Extracted {diagram_count} diagrams into '{OUTPUT_DIR}' (skipped instructions)")
