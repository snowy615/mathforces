import fitz  # PyMuPDF for PDF text + image extraction
import pandas as pd
from PIL import Image
import io
import os

# Input and output files
PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_EXCEL = "extracted_problems.xlsx"
IMG_DIR = "extracted_images"

# Create image folder if not exists
os.makedirs(IMG_DIR, exist_ok=True)

# Open PDF
doc = fitz.open(PDF_PATH)

problems = []
problem_number = 0

for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text("text")

    # Split into problems (rough heuristic: problems numbered 1., 2., etc.)
    lines = text.split("\n")
    for line in lines:
        if line.strip().startswith(tuple(str(i) for i in range(1, 26))):
            problem_number += 1
            problems.append({"ProblemNumber": problem_number, "Text": line.strip(), "ImagePath": ""})
        elif problem_number > 0:
            problems[-1]["Text"] += " " + line.strip()

    # Extract images from page
    images = page.get_images(full=True)
    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        img_ext = base_image["ext"]
        image = Image.open(io.BytesIO(image_bytes))

        img_filename = f"{IMG_DIR}/page{page_num+1}_img{img_index+1}.{img_ext}"
        image.save(img_filename)

        # Attach image to the last problem found on this page (approximate)
        if problems:
            problems[-1]["ImagePath"] = img_filename

# Save to Excel
df = pd.DataFrame(problems)

with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Problems")

print(f"Extraction complete! Saved to {OUTPUT_EXCEL}")