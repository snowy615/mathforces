import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import base64

URL = "https://cemc2.math.uwaterloo.ca/contest/PSG/school/print.php?ids=pc6a50907-f093-11ef-b0cc-005056bc&h=y&t=Gauss%20Gr.%208&type=solutions&openSolutions=false"
IMAGE_DIR = "diagrams"
os.makedirs(IMAGE_DIR, exist_ok=True)

response = requests.get(URL)
soup = BeautifulSoup(response.text, "html.parser")

data_rows = []
problems = soup.select("div.problemcontent > ol > li")

for idx, problem in enumerate(problems):
    qid = f"Q{idx}"

    # Extract question text (excluding answer choices)
    question_parts = []
    for child in problem.children:
        if child.name == "ol" and "choices" in child.get("class", []):
            break  # stop before choices
        if hasattr(child, "get_text"):
            question_parts.append(child.get_text(" ", strip=True))
    question_text = " ".join(question_parts)

    # Extract answer choices
    choices_list = []
    choices_ol = problem.select_one("ol.choices")
    if choices_ol:
        for li in choices_ol.find_all("li", recursive=False):
            choice_label = li.get("class", [""])[-1].replace("choice", "")
            choice_text = li.get_text(" ", strip=True)
            choices_list.append(f"{choice_label}: {choice_text}")
    answer_choices = " | ".join(choices_list)

    # Extract solution info (Source, Topics, Answer, Solution)
    # These are often in the text of the page after problemcontent
    solution_info = problem.find_next("div", class_="solution")
    source = primary_topics = secondary_topics = answer = solution_text = ""
    if solution_info:
        text_lines = solution_info.get_text("\n", strip=True).split("\n")
        for line in text_lines:
            if line.startswith("Source:"):
                source = line.replace("Source:", "").strip()
            elif line.startswith("Primary Topics:"):
                primary_topics = line.replace("Primary Topics:", "").strip()
            elif line.startswith("Secondary Topics:"):
                secondary_topics = line.replace("Secondary Topics:", "").strip()
            elif line.startswith("Answer:"):
                answer = line.replace("Answer:", "").strip()
            else:
                solution_text += line + "\n"

    data_rows.append({
        "ID": qid,
        "Question": question_text,
        "Answer Choices": answer_choices,
        "Source": source,
        "Primary Topics": primary_topics,
        "Secondary Topics": secondary_topics,
        "Answer": answer,
        "Solution": solution_text.strip()
    })

df = pd.DataFrame(data_rows)
df.to_excel("Gauss_Grade8_final.xlsx", index=False)
print("Excel file saved with answer choices properly extracted!")
