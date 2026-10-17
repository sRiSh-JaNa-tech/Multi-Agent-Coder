import sys
import pymupdf as fitz

if len(sys.argv) < 3:
    print("Usage: python repair_pymupdf.py <input> <output>", file=sys.stderr)
    sys.exit(1)

input_path = sys.argv[1]
output_path = sys.argv[2]

try:
    # PyMuPDF/MuPDF reconstructs broken xref tables, repairs damaged trailers and cleans orphaned objects
    doc = fitz.open(input_path)
    doc.save(output_path, garbage=4, clean=True, deflate=True)
    doc.close()
    sys.exit(0)
except Exception as e:
    print(f"Repair failed: {e}", file=sys.stderr)
    sys.exit(1)
