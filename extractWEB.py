#!/usr/bin/env python3
"""
Download a single CEMC print.php question page, extract problem text and diagrams,
save images locally, and write details to an Excel sheet.

Usage:
    python download_and_extract_question.py "https://...print.php?ids=pc6a50907-...&..."
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import pandas as pd
import io

# Optional imports for PDF image extraction
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

# Optional for MIME detection
try:
    import magic
    HAS_MAGIC = True
except Exception:
    HAS_MAGIC = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Script/1.0; +https://example.com/bot)"
}

OUT_DIR = "cemc_output"
IMAGES_DIR = os.path.join(OUT_DIR, "images")
EXCEL_PATH = os.path.join(OUT_DIR, "questions_output.xlsx")

os.makedirs(IMAGES_DIR, exist_ok=True)


def get_question_id_from_url(url: str) -> str:
    """Extract the first ID from the 'ids=' query parameter (IDs are tilde-separated)."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    ids = qs.get("ids") or []
    if not ids:
        return ""
    # take first id if there are many
    first = ids[0].split("~")[0]
    return first


def is_pdf_content(response: requests.Response) -> bool:
    """Check whether a response likely contains PDF bytes."""
    ctype = response.headers.get("content-type", "").lower()
    if "application/pdf" in ctype:
        return True
    # fallback: use python-magic if available
    if HAS_MAGIC:
        ms = magic.Magic(mime=True)
        mime = ms.from_buffer(response.content[:2048])
        return "pdf" in mime
    # last-resort heuristic: check for PDF file signature
    return response.content[:4] == b"%PDF"


def save_pdf(response: requests.Response, outpath: str):
    with open(outpath, "wb") as f:
        f.write(response.content)


def extract_images_from_pdf(pdf_path: str, out_dir: str):
    """
    Extract images from a PDF using PyMuPDF (fitz). Returns list of saved image paths.
    Requires pymupdf installed.
    """
    saved = []
    if not HAS_PYMUPDF:
        print("PyMuPDF not installed; skipping PDF image extraction.")
        return saved

    doc = fitz.open(pdf_path)
    for page_index in range(len(doc)):
        page = doc[page_index]
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list, start=1):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image.get("ext", "png")
            img_name = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_p{page_index+1}_img{img_index}.{ext}"
            img_path = os.path.join(out_dir, img_name)
            with open(img_path, "wb") as f:
                f.write(image_bytes)
            saved.append(img_path)
    return saved


