import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import base64
import re

url = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

IMAGE_DIR = "diagrams"
os.makedirs(IMAGE_DIR, exist_ok=True)

content = soup.find_all(["p", "img"])
data_rows = []

qid = 1
question_text = ""
answer_choices = ""
source = ""
primary_topics = ""
secondary_topics = ""
answer = ""
solution_text = ""

for elem in content:
    text = elem.get_text(strip=True) if elem.name != "img" else ""

    # Check for metadata lines in solution text
    if text.startswith("Source:"):
        source = text.replace("Source:", "").strip()
        continue
    elif text.startswith("Primary Topics:"):
        primary_topics = text.replace("Primary Topics:", "").strip()
        continue
    elif text.startswith("Secondary Topics:"):
        secondary_topics = text.replace("Secondary Topics:", "").strip()
        continue
    elif text.startswith("Answer:"):
        answer = text.replace("Answer:", "").strip()
        continue
    elif text.startswith("Solution:"):
        solution_text += text.replace("Solution:", "").strip() + "\n"
        continue

    # Identify new question
    if text.startswith(str(qid)):
        if question_text:
            data_rows.append({
                "ID": f"Q{qid - 1}",
                "Question": question_text.strip(),
                "Answer Choices": answer_choices.strip(),
                "Source": source,
                "Primary Topics": primary_topics,
                "Secondary Topics": secondary_topics,
                "Answer": answer,
                "Solution": solution_text.strip()
            })
            # Reset for next question
            question_text = ""
            answer_choices = ""
            solution_text = ""
            source = ""
            primary_topics = ""
            secondary_topics = ""
            answer = ""
        question_text = text
        qid += 1
    else:
        # Append text to current question
        question_text += "\n" + text

    # Handle images
    if elem.name == "img" and elem.get("src", "").startswith("data:image"):
        img_data = elem["src"].split(",")[1]
        img_bytes = base64.b64decode(img_data)
        img_name = f"Q{qid - 1}_diagram.png"
        img_path = os.path.join(IMAGE_DIR, img_name)
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        # Add diagram link to solution
        solution_text += f"\n[Diagram: {img_path}]"

# Save last question
if question_text:
    data_rows.append({
        "ID": f"Q{qid - 1}",
        "Question": question_text.strip(),
        "Answer Choices": answer_choices.strip(),
        "Source": source,
        "Primary Topics": primary_topics,
        "Secondary Topics": secondary_topics,
        "Answer": answer,
        "Solution": solution_text.strip()
    })

df = pd.DataFrame(data_rows)
df.to_excel("Gauss_Grade8_corrected.xlsx", index=False)
print("Excel file saved with correct classification!")
