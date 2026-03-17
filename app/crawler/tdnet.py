import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from .base import BaseCrawler
import logging

logger = logging.getLogger(__name__)


class TDNetCrawler(BaseCrawler):
    """TDnetクローラー（適時開示情報をHTMLスクレイピングで取得）"""

    BASE_URL = "https://www.release.tdnet.info/inbs/I_list_{page_num:03d}_{date}.html"

    def __init__(self):
        super().__init__()

    def crawl(self, days: int = 1) -> List[Dict[str, Any]]:
        """
        指定日数分のIR資料情報をTDnetからスクレイピング

        Args:
            days (int): 何日前までの情報を取得するか（デフォルト: 1日）

        Returns:
            List[Dict[str, Any]]: IR資料情報のリスト
        """
        results = []

        for i in range(days):
            target_date = datetime.now() - timedelta(days=i)
            date_str = target_date.strftime("%Y%m%d")

            try:
                page_results = self._crawl_date(date_str)
                results.extend(page_results)
                logger.info(f"TDnet {target_date.strftime('%Y-%m-%d')}: {len(page_results)} documents found")
            except Exception as e:
                logger.error(f"TDNet crawling failed for {date_str}: {str(e)}")
                continue

        return results

    def _crawl_date(self, date_str: str) -> List[Dict[str, Any]]:
        """指定日の全ページをクロール"""
        results = []
        page_num = 1

        while True:
            url = self.BASE_URL.format(page_num=page_num, date=date_str)
            try:
                response = self._get(url)
            except Exception:
                if page_num == 1:
                    logger.warning(f"TDnet: No data for {date_str}")
                break

            response.encoding = response.apparent_encoding or "utf-8"
            soup = self._parse_html(response.text)
            rows = soup.select("tr")

            if not rows or len(rows) <= 1:
                break

            page_docs = self._parse_rows(rows, date_str)
            if not page_docs:
                break

            results.extend(page_docs)

            # 次ページリンクがあるか確認
            next_link = soup.select_one('a[href*="I_list_"]')
            if not next_link or f"I_list_{page_num + 1:03d}" not in str(soup):
                break

            page_num += 1

        return results

    def _parse_rows(self, rows, date_str: str) -> List[Dict[str, Any]]:
        """テーブル行をパースしてドキュメント情報を抽出"""
        results = []
        publish_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        for row in rows:
            cells = row.select("td")
            if len(cells) < 4:
                continue

            try:
                # TDnetの行構造: 時刻 | コード | 会社名 | タイトル（PDFリンク）
                time_cell = cells[0].get_text(strip=True)
                code_cell = cells[1].get_text(strip=True)
                # company_name = cells[2].get_text(strip=True)
                title_cell = cells[3]

                # 証券コードの抽出（4-5桁の数字）
                code_match = re.search(r'(\d{4,5})', code_cell)
                if not code_match:
                    continue
                company_code = code_match.group(1)[:4]

                # タイトルとPDFリンクの抽出
                link = title_cell.select_one("a")
                if not link:
                    continue

                title = link.get_text(strip=True)
                href = link.get("href", "")

                # PDFリンクの構築
                if href:
                    if href.startswith("http"):
                        pdf_url = href
                    else:
                        pdf_url = f"https://www.release.tdnet.info/inbs/{href}"
                else:
                    continue

                result = {
                    "company_code": company_code,
                    "title": title,
                    "publish_date": publish_date,
                    "doc_type": self._determine_doc_type(title),
                    "source_url": pdf_url,
                }
                results.append(result)

            except (IndexError, AttributeError) as e:
                logger.debug(f"Skipping row: {e}")
                continue

        return results

    def _determine_doc_type(self, title: str) -> str:
        """タイトルから資料種別を判定"""
        if "決算短信" in title:
            return "financial_report"
        elif "有価証券報告書" in title:
            return "annual_report"
        elif "説明資料" in title or "補足資料" in title:
            return "presentation"
        elif "適時開示" in title or "業績予想" in title or "配当予想" in title:
            return "press_release"
        else:
            return "other"
