import os
import sys
import base64
import json
import pymupdf as fitz

def encrypt_pdf(
    input_pdf: str,
    user_password: str,
    owner_password: str,
    encryption_level: str = "256", 
    output_pdf: str = "encrypted.pdf"
) -> bool:
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"Input file not found: {input_pdf}")

    level_str = str(encryption_level).lower()
    if level_str in ("high", "256", "aes256"):
        enc_method = fitz.PDF_ENCRYPT_AES_256
    elif level_str in ("medium", "128", "aes128"):
        enc_method = fitz.PDF_ENCRYPT_AES_128
    elif level_str in ("low", "40", "rc4_40"):
        enc_method = fitz.PDF_ENCRYPT_RC4_40
    else:
        enc_method = fitz.PDF_ENCRYPT_AES_256

    # Standard safe permissions (print allowed, modification restricted)
    permissions = (
        fitz.PDF_PERM_PRINT |
        fitz.PDF_PERM_COPY |
        fitz.PDF_PERM_ANNOTATE
    )

    try:
        doc = fitz.open(input_pdf)
        doc.save(
            output_pdf,
            encryption=enc_method,
            user_pw=user_password,
            owner_pw=owner_password,
            permissions=permissions
        )
        doc.close()
        return True
    except Exception as e:
        print(f"Encryption error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Usage: py pdf_encryption.py <base64_payload>", file=sys.stderr)
            sys.exit(1)
        
        payload_str = base64.b64decode(sys.argv[1]).decode('utf-8')
        payload = json.loads(payload_str)

        input_file = payload.get("inputPath")
        user_pw = payload.get("user_password")
        owner_pw = payload.get("owner_password")
        enc_level = payload.get("encryption_lvl", "256")
        output_file = payload.get("outputPath")

        if not all([input_file, user_pw, owner_pw, output_file]):
            print(json.dumps({"success": False, "error": "Missing required parameters in payload"}))
            sys.exit(1)

        success = encrypt_pdf(input_file, user_pw, owner_pw, enc_level, output_file)
        if success:
            print(json.dumps({"success": True, "message": "PDF encrypted successfully"}))
        else:
            print(json.dumps({"success": False, "error": "Failed to encrypt PDF"}))
            sys.exit(1)

    except Exception as err:
        print(json.dumps({"success": False, "error": str(err)}))
        sys.exit(1)