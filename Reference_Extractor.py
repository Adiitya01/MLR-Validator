import fitz 
import re

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using PyMuPDF"""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text")
    doc.close()
    return text

def clean_references_text(text):
    """Extract only References section and stop at BD footer."""
    start = re.search(r"References\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
    if not start:
        return ""
    refs_text = start.group(1)

    stop = re.search(r"(BD, the BD Logo|Becton, Dickinson)", refs_text, flags=re.IGNORECASE)
    if stop:
        refs_text = refs_text[:stop.start()]

    return refs_text.strip()

def extract_references(text):
    """Extract references by capturing from each number until the next number."""
    refs_text = clean_references_text(text)
    if not refs_text:
        return {}

    pattern = r"(\d{1,2})[.)]\s+(.*?)(?=\s+\d{1,2}[.)]\s+|$)"
    matches = re.findall(pattern, refs_text, flags=re.DOTALL)

    references = {}
    for num, ref_text in matches:
        ref_text = ref_text.replace("\n", " ")
        ref_text = re.sub(r"\s+", " ", ref_text).strip()
        references[num] = ref_text

    return references


