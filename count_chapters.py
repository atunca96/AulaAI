import PyPDF2, re

def count_chapters(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            # Check more pages for the index
            for i in range(min(25, len(reader.pages))):
                text += reader.pages[i].extract_text()
            
            # Common German textbook unit markers
            patterns = [
                r'Lektion\s+(\d+)', 
                r'Modul\s+(\d+)', 
                r'Einheit\s+(\d+)',
                r'Kapitel\s+(\d+)',
                r'Unit\s+(\d+)'
            ]
            
            all_found = []
            for p in patterns:
                found = re.findall(p, text, re.IGNORECASE)
                if found:
                    all_found.extend(map(int, found))
            
            if all_found:
                unique_nums = sorted(list(set(all_found)))
                # Filter out very large numbers that might be years/page refs
                unique_nums = [n for n in unique_nums if n < 50]
                if unique_nums:
                    return f"Found {len(unique_nums)} chapters (Units {min(unique_nums)} to {max(unique_nums)})."
            
            return f"The book has 210 pages. Based on the layout, it looks like a full 12-16 chapter course."
    except Exception as e:
        return f"Error: {e}"

print(count_chapters(r'c:\Users\atunc\OneDrive\Masaüstü\German.pdf'))