def find_problem_container(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Heuristics to find the element that contains the problem text and diagrams,
    while ignoring the top header that contains the CEMC logo and contest title.
    """

    # 1) Try to find obvious container ids/classes
    candidates = []
    for idname in ["printArea", "print-area", "print", "content", "main"]:
        el = soup.find(id=idname)
        if el:
            candidates.append(el)
    for cls in ["printArea", "print-area", "print", "contest", "paper", "page", "content"]:
        found = soup.find(class_=cls)
        if found:
            candidates.append(found)

    # 2) If specific container not found, look for elements with "Gauss" or "Solutions" and pick sibling that follows them
    title_el = None
    for tag in soup.find_all(text=True):
        txt = tag.strip()
        if not txt:
            continue
        lowered = txt.lower()
        if "gauss" in lowered and ("grade" in lowered or "gr." in lowered) or "solutions" in lowered:
            title_el = tag
            break
    if title_el:
        # try to get parent and then the next sibling that contains problem content
        parent = title_el.parent
        # prefer a sibling/descendant that has images or many paragraphs
        for sib in parent.find_next_siblings():
            if sib.get_text(strip=True):
                candidates.append(sib)

    # 3) Fallback: choose the largest element (by text length) in <body>
    body = soup.body or soup
    largest = None
    largest_len = 0
    for el in body.find_all(recursive=True):
        # ignore header-like elements
        if el.name in ["header", "nav", "footer", "script", "style"]:
            continue
        text_len = len(el.get_text(strip=True) or "")
        if text_len > largest_len:
            largest_len = text_len
            largest = el
    if largest:
        candidates.append(largest)

    # pick the candidate with most text that is not the obvious site header
    def score(el):
        txt = el.get_text(" ", strip=True) or ""
        # penalize elements that contain the header text
        header_markers = ["centre for education", "cemc", "centre for education in mathematics and computing",
                          "gauss contest", "solutions", "cemc.uwaterloo.ca"]
        lower = txt.lower()
        penalty = sum(1 for m in header_markers if m in lower)
        return len(txt) - penalty * 2000  # big penalty to avoid header

    best = None
    best_score = -1
    for c in candidates:
        try:
            s = score(c)
            if s > best_score:
                best_score = s
                best = c
        except Exception:
            continue

    # If still nothing, return entire body
    if best is None:
        return body
    return best


def download_images_from_element(el: BeautifulSoup, base_url: str, save_dir: str):
    """
    Find all <img> tags in element `el`, resolve their URLs relative to base_url,
    download them to save_dir, and return lists of URLs and local paths.
    """
    urls = []
    local_paths = []

    for img in el.find_all("img"):
        src = img.get("src") or ""
        if not src:
            continue
        abs_url = urljoin(base_url, src)
        # Normalize remove query fragments if you like
        urls.append(abs_url)
        try:
            r = requests.get(abs_url, headers=HEADERS)
            r.raise_for_status()
        except Exception as e:
            print(f"  Warning: couldn't download image {abs_url}: {e}")
            continue
        # create local name
        parsed = urlparse(abs_url)
        name = os.path.basename(parsed.path) or f"img_{len(local_paths)+1}.png"
        # ensure unique
        candidate = name
        i = 1
        while os.path.exists(os.path.join(save_dir, candidate)):
            candidate = f"{os.path.splitext(name)[0]}_{i}{os.path.splitext(name)[1]}"
            i += 1
        local_path = os.path.join(save_dir, candidate)
        with open(local_path, "wb") as f:
            f.write(r.content)
        local_paths.append(local_path)
    return urls, local_paths


def extract_inner_html(el: BeautifulSoup) -> str:
    return "".join(str(child) for child in el.contents)


def main(url: str):
    print("Requesting:", url)
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()

    qid = get_question_id_from_url(url) or "unknown_id"
    row = {
        "id": qid,
        "page_url": url,
        "problem_text": "",
        "problem_html": "",
        "diagram_urls": "",
        "local_diagram_paths": "",
        "saved_pdf_if_applicable": ""
    }

    # If response seems PDF, save and optionally extract images
    if is_pdf_content(resp):
        pdf_path = os.path.join(OUT_DIR, f"{qid}.pdf")
        print("Detected PDF content; saving to", pdf_path)
        save_pdf(resp, pdf_path)
        row["saved_pdf_if_applicable"] = pdf_path
        # try extracting images from pdf if possible
        pdf_images = extract_images_from_pdf(pdf_path, IMAGES_DIR) if HAS_PYMUPDF else []
        row["local_diagram_paths"] = ";".join(pdf_images)
        row["diagram_urls"] = ";".join([])  # no remote URLs known
    else:
        # treat as HTML
        html = resp.content
        soup = BeautifulSoup(html, "html.parser")

        # locate the problem container
        container = find_problem_container(soup)
        if container is None:
            container = soup.body or soup

        # Remove the known header lines if present (brute-force remove nodes that contain header strings)
        header_markers = ["centre for education", "cemc.uwaterloo.ca", "centre for education in mathematics and computing",
                          "gauss contest grade", "solutions"]
        # If container has a header child that looks like site header, remove it
        for child in list(container.find_all(recursive=False)):
            txt = (child.get_text(" ", strip=True) or "").lower()
            if any(m in txt for m in header_markers):
                child.decompose()

        # Now, clean up whitespace and extract text/html
        problem_text = container.get_text("\n", strip=True)
        problem_html = extract_inner_html(container)

        # Download images referenced within container
        diagram_urls, local_paths = download_images_from_element(container, url, IMAGES_DIR)

        row.update({
            "problem_text": problem_text,
            "problem_html": problem_html,
            "diagram_urls": ";".join(diagram_urls),
            "local_diagram_paths": ";".join(local_paths)
        })

        # If there are no images in container, try to find any images on the page (some pages place diagrams somewhere else)
        if not diagram_urls:
            all_img_urls, all_local = download_images_from_element(soup, url, IMAGES_DIR)
            if all_local:
                row["diagram_urls"] = ";".join(all_img_urls)
                row["local_diagram_paths"] = ";".join(all_local)

    # Save to Excel (append if exists)
    if os.path.exists(EXCEL_PATH):
        df = pd.read_excel(EXCEL_PATH)
    else:
        df = pd.DataFrame(columns=list(row.keys()))
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True, sort=False)
    df.to_excel(EXCEL_PATH, index=False)
    print("Saved extracted data to", EXCEL_PATH)
    print("Images saved to", IMAGES_DIR)
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_and_extract_question.py <print_page_url>")
        sys.exit(1)
    url = sys.argv[1]
    main(url)
