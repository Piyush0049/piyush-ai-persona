import os
import sys


def extract_pdf_text(pdf_path):
    print(f"Attempting to extract text from: {pdf_path}")
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except ImportError:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except ImportError:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except ImportError:
        pass

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except ImportError:
        pass

    print("No PDF extraction library available. Trying to install pypdf...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

if __name__ == "__main__":
    candidates = [
        "D:\\Downloads\\Piyush_Joshi_NSUT_CV.pdf",
        "D:\\Downloads\\PiyushJoshiResume.pdf",
        "D:\\Downloads\\piyush_joshi_resume.pdf"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                txt = extract_pdf_text(c)
                out_path = c.replace(".pdf", "_extracted.txt")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(txt)
                print(f"Extracted to {out_path} ({len(txt)} chars)")
            except Exception as e:
                print(f"Error extracting {c}: {e}")
        else:
            print(f"Not found: {c}")
