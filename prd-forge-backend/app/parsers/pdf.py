"""PDF 解析器（pypdf 累加每页文本）。"""

from __future__ import annotations

import io

from pypdf import PdfReader  # type: ignore[import-untyped]
from pypdf.errors import PdfReadError  # type: ignore[import-untyped]

from app.errors import AppError, FILE_PARSE_FAILED
from app.parsers._truncate import truncate_with_marker


class PdfParser:
    """`.pdf` 解析：按页 `extract_text()` 累加。"""

    def parse(self, content: bytes, filename: str) -> str:
        try:
            reader = PdfReader(io.BytesIO(content))
        except PdfReadError as exc:
            raise AppError(
                FILE_PARSE_FAILED,
                f"PDF 解析失败：{filename}：{exc}",
                retriable=False,
            ) from exc
        except Exception as exc:  # 其他 IO / 解析错误
            raise AppError(
                FILE_PARSE_FAILED,
                f"PDF 解析失败：{filename}：{exc}",
                retriable=False,
            ) from exc

        page_texts: list[str] = []
        for idx, page in enumerate(reader.pages):
            try:
                txt = page.extract_text() or ""
            except Exception as exc:  # 单页失败不阻断整文件
                txt = f"[第 {idx + 1} 页解析失败：{exc}]"
            page_texts.append(txt)

        text = "\n".join(page_texts).strip()
        return truncate_with_marker(text, filename)
