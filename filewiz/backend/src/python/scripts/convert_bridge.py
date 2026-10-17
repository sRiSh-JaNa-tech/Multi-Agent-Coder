import sys
import json
import base64
import os
from pdf_converter import convert_pdf_to_images, convert_pdf_to_html

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided"}))
        sys.exit(1)

    try:
        payload_str = base64.b64decode(sys.argv[1]).decode('utf-8')
        payload = json.loads(payload_str)
        
        mode = payload.get("mode", "png").lower()
        input_path = payload.get("inputPath")
        output_path = payload.get("outputPath")
        
        # Parse pages
        start_page = payload.get("startPage")
        end_page = payload.get("endPage")

        start = int(start_page) if start_page is not None and str(start_page).strip() != "" else None
        end = int(end_page) if end_page is not None and str(end_page).strip() != "" else None
        
        if not input_path or not output_path:
             print(json.dumps({"error": "Missing input or output path."}))
             sys.exit(1)

        result = {}

        if mode in ["png", "jpeg", "jpg"]:
            result = convert_pdf_to_images(
                input_path=input_path,
                output_path=output_path,
                format_type=mode,
                first_page=start,
                last_page=end,
                dpi=200
            )

        elif mode == "html":
             result = convert_pdf_to_html(input_path, output_path, start, end)

        elif mode == "docx":
             from pdf_converter import convert_pdf_to_docx
             result = convert_pdf_to_docx(input_path, output_path, start, end)

        else:
             result = {"success": False, "message": f"Unknown mode: {mode}"}
        
        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
