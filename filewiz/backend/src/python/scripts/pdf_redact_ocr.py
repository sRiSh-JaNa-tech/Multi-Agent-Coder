import fitz
import sys
import json
import base64

def snap_redact(input_pdf, output_pdf, redactions):
    doc = fitz.Document(input_pdf)

    for page_index, page in enumerate(doc):
        # Get all words on the page: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        words = page.get_text("words")

        # Frontend sends us a list of "redaction boxes".
        # We want to find which words properly intersect with these boxes.
        
        # Filter redactions for this page
        page_redactions = [r for r in redactions if r["page"] - 1 == page_index]

        for r in page_redactions:
            # Create a rect for the user's selection
            user_rect = fitz.Rect(r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"])
            
            # Find words that intersect with this user_rect
            for w in words:
                word_rect = fitz.Rect(w[0], w[1], w[2], w[3])
                
                # Check intersection
                if user_rect.intersects(word_rect):
                    intersect = user_rect & word_rect
                    word_area = word_rect.get_area()
                    
                    # Require at least 40% overlap to snap (avoids accidental neighbor touches)
                    if word_area > 0 and (intersect.get_area() / word_area) > 0.4: 
                        # Redact the WORD's rect, not the user's imprecise rect
                        page.add_redact_annot(word_rect, fill=(0, 0, 0))

        page.apply_redactions()

    doc.save(output_pdf)
    doc.close()

if __name__ == "__main__":
    try:
        input_pdf = sys.argv[1]
        output_pdf = sys.argv[2]
        # Decode Base64 JSON
        json_str = base64.b64decode(sys.argv[3]).decode('utf-8')
        redactions = json.loads(json_str)

        snap_redact(input_pdf, output_pdf, redactions)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
