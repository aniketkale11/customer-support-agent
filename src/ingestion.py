"""
Phase 2: Document Ingestion Module
==================================
This module is the final, production-grade ingestion pipeline for our agent:
1. Loads our 39-page enterprise manual ('Apex_Electronics_Customer_Support_Manual.pdf') using pdfplumber.
2. Extracts text while preserving tables as clean Markdown tables.
3. Splits documents into semantic chunks using RecursiveCharacterTextSplitter.
4. Attaches rich metadata (source, page_number, chunk_id, has_table) to every chunk.
"""

from pathlib import Path
from typing import List, Optional
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_PDF_PATH = DATA_DIR / "Apex_Electronics_Customer_Support_Manual.pdf"


def table_to_markdown(table: List[List[Optional[str]]]) -> str:
    """
    Convert a 2D table array extracted by pdfplumber into clean Markdown table syntax.
    Cleans internal newlines from cells and ensures proper column alignment.
    """
    if not table or not table[0]:
        return ""

    cleaned_rows = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                # Replace newlines inside cells with space to keep rows on a single line
                cell_str = str(cell).replace("\n", " ").strip()
                cell_str = cell_str.replace("\ufffd", "-")
                cleaned_row.append(cell_str)
        cleaned_rows.append(cleaned_row)

    headers = cleaned_rows[0]
    num_cols = len(headers)

    md_lines = []
    # Header row
    md_lines.append("| " + " | ".join(headers) + " |")
    # Separator row
    md_lines.append("| " + " | ".join(["---"] * num_cols) + " |")
    # Data rows
    for row in cleaned_rows[1:]:
        if len(row) < num_cols:
            row = row + [""] * (num_cols - len(row))
        md_lines.append("| " + " | ".join(row[:num_cols]) + " |")

    return "\n" + "\n".join(md_lines) + "\n"


def load_pdf(pdf_path: Path = DEFAULT_PDF_PATH) -> List[Document]:
    """
    Load PDF using pdfplumber:
    - Extracts clean body text.
    - Detects tables and converts them into structured Markdown tables.
    - Returns a list of LangChain Document objects (one per page).
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"Policy PDF not found at: {pdf_path}")

    documents = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_number = page_idx + 1
            tables = page.find_tables()
            extracted_tables = page.extract_tables()

            if tables and extracted_tables:
                # Filter out table bounding boxes to avoid duplicate raw text
                table_bboxes = [t.bbox for t in tables]

                def not_in_tables(obj):
                    h_mid = (obj["x0"] + obj["x1"]) / 2
                    v_mid = (obj["top"] + obj["bottom"]) / 2
                    for x0, top, x1, bottom in table_bboxes:
                        if (x0 <= h_mid <= x1) and (top <= v_mid <= bottom):
                            return False
                    return True

                non_table_page = page.filter(not_in_tables)
                body_text = non_table_page.extract_text() or ""

                # Format tables into Markdown
                md_tables = [table_to_markdown(t) for t in extracted_tables]
                full_content = body_text + "\n\n" + "\n\n".join(md_tables)
                has_table = True
            else:
                # Regular text page
                full_content = page.extract_text() or ""
                has_table = False

            doc = Document(
                page_content=full_content.strip(),
                metadata={
                    "source": str(pdf_path.name),
                    "page_number": page_number,
                    "has_table": has_table
                }
            )
            documents.append(doc)

    return documents


def split_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 150
) -> List[Document]:
    """
    Split Document objects into semantic chunks with overlap.
    Preserves page numbers, source, and chunk IDs in metadata.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = text_splitter.split_documents(documents)

    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = idx

    return chunks


def load_and_chunk_policy_manual(
    pdf_path: Path = DEFAULT_PDF_PATH,
    chunk_size: int = 1000,
    chunk_overlap: int = 150
) -> List[Document]:
    """
    Convenience function:
    Loads the PDF manual and returns the final chunks ready for vector embeddings.
    """
    pages = load_pdf(pdf_path)
    chunks = split_documents(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunks


if __name__ == "__main__":
    print("=" * 60)
    print("FINAL INGESTION PIPELINE: pdfplumber + Markdown Tables")
    print("=" * 60)

    print(f"\n[1] Loading 39-page manual from: {DEFAULT_PDF_PATH.name}...")
    pages = load_pdf()
    print(f"Total Pages Loaded: {len(pages)}")

    print(f"\n[2] Splitting into chunks (chunk_size=1000, chunk_overlap=150)...")
    chunks = split_documents(pages, chunk_size=1000, chunk_overlap=150)
    print(f"Total Chunks Created: {len(chunks)}")

    # Inspect the Page 11 table chunk
    print("\n--- Inspecting Table Chunk (Page 11) ---")
    table_chunk = next(c for c in chunks if c.metadata.get("page_number") == 11 and "| Transaction Type |" in c.page_content)
    print(f"Chunk ID: {table_chunk.metadata['chunk_id']}")
    print(f"Metadata: {table_chunk.metadata}")
    print("Content:")
    print("-" * 50)
    print(table_chunk.page_content)
    print("-" * 50)

    print("\nSUCCESS: Clean ingestion pipeline verified and ready for embeddings!")
