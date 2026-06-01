import io
import pdfplumber


def extract_text(file_bytes: bytes) -> str:
    try:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        if "encrypted" in str(e).lower() or "password" in str(e).lower():
            raise RuntimeError("PDF is encrypted and cannot be processed.")
        raise RuntimeError(f"Failed to extract text from PDF: {e}")
