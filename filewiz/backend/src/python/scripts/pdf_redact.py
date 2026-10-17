import fitz  # PyMuPDF
import sys
import json

def redact_by_coords(input_pdf, output_pdf, redactions):
    doc = fitz.open(input_pdf)

    for item in redactions:
        page_index = item["page"] - 1
        page = doc[page_index]

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
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    redactions = json.loads(sys.argv[3])

    redact_by_coords(input_pdf, output_pdf, redactions)
