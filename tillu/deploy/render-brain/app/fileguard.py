from io import BytesIO
from pypdf import PdfReader

MAX_PAGES=500
MAX_EXTRACTED_CHARS=2_000_000

def inspect_pdf(data:bytes):
    try:reader=PdfReader(BytesIO(data),strict=True)
    except Exception as exc:raise ValueError('Malformed PDF') from exc
    if reader.is_encrypted:raise ValueError('Encrypted PDFs are not accepted')
    pages=len(reader.pages)
    if pages<1 or pages>MAX_PAGES:raise ValueError(f'PDF page count must be between 1 and {MAX_PAGES}')
    # Touch page dictionaries to reject broken object graphs before persistence.
    for page in reader.pages[:min(pages,20)]:
        _=page.mediabox
    return {'pages':pages,'status':'quarantined','scan':'structural-only'}
