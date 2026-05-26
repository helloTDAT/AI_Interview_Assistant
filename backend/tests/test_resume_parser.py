from pathlib import Path

from app.models import ResumeFileKind
from app.services.resume_parser import ResumeParser


def test_image_resume_uses_ocr_fallback(tmp_path: Path):
    image = tmp_path / "resume.png"
    image.write_bytes(b"not really an image but enough for extension routing")

    profile = ResumeParser().parse(image)

    assert profile.source_kind == ResumeFileKind.image
    assert profile.parse_confidence < 0.6
    assert profile.warnings
    assert "OCR" in profile.raw_text


def test_docx_resume_extracts_text(tmp_path: Path):
    from docx import Document

    docx = tmp_path / "resume.docx"
    doc = Document()
    doc.add_paragraph("张三")
    doc.add_paragraph("求职意向：后端开发工程师")
    doc.add_paragraph("技能：Python MySQL Redis FastAPI")
    doc.save(str(docx))

    profile = ResumeParser().parse(docx)

    assert profile.source_kind == ResumeFileKind.docx
    assert profile.candidate_name == "张三"
    assert "Python" in profile.skills
    assert profile.target_position == "后端开发工程师"
