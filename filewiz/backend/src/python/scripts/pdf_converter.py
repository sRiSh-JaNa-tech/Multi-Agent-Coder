import pymupdf as fitz
import os

import zipfile
from concurrent.futures import ThreadPoolExecutor

def convert_pdf_to_images(
    input_path: str,
    output_path: str,
    format_type: str = "png",
    first_page: int | None = None,
    last_page: int | None = None,
    dpi: int = 200
) -> dict:
    """
    Blazing-fast native PyMuPDF multi-threaded PDF to image converter.
    Zero Ghostscript dependency, zero intermediate disk I/O, renders directly into memory / ZIP streams.
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": "Input PDF does not exist"}

    fmt = "jpeg" if format_type.lower() in ("jpg", "jpeg") else "png"

    try:
        doc = fitz.open(input_path)
    except Exception as e:
        return {"success": False, "error": f"Failed to open PDF: {str(e)}"}

    try:
        total_pages = len(doc)
        if total_pages == 0:
            return {"success": False, "error": "PDF has 0 pages"}

        start = max(0, (first_page - 1) if first_page is not None else 0)
        end = min(total_pages - 1, (last_page - 1) if last_page is not None else total_pages - 1)

        if start > end:
            return {"success": False, "error": "Invalid page range (start > end)"}

        pages_to_render = list(range(start, end + 1))

        def render_page(idx):
            page = doc.load_page(idx)
            # alpha=False for JPEG, True for PNG
            pix = page.get_pixmap(dpi=dpi, alpha=(fmt == "png"))
            return idx, pix.tobytes(fmt)

        max_workers = min(8, len(pages_to_render), os.cpu_count() or 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            rendered = list(executor.map(render_page, pages_to_render))

        rendered.sort(key=lambda x: x[0])

        if output_path.endswith(".zip"):
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for idx, img_bytes in rendered:
                    zf.writestr(f"page_{idx + 1}.{fmt}", img_bytes)
            return {"success": True, "message": f"Successfully converted {len(rendered)} page(s) to {fmt.upper()} ZIP"}
        else:
            if len(rendered) > 0:
                with open(output_path, "wb") as f:
                    f.write(rendered[0][1])
            return {"success": True, "message": f"Successfully converted page to {fmt.upper()}"}
    except Exception as e:
        return {"success": False, "error": f"Image conversion failed: {str(e)}"}
    finally:
        doc.close()

def is_scanned_pdf(pdf_path: str, text_threshold: int = 50) -> bool:
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            text = page.get_text().strip()
            images = page.get_images(full=True)
            if len(text) < text_threshold and images:
                return True
        return False
    finally:
        doc.close()


def convert_pdf_to_docx(
    input_pdf: str,
    output_docx: str,
    start_page: int | None = None,
    end_page: int | None = None
):
    # ---------- Basic validation ----------
    if not os.path.exists(input_pdf):
        return {
            "success": False,
            "message": "Input PDF does not exist",
            "warning": None
        }

    if not input_pdf.lower().endswith(".pdf"):
        return {
            "success": False,
            "message": "Input file is not a PDF",
            "warning": None
        }


    # ---------- Page range validation ----------
    if start_page is not None and start_page < 0:
        return {
            "success": False,
            "message": "start_page must be >= 0",
            "warning": None
        }

    if end_page is not None and end_page < 0:
        return {
            "success": False,
            "message": "end_page must be >= 0",
            "warning": None
        }

    if start_page is not None and end_page is not None:
        if start_page > end_page:
            return {
                "success": False,
                "message": "start_page cannot be greater than end_page",
                "warning": None
            }

    # ---------- Conversion ----------
    try:
        from pdf2docx import Converter
        cv = Converter(input_pdf)
    except ImportError:
        return {
            "success": False,
            "message": "pdf2docx package is not installed on this system.",
            "warning": None
        }

    try:
        convert_kwargs = {}
        # pdf2docx crashes if start=None is explicitly passed, it defaults to 0
        convert_kwargs["start"] = start_page if start_page is not None else 0
        if end_page is not None:
            convert_kwargs["end"] = end_page

        cv.convert(output_docx, **convert_kwargs)
    except Exception as e:
        return {
            "success": False,
            "message": f"Conversion failed: {str(e)}",
            "warning": None
        }
    finally:
        cv.close()

    return {
        "success": True,
        "message": "PDF successfully converted to DOCX",
        "warning": warning_msg
    }

def convert_pdf_to_html(
    input_pdf: str,
    output_html: str,
    start_page: int | None = None,
    end_page: int | None = None
):
    """
    Fool-proof PDF → HTML conversion.

    Returns:
    {
        success: bool,
        message: str,
        warning: str | None
    }
    """

    # ---------- Validation ----------
    if not os.path.exists(input_pdf):
        return {
            "success": False,
            "message": "Input PDF does not exist",
            "warning": None
        }

    if not input_pdf.lower().endswith(".pdf"):
        return {
            "success": False,
            "message": "Input file is not a PDF",
            "warning": None
        }

    # ---------- Open PDF ----------
    try:
        doc = fitz.open(input_pdf)
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to open PDF: {str(e)}",
            "warning": None
        }

    total_pages = doc.page_count

    # ---------- Page range handling ----------
    start = start_page if start_page is not None else 0
    end = end_page if end_page is not None else total_pages - 1

    if start < 0 or end >= total_pages or start > end:
        return {
            "success": False,
            "message": "Invalid page range",
            "warning": None
        }

    # ---------- HTML generation ----------
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'>",
        "<style>",
        "body { font-family: Arial, sans-serif; line-height: 1.5; }",
        ".page { margin-bottom: 40px; }",
        "</style>",
        "</head>",
        "<body>"
    ]

    try:
        for page_number in range(start, end + 1):
            page = doc.load_page(page_number)
            page_html = page.get_text("html")

            html_parts.append(f"<div class='page'>")
            html_parts.append(f"<h3>Page {page_number + 1}</h3>")
            html_parts.append(page_html)
            html_parts.append("</div>")

        html_parts.append("</body></html>")

        with open(output_html, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

    except Exception as e:
        return {
            "success": False,
            "message": f"HTML conversion failed: {str(e)}",
            "warning": None
        }
    finally:
        doc.close()

    return {
        "success": True,
        "message": "PDF successfully converted to HTML",
        "warning": (
            "PDF to HTML conversion is best-effort. "
            "Exact layout, columns, and fonts may not be preserved."
        )
    }