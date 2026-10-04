"""File-to-text conversion service using OpenAI's API.

Provides utilities for converting various file formats (PDF, images, Excel,
CSV, JSON, and text) to plain text using OpenAI's language models. Handles
file validation, format conversion for unsupported types, and binary file
uploads to OpenAI's API.

Note:
    This module requires the FILES_TO_TEXT_API_KEY environment variable
    or an explicit API key passed to the File2Text constructor. Async methods
    must be called within an async context.

Example:
    >>> service = File2Text(model_name="gpt-4", base_url=None)
    >>> text = await service.convert_one("document.pdf", file_bytes)
"""

import asyncio
import datetime
import json
import os
from io import BytesIO
from typing import Literal, Optional, Tuple
from uuid import uuid4

import aiofiles
import img2pdf
import pandas as pd
from openai import AsyncOpenAI
from openai.types.responses.response import Response
from PIL import Image

from ..._logger import log as _log
from ...exceptions import ConfigurationError
from ...messages.exceptions import undefined_param
from ...messages.warnings import missing_env_var
from ..exceptions import ChainServiceError, InvalidFileExtension

OPENAI_ACCEPTED_EXTENSIONS = [
    ".art",
    ".bat",
    ".brf",
    ".c",
    ".cls",
    ".css",
    ".diff",
    ".eml",
    ".es",
    ".h",
    ".hs",
    ".htm",
    ".html",
    ".ics",
    ".ifb",
    ".java",
    ".js",
    ".json",
    ".ksh",
    ".ltx",
    ".mail",
    ".markdown",
    ".md",
    ".mht",
    ".mhtml",
    ".mjs",
    ".nws",
    ".patch",
    ".pdf",
    ".pl",
    ".pm",
    ".pot",
    ".py",
    ".rst",
    ".scala",
    ".sh",
    ".shtml",
    ".srt",
    ".sty",
    ".tex",
    ".text",
    ".txt",
    ".vcf",
    ".vtt",
    ".xml",
    ".yaml",
    ".yml",
    ".docx",
    ".doc",
    ".dot",
    ".rtf",
]  # File extensions directly accepted by OpenAI's API for text extraction

OPENAI_CONVERT_EXTENSIONS = {
    "excel": [".xlsx", ".xlsm", ".xltx", ".xltm", ".xlsb", ".xls", ".xlt", ".xlm"],
    "csv": [".csv"],
    "image": [
        ".jpg",
        ".jpeg",
        ".jpe",
        ".png",
        ".tiff",
        ".tif",
        ".bmp",
        ".jp2",
        ".j2k",
        ".jpf",
        ".jpx",
        ".jpm",
        ".webp",
        ".pbm",
        ".pgm",
        ".ppm",
        ".pnm",
        ".tga",
    ],
}  # File extensions that require format conversion before OpenAI processing

OPENAI_PLAIN_TEXT_EXTENSIONS = [".json", ".txt"]  # Extensions processed as plain text without binary upload


