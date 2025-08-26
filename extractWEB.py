import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

URL = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"

# --- Setup output dirs ---
OUT_DIR = "cemc_output"
IMG_DIR = os.path.join(OUT_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)

EXCEL_PATH = os.path.join(OUT_DIR, "questions.xlsx")

# --- Request page ---
resp = requests.get(URL)
resp.raise_for_status()

# --- Detect PDF or HTML ---
if resp.headers.get("content-type", "").lower().startswith("application/pdf"):
    pdf_path = os.path.join(OUT_DIR, "question.pdf")
    with open(pdf_path, "wb") as f:
        f.write(resp.content)
    print(f"PDF saved: {pdf_path}")
    # For PDFs, just record file path in Excel
    data = {
        "id": "pc6a50907-f093-11ef-b0cc-005056bc",
        "page_url": URL,
        "problem_text": "",
        "diagram_urls": "",
        "local_images": "",
        "saved_pdf": pdf_path
    }
else:
    # --- Parse HTML ---
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove top header text
    for tag in soup.find_all(text=True):
        if any(word in tag.lower() for word in ["centre for education", "cemc", "gauss contest", "solutions"]):
            tag.extract()

    # Extract main body text
    text = soup.get_text(" ", strip=True)

    # Extract images
    img_urls, local_imgs = [], []
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        abs_url = urljoin(URL, src)
        img_urls.append(abs_url)

        r = requests.get(abs_url)
        filename = os.path.basename(urlparse(abs_url).path)
        local_path = os.path.join(IMG_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(r.content)
        local_imgs.append(local_path)

    data = {
        "id": "pc6a50907-f093-11ef-b0cc-005056bc",
        "page_url": URL,
        "problem_text": text,
        "diagram_urls": ";".join(img_urls),
        "local_images": ";".join(local_imgs),
        "saved_pdf": ""
    }

# --- Save Excel ---
df = pd.DataFrame([data])
df.to_excel(EXCEL_PATH, index=False)
print(f"Excel saved: {EXCEL_PATH}")
