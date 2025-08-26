import fitz  # PyMuPDF
import cv2
import numpy as np
import os

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_DIR = "extracted_diagrams"

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

diagram_count = 0
padding_ratio = 0.15  # 8% padding on each side

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
        cutoff = int(img.shape[0] * 0.25)  # remove top 25% of page 2
        img = img[cutoff:, :, :]

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)

        if w > 100 and h > 100:  # filter out small noise
            # Compute relative padding
            pad_w = int(w * padding_ratio)
            pad_h = int(h * padding_ratio)

            x1 = max(x - pad_w, 0)
            y1 = max(y - pad_h, 0)
            x2 = min(x + w + pad_w, img.shape[1])
            y2 = min(y + h + pad_h, img.shape[0])

            crop = img[y1:y2, x1:x2]

            out_path = f"{OUTPUT_DIR}/page{page_num+1}_diagram{i+1}.png"
            cv2.imwrite(out_path, crop)
            diagram_count += 1

print(f"✅ Extracted {diagram_count} diagrams into '{OUTPUT_DIR}' with ~{int(padding_ratio*100)}% extra borders")
