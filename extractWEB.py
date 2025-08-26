#!/usr/bin/env python3
"""
Download one CEMC problem print page, extract the problem text and diagrams
(correctly handling srcset, data-src, inline base64 images, style backgrounds,
and inline SVG). Save images locally and record remote URLs & local paths in Excel.

Usage:
    python extract_cemc_problem.py "https://...print.php?ids=pc6a50907-...&..."
"""

import os
import re
import requests
import base64
import mimetypes
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd

# -------- CONFIG ----------
PAGE_URL = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"
OUT_DIR = "cemc_output"
IMG_DIR = os.path.join(OUT_DIR, "images")
EXCEL_PATH = os.path.join(OUT_DIR, "questions.xlsx")
USER_AGENT = "Mozilla/5.0 (compatible; ExtractBot/1.0)"

os.makedirs(IMG_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def choose_src_from_srcset(srcset: str) -> str:
    """
    Choose the 'best' candidate from a srcset string.
    Heuristic: pick candidate with largest width descriptor (e.g. '400w')
    or the last candidate if no width numbers present.
    """
    parts = [p.strip() for p in srcset.split(",") if p.strip()]
    best_url = None
    best_w = -1
    for p in parts:
        # p typically "url 400w" or "url 2x" or just "url"
        toks = p.split()
        url_part = toks[0]
        if len(toks) > 1:
            desc = toks[1]
            m = re.match(r"(\d+)w", desc)
            if m:
                w = int(m.group(1))
                if w > best_w:
                    best_w = w
                    best_url = url_part
                continue
            m2 = re.match(r"(\d+)x", desc)
            if m2:
                # treat x as lower-quality heuristic; prefer higher multiplier
                w = int(m2.group(1)) * 1000
                if w > best_w:
                    best_w = w
                    best_url = url_part
                continue
        # fallback: if no descriptor, use last candidate
        best_url = url_part
    return best_url


def ext_from_content_type(ct: str) -> str:
    if not ct:
        return ""
    # prefer common extensions
    ct = ct.split(";")[0].strip().lower()
    ext = mimetypes.guess_extension(ct)
    if ext:
        return ext
    # some fallback cases
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "png" in ct:
        return ".png"
    if "svg" in ct:
        return ".svg"
    if "gif" in ct:
        return ".gif"
    return ""


def save_remote_image(url: str, out_dir: str, base_name: str):
    """Download remote image and return local path and final URL used."""
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except Exception:
        # sometimes the site uses relative URLs with HTML-escaped chars; try unquoting
        raise

    # determine extension
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    if not ext:
        ext = ext_from_content_type(r.headers.get("content-type", ""))
    if not ext:
        ext = ".bin"

    # ensure unique filename
    i = 0
    candidate = f"{base_name}{ext}"
    while os.path.exists(os.path.join(out_dir, candidate)):
        i += 1
        candidate = f"{base_name}_{i}{ext}"
    local_path = os.path.join(out_dir, candidate)
    with open(local_path, "wb") as f:
        f.write(r.content)
    return local_path


def save_inline_base64(data_uri: str, out_dir: str, base_name: str):
    """Decode data:image/...;base64,... and save to disk."""
    header, b64 = data_uri.split(",", 1)
    m = re.match(r"data:(image/[a-z0-9.+-]+);base64", header, re.I)
    ext = ".img"
    if m:
        ext = ext_from_content_type(m.group(1)) or ".png"
    filename = f"{base_name}{ext}"
    i = 0
    while os.path.exists(os.path.join(out_dir, filename)):
        i += 1
        filename = f"{base_name}_{i}{ext}"
    path = os.path.join(out_dir, filename)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    return path


def save_svg_string(svg_str: str, out_dir: str, base_name: str):
    filename = f"{base_name}.svg"
    i = 0
    while os.path.exists(os.path.join(out_dir, filename)):
        i += 1
        filename = f"{base_name}_{i}.svg"
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_str)
    return path


def find_problem_block(soup: BeautifulSoup):
    """
    Heuristics:
    - Prefer the element that contains 'Source:' or 'Answer:' (these are present on the print page),
      then collect that element and a few nearby siblings (previous siblings often contain diagrams).
    - Fallback: first large text block in body.
    """
    marker = soup.find(string=re.compile(r"\bSource:|\bAnswer:", re.I))
    container_nodes = []
    if marker:
        node = marker.parent
        # climb up a bit to get a segment that contains the problem text
        for _ in range(4):
            if node is None:
                break
            txt_len = len(node.get_text(" ", strip=True) or "")
            if txt_len > 30:
                break
            node = node.parent
        if node is None:
            node = soup.body or soup

        # Collect node, a few previous siblings, and next siblings
        collected = []
        # previous siblings (reverse them to get natural order)
        prevs = list(node.find_previous_siblings())
        prevs.reverse()
        for p in prevs[-3:]:  # just up to last 3 previous siblings
            collected.append(p)
        collected.append(node)
        for n in list(node.find_next_siblings())[:2]:
            collected.append(n)

        # make a new soup fragment containing the collected nodes to search images inside them
        frag = BeautifulSoup("<div></div>", "html.parser").div
        for c in collected:
            frag.append(c)
        return frag

    # Fallback: return the entire body (last resort)
    return soup.body or soup


