import fitz  # PyMuPDF
import cv2
import numpy as np
import os

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_DIR = "extracted_diagrams_v2"

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

diagram_count = 0
padding = 20  # extra pixels around each crop

for page_num in range(len(doc)):
    # Skip page 1 (instructions)
    if page_num == 0:
        continue

    page = doc[page_num]

    # Render page at high resolution (300 DPI)
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:  # RGBA → RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

    # Skip top half of page 2 (instructions)
    if page_num == 1:  # second page (index 1)
        img = img[img.shape[0]//2:, :, :]  # keep only bottom half

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Adaptive threshold (better for faint diagrams)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51, 15
    )

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)

        # Filter out tiny specks, but allow medium diagrams
        if w > 80 and h > 80:
            # Add padding but stay inside image bounds
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img.shape[1], x + w + padding)
            y2 = min(img.shape[0], y + h + padding)

            crop = img[y1:y2, x1:x2]

            out_path = f"{OUTPUT_DIR}/page{page_num+1}_diagram{i+1}.png"
            cv2.imwrite(out_path, crop)
            diagram_count += 1

print(f"✅ Extracted {diagram_count} diagrams into '{OUTPUT_DIR}'")