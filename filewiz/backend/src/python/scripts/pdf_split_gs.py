import os
import sys
import math
import pymupdf as fitz

def split_by_count(input_pdf, output_dir, parts):
    doc = fitz.open(input_pdf)
    try:
        total_pages = len(doc)
        if total_pages == 0:
            return

        if parts > total_pages:
            parts = total_pages

        pages_per_part = math.ceil(total_pages / parts)
        current_page = 0
        index = 1

        while current_page < total_pages:
            end_page = min(current_page + pages_per_part, total_pages)
            output_file = os.path.join(output_dir, f"part_{index}.pdf")

            part_doc = fitz.open()
            part_doc.insert_pdf(doc, from_page=current_page, to_page=end_page - 1)
            part_doc.save(output_file)
            part_doc.close()

            current_page = end_page
            index += 1
    finally:
        doc.close()


def split_by_ranges(input_pdf, output_dir, ranges):
    doc = fitz.open(input_pdf)
    try:
        total_pages = len(doc)

        for i, r in enumerate(ranges):
            r = r.strip()
            if not r:
                continue
            if "-" in r:
                parts = r.split("-")
                start = max(1, int(parts[0]))
                end = min(total_pages, int(parts[1]))
            else:
                start = max(1, int(r))
                end = min(total_pages, start)

            if start <= end and start <= total_pages:
                output_file = os.path.join(output_dir, f"part_{i + 1}.pdf")
                part_doc = fitz.open()
                part_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
                part_doc.save(output_file)
                part_doc.close()
    finally:
        doc.close()


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python pdf_split_gs.py input.pdf output_dir <count|range> <param>", file=sys.stderr)
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_dir = sys.argv[2]
    mode = sys.argv[3]

    os.makedirs(output_dir, exist_ok=True)

    if mode == "count":
        split_by_count(input_pdf, output_dir, int(sys.argv[4]))
    elif mode == "range":
        split_by_ranges(input_pdf, output_dir, sys.argv[4].split(","))
    else:
        print(f"Invalid split mode: {mode}", file=sys.stderr)
        sys.exit(1)
