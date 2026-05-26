from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.models import ResumeFileKind, ResumeProfile
from app.services.ai_clients import OCRClient


class ResumeParser:
    def __init__(self, ocr_client: OCRClient | None = None) -> None:
        self.ocr_client = ocr_client or OCRClient()

    def parse(self, path: Path) -> ResumeProfile:
        kind = self.detect_kind(path)
        if kind == ResumeFileKind.pdf:
            raw_text, confidence, warnings = self._parse_pdf(path)
        elif kind == ResumeFileKind.docx:
            raw_text, confidence, warnings = self._parse_docx(path)
        elif kind == ResumeFileKind.image:
            result = self.ocr_client.extract_from_image(path)
            raw_text, confidence, warnings = result.text, result.confidence, []
            if result.confidence < 0.6:
                warnings.append("图片 OCR 置信度较低，需要用户或讲师确认关键字段。")
        else:
            raw_text, confidence, warnings = "", 0.0, ["不支持的简历格式。"]
        return self._build_profile(raw_text, kind, confidence, warnings)

    def detect_kind(self, path: Path) -> ResumeFileKind:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return ResumeFileKind.pdf
        if suffix == ".docx":
            return ResumeFileKind.docx
        if suffix in {".png", ".jpg", ".jpeg"}:
            return ResumeFileKind.image
        return ResumeFileKind.unsupported

    def _parse_pdf(self, path: Path) -> tuple[str, float, list[str]]:
        warnings: list[str] = []
        text = ""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:  # pragma: no cover - depends on external files
            warnings.append(f"PDF 文本抽取失败：{exc}")
        if len(text) < settings.min_pdf_text_chars:
            ocr = self.ocr_client.extract_from_pdf_pages(path)
            warnings.append("PDF 文本层过少，已切换到扫描版 OCR 解析路径。")
            if ocr.confidence < 0.6:
                warnings.append("PDF OCR 置信度较低，需要人工确认。")
            return ocr.text, ocr.confidence, warnings
        return text, 0.86, warnings

    def _parse_docx(self, path: Path) -> tuple[str, float, list[str]]:
        try:
            from docx import Document

            doc = Document(str(path))
            chunks: list[str] = []
            chunks.extend(p.text for p in doc.paragraphs if p.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    chunks.append(" | ".join(cell.text.strip() for cell in row.cells))
            return "\n".join(chunks).strip(), 0.9, []
        except Exception as exc:  # pragma: no cover - depends on external files
            return "", 0.0, [f"DOCX 解析失败：{exc}"]

    def _build_profile(
        self,
        raw_text: str,
        kind: ResumeFileKind,
        confidence: float,
        warnings: list[str],
    ) -> ResumeProfile:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        name = self._guess_name(lines)
        contact = self._find_contact(raw_text)
        skills = self._extract_skills(raw_text)
        return ResumeProfile(
            candidate_name=name,
            contact=contact,
            education=self._extract_section(lines, ["教育", "教育经历", "学历"]),
            projects=self._extract_section(lines, ["项目", "项目经历"]),
            internships=self._extract_section(lines, ["实习", "工作经历", "实践经历"]),
            skills=skills,
            certificates=self._extract_section(lines, ["证书", "获奖", "荣誉"]),
            target_position=self._guess_target(raw_text, skills),
            raw_text=raw_text,
            parse_confidence=confidence,
            source_kind=kind,
            warnings=warnings,
        )

    def _guess_name(self, lines: list[str]) -> str | None:
        for line in lines[:5]:
            clean = re.sub(r"\s+", "", line)
            if 2 <= len(clean) <= 8 and not re.search(r"简历|电话|邮箱|求职", clean):
                return clean
        return None

    def _find_contact(self, text: str) -> str | None:
        email = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
        phone = re.search(r"1[3-9]\d{9}", text)
        contacts = [m.group(0) for m in [phone, email] if m]
        return " / ".join(contacts) if contacts else None

    def _extract_skills(self, text: str) -> list[str]:
        known = [
            "Python",
            "Java",
            "C++",
            "SQL",
            "MySQL",
            "Redis",
            "Docker",
            "Linux",
            "React",
            "Vue",
            "FastAPI",
            "Spring",
            "PyTorch",
            "TensorFlow",
            "NLP",
            "Transformer",
            "OpenCV",
            "LangChain",
            "算法",
            "数据分析",
            "机器学习",
            "深度学习",
        ]
        return [skill for skill in known if skill.lower() in text.lower()]

    def _extract_section(self, lines: list[str], keywords: list[str]) -> list[str]:
        matched: list[str] = []
        for index, line in enumerate(lines):
            if any(keyword in line for keyword in keywords):
                matched.extend(lines[index : min(index + 4, len(lines))])
        return list(dict.fromkeys(matched))[:6]

    def _guess_target(self, text: str, skills: list[str]) -> str | None:
        match = re.search(r"求职意向[:：\s]*(.+)", text)
        if match:
            return match.group(1).strip()[:40]
        if any(skill in skills for skill in ["Python", "Java", "MySQL", "Redis", "FastAPI", "Spring"]):
            return "后端开发工程师"
        if any(skill in skills for skill in ["React", "Vue"]):
            return "前端开发工程师"
        return None
