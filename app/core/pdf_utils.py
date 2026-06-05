import io
from typing import Optional
import requests
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError
import pytesseract
from PIL import Image
import logging
import tempfile
import os

logger = logging.getLogger(__name__)

class PDFExtractor:
    """PDFからテキストを抽出するクラス"""
    
    @staticmethod
    def extract_from_url(url: str) -> Optional[str]:
        """
        URLからPDFをダウンロードしてテキストを抽出
        
        Args:
            url (str): PDF URL
            
        Returns:
            Optional[str]: 抽出したテキスト。失敗時はNone
        """
        try:
            # PDFをダウンロード
            response = requests.get(url)
            response.raise_for_status()
            pdf_content = io.BytesIO(response.content)
            
            # テキスト抽出を試行
            try:
                text = extract_text(pdf_content)
                if text.strip():
                    return text
            except PDFSyntaxError:
                logger.warning(f"Failed to extract text from PDF: {url}")
                
            # テキスト抽出失敗の場合、OCRを試行
            return PDFExtractor._extract_with_ocr(pdf_content)
            
        except Exception as e:
            logger.error(f"Failed to process PDF: {url} - {str(e)}")
            return None
    
    @staticmethod
    def _extract_with_ocr(pdf_content: io.BytesIO) -> Optional[str]:
        """
        OCRを使用してテキストを抽出
        
        Args:
            pdf_content (io.BytesIO): PDFのバイナリデータ
            
        Returns:
            Optional[str]: 抽出したテキスト。失敗時はNone
        """
        try:
            from pdf2image import convert_from_bytes
            
            # PDFを画像に変換
            images = convert_from_bytes(pdf_content.getvalue())
            
            # 一時ディレクトリを作成
            with tempfile.TemporaryDirectory() as temp_dir:
                texts = []
                
                # 各ページに対してOCR実行
                for i, image in enumerate(images):
                    # 画像を一時保存
                    image_path = os.path.join(temp_dir, f"page_{i}.png")
                    image.save(image_path, "PNG")
                    
                    # OCR実行
                    text = pytesseract.image_to_string(Image.open(image_path), lang="jpn+eng")
                    texts.append(text)
                
                return "\n\n".join(texts)
                
        except Exception as e:
            logger.error(f"OCR failed: {str(e)}")
            return None 