def extract_diagrams_from_block(block: BeautifulSoup, base_url: str, qid: str):
    """
    Return two parallel lists: diagram_urls (remote URLs or 'embedded-base64' or 'svg-inline'),
    and local_paths (where we saved them).
    """
    diagram_urls = []
    local_paths = []
    idx = 0

    # 1) <img> tags and lazy attributes
    for img in block.find_all("img"):
        idx += 1
        # prefer several attributes
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy")
        srcset = img.get("srcset")
        if srcset and not src:
            src = choose_src_from_srcset(srcset)
        if not src:
            continue

        if src.startswith("data:image"):
            # inline base64
            local = save_inline_base64(src, IMG_DIR, f"{qid}_img{idx}")
            diagram_urls.append("embedded-base64")
            local_paths.append(local)
            continue

        # resolve relative
        abs_url = urljoin(base_url, src)
        try:
            local = save_remote_image(abs_url, IMG_DIR, f"{qid}_img{idx}")
            diagram_urls.append(abs_url)
            local_paths.append(local)
        except Exception as e:
            # try with srcset parsing if not already tried
            if srcset:
                try:
                    s2 = choose_src_from_srcset(srcset)
                    if s2:
                        abs2 = urljoin(base_url, s2)
                        local = save_remote_image(abs2, IMG_DIR, f"{qid}_img{idx}")
                        diagram_urls.append(abs2)
                        local_paths.append(local)
                        continue
                except Exception:
                    pass
            # give up on this image
            print(f"Warning: failed to download image {src}: {e}")
            continue

    # 2) <source> tags inside <picture> or <figure> (srcset)
    for source in block.find_all("source"):
        srcset = source.get("srcset")
        if not srcset:
            continue
        idx += 1
        chosen = choose_src_from_srcset(srcset)
        if not chosen:
            continue
        abs_url = urljoin(base_url, chosen)
        try:
            local = save_remote_image(abs_url, IMG_DIR, f"{qid}_img{idx}")
            diagram_urls.append(abs_url)
            local_paths.append(local)
        except Exception as e:
            print("Warning: failed to download source srcset", e)

    # 3) style="background-image: url(...)"
    style_url_pattern = re.compile(r"url\((['\"]?)(.*?)\1\)")
    for el in block.find_all(True):  # all tags
        style = el.get("style")
        if not style:
            continue
        m = style_url_pattern.search(style)
        if not m:
            continue
        url_part = m.group(2)
        # skip data URIs handled above
        if url_part.startswith("data:image"):
            idx += 1
            local = save_inline_base64(url_part, IMG_DIR, f"{qid}_bg{idx}")
            diagram_urls.append("embedded-base64-bg")
            local_paths.append(local)
        else:
            idx += 1
            abs_url = urljoin(base_url, url_part)
            try:
                local = save_remote_image(abs_url, IMG_DIR, f"{qid}_bg{idx}")
                diagram_urls.append(abs_url)
                local_paths.append(local)
            except Exception as e:
                print("Warning: failed to download background image", e)

    # 4) inline <svg> elements — save their outer HTML as .svg
    for svg in block.find_all("svg"):
        idx += 1
        svg_html = str(svg)
        local = save_svg_string(svg_html, IMG_DIR, f"{qid}_svg{idx}")
        diagram_urls.append("svg-inline")
        local_paths.append(local)

    return diagram_urls, local_paths


def main(url: str):
    print("Requesting:", url)
    r = session.get(url, timeout=20)
    r.raise_for_status()

    # if server returned a PDF directly, save & exit (this page usually returns HTML)
    ctype = r.headers.get("content-type", "").lower()
    if "application/pdf" in ctype or r.content[:4] == b"%PDF":
        pdf_path = os.path.join(OUT_DIR, "problem_direct.pdf")
        with open(pdf_path, "wb") as f:
            f.write(r.content)
        print("Server returned PDF; saved to", pdf_path)
        # Save Excel row pointing to PDF
        row = {
            "id": url.split("ids=")[-1].split("&")[0],
            "page_url": url,
            "problem_text": "",
            "diagram_urls": "",
            "local_images": "",
            "saved_pdf": pdf_path,
        }
        pd.DataFrame([row]).to_excel(EXCEL_PATH, index=False)
        print("Excel written to", EXCEL_PATH)
        return

    soup = BeautifulSoup(r.text, "html.parser")

    # Remove the global header text nodes to avoid picking header images
    for t in soup.find_all(string=re.compile(r"(centre for education|cemc|gauss contest|solutions)", re.I)):
        try:
            t.extract()
        except Exception:
            pass

    qid = url.split("ids=")[-1].split("&")[0]
    # find the problem block
    block = find_problem_block(soup)

    # get clean text of the block
    problem_text = block.get_text("\n", strip=True)

    diagram_urls, local_paths = extract_diagrams_from_block(block, url, qid)

    row = {
        "id": qid,
        "page_url": url,
        "problem_text": problem_text,
        "diagram_urls": ";".join(diagram_urls),
        "local_images": ";".join(local_paths),
        "saved_pdf": ""
    }
    df = pd.DataFrame([row])
    df.to_excel(EXCEL_PATH, index=False)
    print("Saved Excel:", EXCEL_PATH)
    print("Saved images to:", IMG_DIR)
    if diagram_urls:
        print("Found diagrams:", diagram_urls)
    else:
        print("No diagrams found inside the problem block (check the page visually).")


if __name__ == "__main__":
    main(PAGE_URL)
