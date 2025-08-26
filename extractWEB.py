import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import base64

URL = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"

# --- Setup output dirs ---
OUT_DIR = "cemc_output"
IMG_DIR = os.path.join(OUT_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)

EXCEL_PATH = os.path.join(OUT_DIR, "questions.xlsx")

# --- Request page ---
resp = requests.get(URL)
resp.raise_for_status()

# --- Parse HTML ---
soup = BeautifulSoup(resp.text, "html.parser")

# Remove top header text
for tag in soup.find_all(string=True):  # fixed deprecation warning
    if any(word in tag.lower() for word in ["centre for education", "cemc", "gauss contest", "solutions"]):
        tag.extract()

# Extract main body text
text = soup.get_text(" ", strip=True)

# Extract images
img_urls, local_imgs = [], []
for i, img in enumerate(soup.find_all("img")):
    src = img.get("src")
    if not src:
        continue

    if src.startswith("data:image"):
        # Base64 image
        header, b64data = src.split(",", 1)
        ext = header.split("/")[1].split(";")[0]  # e.g. png, jpeg
        filename = f"inline_{i}.{ext}"
        local_path = os.path.join(IMG_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(base64.b64decode(b64data))
        local_imgs.append(local_path)
        img_urls.append("embedded-base64")
    else:
        # Normal image URL
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
}

# --- Save Excel ---
df = pd.DataFrame([data])
df.to_excel(EXCEL_PATH, index=False)
print(f"✅ Done! Excel saved at: {EXCEL_PATH}")
print(f"Images saved inside: {IMG_DIR}")
