import requests
from bs4 import BeautifulSoup
import os
import pandas as pd

# Folder to save images
IMAGE_DIR = "diagrams"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Example page URL
url = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"

response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

# Remove top CEMC header if present
header = soup.find("div", class_="header")  # adjust if necessary
if header:
    header.decompose()

data_rows = []

# Each question block (adjust class/structure as needed)
questions = soup.find_all("div", class_="question")  # update selector if different

for idx, q in enumerate(questions, 1):
    qid = f"Q{idx}"

    # Question text
    question_text = q.find("div", class_="question-text")
    question_text = question_text.get_text(separator="\n").strip() if question_text else ""

    # Answer choices (if multiple choice)
    choices = q.find("div", class_="answer-choices")
    if choices:
        answer_choices = "; ".join([c.get_text(strip=True) for c in choices.find_all("li")])
    else:
        answer_choices = ""

    # Solution / answer
    solution_div = q.find("div", class_="solution")
    solution_text = solution_div.get_text(separator="\n").strip() if solution_div else ""

    # Answer (if explicitly given)
    answer_div = q.find("span", class_="answer")  # adjust selector
    answer_text = answer_div.get_text(strip=True) if answer_div else ""

    # Diagrams (save locally)
    diagrams = q.find_all("img")
    local_paths = []
    for i, img in enumerate(diagrams, 1):
        img_src = img.get("src")
        if img_src.startswith("data:image"):
            img_data = img_src.split(",")[1]
            import base64

            img_bytes = base64.b64decode(img_data)
            img_name = f"{qid}_diagram{i}.png"
            img_path = os.path.join(IMAGE_DIR, img_name)
            with open(img_path, "wb") as f:
                f.write(img_bytes)
            local_paths.append(img_path)

    # Row dictionary
    row = {
        "ID": qid,
        "Question": question_text,
        "Answer Choices": answer_choices,
        "Source": url,
        "Primary Topics": "",
        "Secondary Topics": "",
        "Answer": answer_text,
        "Solution": solution_text
    }

    data_rows.append(row)

# Save to Excel
df = pd.DataFrame(data_rows)
df.to_excel("Gauss_Grade8.xlsx", index=False)
print("Excel file saved as Gauss_Grade8.xlsx")