class File2Text:
    """Service for converting various file types to text using OpenAI's API.

    Provides a unified interface for file upload, validation, format conversion,
    and text extraction from files using AI-powered OCR and language models.
    Handles multi-format support (PDF, images, Excel, CSV, JSON, text) with
    automatic format conversion for unsupported types.

    Attributes:
        model_name: The name of the OpenAI model to use for text extraction.
        llm: An AsyncOpenAI client configured with the provided API key and base URL.
    """

    def __init__(self, model_name: str, base_url: Optional[str], *, api_key: Optional[str] = None):
        """Initialize the File2Text service with OpenAI API credentials.

        Args:
            model_name: The name of the OpenAI model to use for extraction.
            base_url: The base URL for the OpenAI API endpoint, or None to use default.
            api_key: The OpenAI API key. If not provided, reads from
                FILES_TO_TEXT_API_KEY environment variable.

        Raises:
            ConfigurationError: If no API key is provided and FILES_TO_TEXT_API_KEY
                environment variable is not set.
        """
        self.model_name = model_name

        if not api_key:
            api_key = os.environ.get("FILES_TO_TEXT_API_KEY")
            if not api_key:
                raise ConfigurationError(undefined_param.format(name="Files to Text OpenAI API key", param="FILES_TO_TEXT_API_KEY"))
        else:
            _log.warning(missing_env_var.format(name="OpenAI API key"))

        self.llm = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def convert_one(self, full_name: str, content: bytes, *, language: Optional[str] = None) -> str:
        """Extract text from a single file using OpenAI's API.

        Processes a file by converting it to text format using OpenAI's language
        model. Validates the file extension, converts unsupported formats
        automatically, and manages binary file uploads to OpenAI's API.

        Args:
            full_name: The complete filename including extension.
            content: The file contents as raw bytes.
            language: The target language for the extracted text. If not
                provided or blank, extraction is returned in the same language
                as the source document.

        Returns:
            The extracted text from the file as a string.

        Raises:
            InvalidFileExtension: If the file extension is not supported and
                cannot be converted.
            ChainServiceError: If the file conversion process fails or OpenAI
                API returns an error.

        Note:
            Plain text files (.json, .txt) are processed as text input.
            Binary files are uploaded to OpenAI and processed using file IDs.
            Unsupported formats are automatically converted before processing.
        """

        f_extension = os.path.splitext(full_name)[1].lower()

        if self.is_unsupported_file(f_extension):
            raise InvalidFileExtension("Unsupported file format attached")

        if f_extension not in OPENAI_ACCEPTED_EXTENSIONS:
            try:
                content, f_extension = await ExtensionConverter(content, f_extension).convert()
            except ChainServiceError:
                raise ChainServiceError("Internal error caused by file conversion process")

        if f_extension in OPENAI_PLAIN_TEXT_EXTENSIONS:
            json_string = content.decode("utf-8")
            full_prompt = [{"type": "input_text", "text": json_string}, {"type": "input_text", "text": self.prompt(language)}]
            response = await self.llm.responses.create(model=self.model_name, input=[{"role": "user", "content": full_prompt}])
        else:
            file_obj = self.openai_file_object(content, name=full_name, extension=f_extension)
            uploaded = await self.llm.files.create(file=file_obj, purpose="assistants")
            full_prompt = [{"type": "input_file", "file_id": uploaded.id}, {"type": "input_text", "text": self.prompt(language)}]

            try:
                response = await self.llm.responses.create(model=self.model_name, input=[{"role": "user", "content": full_prompt}])
            except Exception as e:
                if "Expected context stuffing file type to be a supported format" in str(e):
                    raise InvalidFileExtension("Unsupported file(s) format attached")
                raise ChainServiceError(e)

        response = self.fix_openai_files_response_format(response)
        return response

    async def convert_many(self, files: list) -> list[str]:
        """Extract text from multiple files using OpenAI's API.

        Not yet implemented. Use convert_one() for individual files.

        Args:
            files: A list of FileInfo objects containing file data and metadata.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """

        # files_data = []

        # if self.any_unsupported_file(files):
        #     raise InvalidFileExtension("Unsupported file(s) format attached")

        # for file in files:
        #     file_extension = os.path.splitext(file.name)[1].lower()
        #     file_bytes = base64.b64decode(file.base64)

        #     if file_extension not in OPENAI_ACCEPTED_EXTENSIONS:
        #         try:
        #             file_bytes, file_extension = await ExtensionConverter(file_bytes, file_extension).convert()
        #         except ChainServiceError:
        #             raise ChainServiceError("Internal error caused by file conversion process")

        #     if file_extension in OPENAI_PLAIN_TEXT_EXTENSIONS:
        #         json_string = file_bytes.decode("utf-8")
        #         full_prompt = [{"type": "input_text", "text": json_string}, {"type": "input_text", "text": self.prompt}]
        #         response = await self.llm.responses.create(model=self.model_name, input=[{"role": "user", "content": full_prompt}])
        #     else:
        #         file_obj = self.openai_file_object(file_bytes, name=file.name, extension=file_extension)
        #         uploaded = await self.llm.files.create(file=file_obj, purpose="assistants")
        #         full_prompt = [{"type": "input_file", "file_id": uploaded.id}, {"type": "input_text", "text": self.prompt}]

        #         try:
        #             response = await self.llm.responses.create(model=self.model_name, input=[{"role": "user", "content": full_prompt}])
        #         except Exception as e:
        #             if "Expected context stuffing file type to be a supported format" in str(e):
        #                 raise InvalidFileExtension("Unsupported file(s) format attached")
        #             raise ChainServiceError(e)

        #     response = self.fix_openai_files_response_format(response)
        #     files_data.append(response)

        # return files_data

        raise NotImplementedError

    @staticmethod
    def is_unsupported_file(extension: str) -> bool:
        """Check if a file extension is not supported for text extraction.

        Validates whether the file extension can be processed by checking against
        both directly accepted OpenAI formats and convertible formats.

        Args:
            extension: The file extension (e.g., '.pdf', '.exe').

        Returns:
            True if the extension is not supported, False if it is supported.

        Example:
            >>> File2Text.is_unsupported_file('.pdf')
            False
            >>> File2Text.is_unsupported_file('.exe')
            True
        """

        supported_extensions = OPENAI_ACCEPTED_EXTENSIONS + [ext for exts in OPENAI_CONVERT_EXTENSIONS.values() for ext in exts]

        if extension not in supported_extensions:
            return True
        return False

    def openai_file_object(self, file_data: bytes, *, name: str, extension: str) -> BytesIO:
        """Create a BytesIO object formatted for OpenAI API file upload.

        Wraps file data in a BytesIO object with a properly formatted filename,
        replacing the original extension with the specified one.

        Args:
            file_data: The raw file contents as bytes.
            name: The original filename including extension.
            extension: The file extension to apply (e.g., '.txt', '.pdf').

        Returns:
            A BytesIO object with the name attribute set to the filename
            with original extension replaced by the specified extension.

        Example:
            >>> file_obj = file_to_text.openai_file_object(b'Hello', name='doc.old', extension='.txt')
            >>> file_obj.name
            'doc.txt'
        """

        file_obj = BytesIO(file_data)
        name = os.path.splitext(name)[0] + extension
        file_obj.name = name
        return file_obj

    def fix_openai_files_response_format(self, ai_response: Response) -> str:
        """Extract text content from OpenAI Responses API output.

        Processes the response structure from OpenAI's Responses API to extract
        all text content, unifying the format for consistent downstream handling.

        Args:
            ai_response: The response object from OpenAI's responses.create() call.

        Returns:
            Concatenated text content from all response items as a single string.
        """

        fixed_response = ""

        for item in ai_response.output:
            if hasattr(item, "content") and item.content:  # type: ignore
                for content in item.content:  # type: ignore
                    if hasattr(content, "text") and content.text:  # type: ignore
                        fixed_response += content.text  # type: ignore

        return fixed_response

    def prompt(self, language: Optional[str]) -> str:
        """Build the system prompt for document text extraction.

        Returns a detailed prompt instructing the model to extract all content
        from general-purpose documents with high accuracy and precision.

        Args:
            language: The target language requested for the output text. If
                None or blank, the prompt instructs the model to use the same
                language as the attached document.

        Returns:
            The OCR system prompt as a string.
        """

        if language is None or not language.strip():
            language_rule = "the same language as the attached document"
        else:
            language_rule = language.title() + " language"

        return f"""
        You are a very smart and accurate OCR tool for documents. You are specialized in reading general purpose documents and fully
        converting the data in them to textual data without any loss of data. You have only a single purpose: read received documents,
        analyze them, and convert them to text form. Follow these guidelines strictly:

        ## NATURE OF DOCUMENTS
        The provided documents are general-purpose documents. They can be of any nature; text-rich, number-rich, table-rich, or of
        any other nature. They are presented in any file extention, but mainly _.pdf_, _.doc_, _.docx_, _.xlsx_, _.csv_, and _.json_.
        These documents consist of very important and precise data, which is why they are meant to be handled with cautious and utmost
        concentration. In these documents, even the smallest data is meaningful.

        ## OPERATIONAL STEPS
        1- Properly understand the nature of documents that you will be requested to convert into textual information by reading
        the _Nature of Documents_ section above.
        
        2- Go through and analyze the documents you received and fully understand them.

        3- Fully convert all the data into human-readable text form in {language_rule} **without losing any piece of data, no matter
        how small it is**.

        ## BEHAVIORAL GUIDELINES
        - Do not include welcoming and/or extra informative messages in your response (e.g "Sure, here's the result:",
        "The translated information:", "After analyzing the given document, here's the textual information:").

        - Make sure no data is lost in the conversion process

        - Preserve the format of the received documents when you convert the data to textual form.

        - Make sure that the resultant response is human-readable.

        ## RESPONSE FORMAT GUIDELINES
        - The response is **STRICTLY** supposed to be returned as a **string**. This is very important.
        """


