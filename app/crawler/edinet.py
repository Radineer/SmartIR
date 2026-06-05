import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .base import BaseCrawler
import logging

logger = logging.getLogger(__name__)


class EDINETCrawler(BaseCrawler):
    """EDINETクローラー（有価証券報告書等を取得）- EDINET API v2対応"""

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv(
            "EDINET_API_URL",
            "https://api.edinet-fsa.go.jp/api/v2/"
        )
        self.api_key = os.getenv("EDINET_API_KEY", "")

    def crawl(self, days: int = 1, doc_type_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        指定日数分の開示書類を取得

        Args:
            days (int): 何日前までの情報を取得するか
            doc_type_codes (List[str]): 取得する書類タイプコード
                - 120: 有価証券報告書
                - 140: 四半期報告書
                - 160: 半期報告書
                - 030: 臨時報告書

        Returns:
            List[Dict[str, Any]]: IR資料情報のリスト
        """
        if doc_type_codes is None:
            doc_type_codes = ["120", "140", "160"]  # デフォルトは決算関連

        results = []

        # 日付範囲を設定
        for i in range(days):
            target_date = datetime.now() - timedelta(days=i)
            date_str = target_date.strftime("%Y-%m-%d")

            try:
                # 書類一覧を取得
                documents = self._get_documents_list(date_str)

                for doc in documents:
                    # フィルタリング
                    if doc.get("docTypeCode") not in doc_type_codes:
                        continue

                    # 上場企業のみ
                    if not doc.get("secCode"):
                        continue

                    try:
                        result = {
                            "company_code": doc["secCode"][:4],  # 証券コード（4桁）
                            "title": doc.get("docDescription", "不明"),
                            "publish_date": date_str,
                            "doc_type": self._determine_doc_type(doc.get("docTypeCode", "")),
                            "source_url": self._get_document_url(doc["docID"]),
                            "edinet_doc_id": doc["docID"],
                            "filer_name": doc.get("filerName", ""),
                        }
                        results.append(result)
                    except KeyError as e:
                        logger.error(f"Invalid EDINET document format: {str(e)}")
                        continue

            except Exception as e:
                logger.error(f"EDINET crawling failed for {date_str}: {str(e)}")
                continue

        return results

    def _get_documents_list(self, date: str) -> List[Dict[str, Any]]:
        """指定日の書類一覧を取得（EDINET API v2）"""
        url = f"{self.base_url}documents.json"
        params = {
            "date": date,
            "type": 2,  # 2: 有価証券報告書等
        }

        if self.api_key:
            params["Subscription-Key"] = self.api_key

        response = self._get(url, params=params)
        data = response.json()

        if data.get("metadata", {}).get("status") != "200":
            logger.warning(f"EDINET API returned non-200 status for {date}")
            return []

        return data.get("results", [])

    def _get_document_url(self, doc_id: str) -> str:
        """書類のダウンロードURLを生成（v2）"""
        key_param = f"&Subscription-Key={self.api_key}" if self.api_key else ""
        return f"{self.base_url}documents/{doc_id}?type=1{key_param}"

    def _determine_doc_type(self, doc_type_code: str) -> str:
        """書類タイプコードから資料種別を判定"""
        type_mapping = {
            "120": "annual_report",      # 有価証券報告書
            "140": "financial_report",   # 四半期報告書
            "160": "financial_report",   # 半期報告書
            "030": "press_release",      # 臨時報告書
        }
        return type_mapping.get(doc_type_code, "other")

    def download_document(self, doc_id: str) -> Optional[bytes]:
        """書類をダウンロード"""
        try:
            url = self._get_document_url(doc_id)
            response = self._get(url)
            return response.content
        except Exception as e:
            logger.error(f"Failed to download EDINET document {doc_id}: {str(e)}")
            return None
