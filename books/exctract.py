from pypdf import PdfReader
from concurrent.futures import ThreadPoolExecutor
import os

def extract_and_clean_pdf(path):
    """Extract and clean text from a PDF file."""
    try:
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        text = text.replace("-\n", "")      
        text = " ".join(text.split())      
        return text, os.path.basename(path)  
    except Exception as e:
        print(f"Error processing {path}: {e}")
        return "", os.path.basename(path)

def process_pdfs_from_directory(pdf_directory, txt_directory):
    """
    Process all PDFs in a directory and save extracted text to separate files.
    
    Args:
        pdf_directory: Path to directory containing PDF files
        txt_directory: Path to directory where .txt files will be saved
    """
    # Create output directory if it doesn't exist
    os.makedirs(txt_directory, exist_ok=True)
    
    # Get all PDF files from the directory
    pdf_files = []
    for file in os.listdir(pdf_directory):
        if file.lower().endswith('.pdf'):
            full_path = os.path.join(pdf_directory, file)
            pdf_files.append(full_path)
    
    if not pdf_files:
        print(f"No PDF files found in {pdf_directory}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Use ThreadPoolExecutor to process PDFs in parallel
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(executor.map(extract_and_clean_pdf, pdf_files))
    
    # Save each PDF's text to a separate .txt file
    saved_count = 0
    for text, filename in results:
        if text.strip():  # Only save non-empty texts
            # Replace .pdf extension with .txt
            txt_filename = os.path.splitext(filename)[0] + '.txt'
            txt_path = os.path.join(txt_directory, txt_filename)
            
            # Save to text file
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"Saved: {txt_filename}")
            saved_count += 1
    
    print(f"\nExtracted text from {saved_count} PDF file(s) saved to {txt_directory}")

process_pdfs_from_directory('pdfs', 'txts')