class ExtensionConverter:
    """Converts unsupported file formats to OpenAI-compatible formats.

    Handles conversion of Excel, CSV, and image files to JSON or PDF format
    for processing by OpenAI's API. All conversions are performed asynchronously
    to avoid blocking the event loop.

    Attributes:
        file_bytes: The raw file contents as bytes.
        extension: The current file extension (e.g., '.xlsx', '.jpg').
    """

    def __init__(self, file_bytes: bytes, extension: str):
        """Initialize the converter with file data and extension.

        Args:
            file_bytes: The raw file contents as bytes.
            extension: The file extension (e.g., '.xlsx', '.csv', '.jpg').
        """
        self.file_bytes = file_bytes
        self.extension = extension

    async def convert(self) -> Tuple[bytes, str]:
        """Convert the file to an OpenAI-supported format.

        Dispatches to the appropriate converter based on file extension.
        Excel and CSV files are converted to JSON; images are converted to PDF.

        Returns:
            A tuple of (converted_bytes, new_extension) where converted_bytes
            contains the converted file data and new_extension is the resulting
            format (e.g., '.json', '.pdf').

        Raises:
            InvalidFileExtension: If the file extension is not handled by
                any converter.
        """
        if self.extension in OPENAI_CONVERT_EXTENSIONS["excel"]:
            return await self.convert_excel_to_json()
        if self.extension in OPENAI_CONVERT_EXTENSIONS["csv"]:
            return await self.convert_csv_to_json()
        if self.extension in OPENAI_CONVERT_EXTENSIONS["image"]:
            return await self.convert_image_to_pdf()
        else:
            raise InvalidFileExtension(
                f"The provided extension {self.extension} is not a part of the extensions handled by this method, yet still passed to this method."
            )

    async def convert_excel_to_json(self) -> Tuple[bytes, Literal[".json"]]:
        """Convert Excel file to JSON format.

        Reads all sheets from the Excel file and converts each sheet to a
        dictionary of records. DateTime values are converted to ISO format.
        Blocking I/O is performed in a separate thread to avoid blocking
        the event loop.

        Returns:
            A tuple of (json_bytes, '.json') where json_bytes contains the
            JSON-encoded Excel data.

        Raises:
            ChainServiceError: If the Excel file cannot be read or processed.

        Note:
            Creates temporary files during processing which are cleaned up
            after conversion completes.
        """
        tmp_dir = "tmp"

        os.makedirs(tmp_dir, exist_ok=True)  # TODO: This is fast but blocking.
        file_path = f"{tmp_dir}/{str(uuid4())}.{self.extension}"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(self.file_bytes)

        # To avoid blocking the event loop, run the heavy operations in a separate thread.
        def read_excel_file():
            try:
                with pd.ExcelFile(file_path) as xls:
                    data = {}

                    for sheet in xls.sheet_names:
                        df = xls.parse(sheet)
                        df = df.where(pd.notnull(df), None)  # type: ignore

                        for col in df.columns:
                            df[col] = df[col].apply(lambda x: x.isoformat() if isinstance(x, datetime.datetime) else x)

                        data[sheet] = df.to_dict(orient="records")

                data_json = json.dumps(data, indent=2, ensure_ascii=False)
                data_bytes = data_json.encode("utf-8")
            finally:
                os.remove(file_path)
                os.rmdir(tmp_dir)

            return data_bytes

        data_bytes = await asyncio.to_thread(read_excel_file)
        return data_bytes, ".json"

    async def convert_csv_to_json(self) -> Tuple[bytes, Literal[".json"]]:
        """Convert CSV file to JSON format.

        Reads the CSV file and converts it to JSON records format. Blocking
        I/O is performed in a separate thread to avoid blocking the event loop.

        Returns:
            A tuple of (json_bytes, '.json') where json_bytes contains the
            JSON-encoded CSV data as records.
        """
        csv_buffer = BytesIO(self.file_bytes)

        def read_csv_file():
            df = pd.read_csv(csv_buffer)
            data_json = df.to_json(orient="records", indent=2)
            return data_json.encode("utf-8")

        data_bytes = await asyncio.to_thread(read_csv_file)
        return data_bytes, ".json"

    async def convert_image_to_pdf(self) -> Tuple[bytes, Literal[".pdf"]]:
        """Convert image file to PDF format.

        Removes transparency layer from the image and converts it to PDF.
        Heavy operations are performed in separate threads to avoid blocking
        the event loop.

        Returns:
            A tuple of (pdf_bytes, '.pdf') where pdf_bytes contains the
            PDF-encoded image data.
        """
        image_bytes = await asyncio.to_thread(self._remove_image_transparency_layer, self.file_bytes)
        data_bytes = await asyncio.to_thread(img2pdf.convert, image_bytes)
        return data_bytes, ".pdf"  # type: ignore

    @staticmethod
    def _remove_image_transparency_layer(file_bytes: bytes, *, ext_format: str = "JPEG") -> BytesIO:
        """Remove transparency from image and return as BytesIO object.

        Converts image to RGB format to remove alpha channel, preventing issues
        when converting images with transparency to PDF.

        Args:
            file_bytes: Raw image file bytes.
            ext_format: Image format for output (e.g., 'JPEG', 'PNG').
                Defaults to 'JPEG'.

        Returns:
            A BytesIO object containing the image without transparency.
        """
        file_io = BytesIO(file_bytes)
        file_io.seek(0)

        with Image.open(file_io) as img:
            rgb = img.convert("RGB")
            output = BytesIO()
            rgb.save(output, format=ext_format)
            output.seek(0)

        return output
