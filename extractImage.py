import fitz  # PyMuPDF
import cv2
import numpy as np
import os

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_DIR = "extracted_diagrams"

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

diagram_count = 0

for page_num in range(len(doc)):
    page = doc[page_num]

    # Render page at 300 DPI
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:  # RGBA → RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)

        # Filter out tiny noise (only keep reasonably big boxes)
        if w > 100 and h > 100:
            crop = img[y:y+h, x:x+w]

            out_path = f"{OUTPUT_DIR}/page{page_num+1}_diagram{i+1}.png"
            cv2.imwrite(out_path, crop)
            diagram_count += 1

print(f"✅ Extracted {diagram_count} diagrams into '{OUTPUT_DIR}'")