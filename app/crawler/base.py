from abc import ABC, abstractmethod
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    """クローラーの基底クラス"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "AI-IR-Insight/1.0 (https://example.com; info@example.com)"
        }
    
    @abstractmethod
    def crawl(self) -> List[Dict[str, Any]]:
        """
        クローリングを実行し、IR資料情報のリストを返す
        Returns:
            List[Dict[str, Any]]: IR資料情報のリスト
            [
                {
                    "company_code": str,
                    "title": str,
                    "publish_date": str,  # YYYY-MM-DD
                    "doc_type": str,
                    "source_url": str
                },
                ...
            ]
        """
        pass
    
    def _get(self, url: str, params: dict = None) -> requests.Response:
        """GETリクエストを送信"""
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url} - {str(e)}")
            raise
    
    def _parse_html(self, html: str) -> BeautifulSoup:
        """HTMLをパース"""
        return BeautifulSoup(html, "html.parser")
    
    def __del__(self):
        """セッションをクローズ"""
        self.session.close() 