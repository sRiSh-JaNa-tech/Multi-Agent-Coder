import fitz  # PyMuPDF
import base64
import sys
import json

def redact_by_coords(input_pdf, output_pdf, redactions):
    doc = fitz.Document(input_pdf)

    for item in redactions:
        page_index = item["page"] - 1
        page = doc[page_index]

        # Coordinates from frontend might need scaling if not handled there.
        # But redactPrev.ejs sends scaled coordinates.
        
        rect = fitz.Rect(
            item["x"],
            item["y"],
            item["x"] + item["width"],
            item["y"] + item["height"]
        )

        page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

    # 🔐 remove metadata
    doc.set_metadata({})
    doc.save(output_pdf, deflate=True)
    doc.close()

if __name__ == "__main__":
    try:
        input_pdf = sys.argv[1]
        output_pdf = sys.argv[2]
        # Decode Base64 JSON to avoid shell quoting issues
        json_str = base64.b64decode(sys.argv[3]).decode('utf-8')
        redactions = json.loads(json_str)

        redact_by_coords(input_pdf, output_pdf, redactions)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
