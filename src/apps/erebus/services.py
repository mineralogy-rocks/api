# -*- coding: UTF-8 -*-
import os
import re
import tempfile

import camelot
import pandas as pd
from markitdown import MarkItDown


class SpreadsheetConverter:
    """Handles conversion of spreadsheet files (CSV, XLS, XLSX) to markdown format."""

    SUPPORTED_EXTENSIONS = [".csv", ".xls", ".xlsx"]

    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: str) -> str:
        file_extension = os.path.splitext(file_path)[1].lower()
        df = pd.read_csv(file_path, on_bad_lines="skip") if file_extension == ".csv" else pd.read_excel(file_path)
        return df.fillna("").to_markdown(index=False)


class PDFConverter:
    """Handles conversion of PDF files to markdown format with table extraction."""

    SUPPORTED_EXTENSIONS = [".pdf"]

    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: str) -> str:
        """Convert PDF to markdown using Camelot for table extraction."""
        try:
            tables = camelot.read_pdf(file_path, pages="all", flavor="lattice")

            if not tables:
                tables = camelot.read_pdf(file_path, pages="all", flavor="stream")

            if not tables:
                raise Exception("No tables found")

            return self._format_tables(tables)

        except Exception:
            return MarkItDown().convert(file_path).text_content

    @staticmethod
    def _format_tables(tables) -> str:
        """Format extracted tables as markdown."""
        parts = []

        for i, table in enumerate(tables, start=1):
            df = table.df

            if len(df) > 1:
                df.columns = df.iloc[0]
                df = df[1:].reset_index(drop=True)

            df = df.fillna("").replace(r"\s+", " ", regex=True)
            df = df.loc[:, (df != "").any(axis=0)]
            df = df[(df != "").any(axis=1)]

            if not df.empty:
                parts.append(f"## Table {i} (Page {table.page})\n\n{df.to_markdown(index=False)}")

        return "\n\n".join(parts) if parts else "No tables extracted"


class DocumentConverter:
    """Handles conversion of document files to markdown format using MarkItDown."""

    def can_handle(self, file_extension: str) -> bool:
        return True

    def convert(self, file_path: str) -> str:
        """Convert document file to markdown format using MarkItDown."""
        md = MarkItDown()
        result = md.convert(file_path)
        markdown_content = result.text_content

        # markdown_content = re.sub(r'\bnan\b', '', markdown_content, flags=re.IGNORECASE)
        # markdown_content = re.sub(r'\b-?inf\b', '', markdown_content, flags=re.IGNORECASE)

        return markdown_content


class TextCleaningService:
    """Service for cleaning and normalizing markdown text content."""

    @staticmethod
    def clean_markdown(text: str) -> str:
        """
        Clean markdown text by normalizing whitespace.

        Removes multiple consecutive spaces and excessive blank lines.
        """
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n\n+", "\n\n", text)
        return text


class FileConversionService:
    """
    Service for converting uploaded files to markdown format.

    Coordinates file conversion by selecting the appropriate converter
    and managing temporary file lifecycle.
    """

    def __init__(self):
        self.converters = [
            SpreadsheetConverter(),
            PDFConverter(),
            DocumentConverter(),
        ]

    def convert_to_markdown(self, uploaded_file) -> str:
        """
        Convert an uploaded file to markdown format.

        Args:
            uploaded_file: Django UploadedFile object

        Returns:
            str: Markdown content

        Raises:
            Exception: If conversion fails
        """
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension, mode="wb") as tmp_file:
            uploaded_file.seek(0)
            file_content = uploaded_file.read()
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        uploaded_file.seek(0)

        try:
            converter = next((c for c in self.converters if c.can_handle(file_extension)), None)

            markdown_content = converter.convert(tmp_file_path)

            return markdown_content

        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
