import fitz  # PyMuPDF
import os
from PIL import Image
import io

PDF_PATH = "2025Gauss8Contest.pdf"
IMG_DIR = "extracted_images"

# Create folder for extracted images
os.makedirs(IMG_DIR, exist_ok=True)

# Open PDF
doc = fitz.open(PDF_PATH)

image_count = 0

# Loop through each page
for page_num in range(len(doc)):
    page = doc[page_num]
    images = page.get_images(full=True)

    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]

        # Always save as PNG
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        img_filename = f"{IMG_DIR}/page{page_num+1}_img{img_index+1}.png"
        image.save(img_filename, "PNG")
        image_count += 1

print(f"✅ Extracted {image_count} images into '{IMG_DIR}'")