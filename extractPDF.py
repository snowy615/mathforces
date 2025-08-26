import fitz  # PyMuPDF
import os
from PIL import Image
import io

PDF_PATH = "2025Gauss8Contest.pdf"
OUTPUT_TEX = "gauss8_extracted.tex"
IMG_DIR = "latex_images"

# Create image folder
os.makedirs(IMG_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

problems = []
problem_number = 0

# Process all pages except first (instructions)
for page_num in range(1, len(doc)):
    page = doc[page_num]
    text = page.get_text("text")

    # Split into questions by number patterns
    lines = text.split("\n")
    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith(tuple(str(i) for i in range(1, 26))):
            problem_number += 1
            problems.append({"ProblemNumber": problem_number, "Text": line_stripped, "Images": []})
        elif problem_number > 0:
            problems[-1]["Text"] += " " + line_stripped

    # Extract images
    images = page.get_images(full=True)
    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        img_ext = base_image["ext"]
        image = Image.open(io.BytesIO(image_bytes))

        img_filename = f"{IMG_DIR}/q{problem_number}p{page_num+1}{img_index+1}.{img_ext}"
        image.save(img_filename)

        # Attach to current problem (approximation: last active problem)
        if problems:
            problems[-1]["Images"].append(img_filename)

# Ensure exactly 25 problems
problems = problems[:25]

# Write LaTeX file
with open(OUTPUT_TEX, "w", encoding="utf-8") as f:
    f.write(r"""\documentclass[12pt]{article}
\usepackage{graphicx}
\usepackage{enumitem}
\setlength{\parindent}{0pt}
\begin{document}
\section*{Extracted Gauss 8 Contest Problems}
""")

    for prob in problems:
        f.write(f"\\textbf{{Problem {prob['ProblemNumber']}}} \\\\ \n")
        f.write(prob["Text"].replace("", "\\") + "\n\n")
        for img_path in prob["Images"]:
            f.write(f"\\\\ \\includegraphics[width=0.7\\linewidth]{{{img_path}}}\n\n")
        f.write("\\vspace{1em}\n\n")

    f.write("\\end{document}")

print(f"LaTeX file written to {OUTPUT_TEX}. Compile with: pdflatex {OUTPUT_TEX}")