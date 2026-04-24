import PyPDF2

def debug_pages(pdf_path, start_page, end_page):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for i in range(start_page - 1, min(end_page, len(reader.pages))):
                text += f"\n--- PAGE {i+1} ---\n"
                text += reader.pages[i].extract_text()
            return text
    except Exception as e:
        return str(e)

# Check pages 10-15 to see why it skipped Section 1.04
print(debug_pages(r'c:\Users\atunc\OneDrive\Masaüstü\German.pdf', 10, 15))
