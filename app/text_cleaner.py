# app/text_cleaner.py

# Action: The text_cleaner takes the raw HTML/Text and strips away "noise" like navigation menus, 
# footer links, and excessive white space.

import re

def clean_text(text: str) -> str:
    """Cleans text by removing excessive whitespace and non-standard characters."""
    if not text:
        return ""
    # Replace multiple whitespaces/newlines with a single space
    text = re.sub(r"\s+", " ", text)
    # Remove characters that are likely noise, but keep punctuation and common symbols
    # Keeping: a-z, A-Z, 0-9, common punctuation, symbols like $, %, &
    text = re.sub(r"[^a-zA-Z0-9\s.,!?;:()\'\"$%\-&]", "", text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """
    Chunks text into segments of approximate word count with overlap.
    Overlap helps maintain context between chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    i = 0
    while i < len(words):
        # Create a chunk of 'chunk_size' words
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        
        # Move forward by (chunk_size - overlap)
        i += (chunk_size - overlap)
        
        # Break if we've reached the end
        if i >= len(words):
            break
            
    return chunks

