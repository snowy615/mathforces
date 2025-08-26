import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import base64

url = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

# Folder for diagrams
IMAGE_DIR = "diagrams"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Skip the top header
content = soup.find_all(["p", "img"])
data_rows = []

qid = 1
question_text = ""
solution_text = ""
answer_text = ""
diagrams = []

for elem in content:
    text = elem.get_text(strip=True) if elem.name != "img" else ""

    # Check if it's a new question (usually starts with a number)
    if text.startswith(str(qid)):
        if question_text:
            # Save previous question
            data_rows.append({
                "ID": f"Q{qid - 1}",
                "Question": question_text,
                "Answer Choices": "",
                "Source": url,
                "Primary Topics": "",
                "Secondary Topics": "",
                "Answer": answer_text,
                "Solution": solution_text
            })
            question_text = ""
            solution_text = ""
            answer_text = ""
            diagrams = []
        question_text = text
        qid += 1
    elif "Solution" in text or "Answer" in text:
        solution_text += text + "\n"
    else:
        question_text += "\n" + text

    # Handle images
    if elem.name == "img" and elem.get("src", "").startswith("data:image"):
        img_data = elem["src"].split(",")[1]
        img_bytes = base64.b64decode(img_data)
        img_name = f"Q{qid - 1}_diagram.png"
        img_path = os.path.join(IMAGE_DIR, img_name)
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        diagrams.append(img_path)

# Save last question
if question_text:
    data_rows.append({
        "ID": f"Q{qid - 1}",
        "Question": question_text,
        "Answer Choices": "",
        "Source": url,
        "Primary Topics": "",
        "Secondary Topics": "",
        "Answer": answer_text,
        "Solution": solution_text
    })

# Export to Excel
df = pd.DataFrame(data_rows)
df.to_excel("Gauss_Grade8.xlsx", index=False)
print("Excel file saved with questions and diagrams!")
