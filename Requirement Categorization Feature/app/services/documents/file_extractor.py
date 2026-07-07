import docx
import pandas as pd
import pdfplumber


async def extract_text_from_file(upload_file):
    filename = upload_file.filename.lower()

    # PDF
    if filename.endswith(".pdf"):
        with pdfplumber.open(upload_file.file) as pdf:
            text = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
            return "\n".join(text)

    # DOCX
    if filename.endswith(".docx"):
        doc = docx.Document(upload_file.file)
        return "\n".join(p.text for p in doc.paragraphs)

    # TXT
    if filename.endswith(".txt"):
        content = await upload_file.read()
        return content.decode("utf-8", errors="ignore")

    # CSV
    if filename.endswith(".csv"):
        df = pd.read_csv(upload_file.file)
        return "\n".join(df.astype(str).values.flatten())

    # Excel
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        df = pd.read_excel(upload_file.file)
        return "\n".join(df.astype(str).values.flatten())

    raise ValueError("Unsupported file type")
