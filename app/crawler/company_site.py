import os
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from .base import BaseCrawler
import logging
import re

logger = logging.getLogger(__name__)


class CompanySiteCrawler(BaseCrawler):
    """企業サイトクローラー（プレスリリース・IR情報を取得）"""

    # よくあるIRページのパターン
    IR_PAGE_PATTERNS = [
        "/ir/",
        "/investor/",
        "/investors/",
        "/ir-info/",
        "/ir_info/",
        "/news/",
        "/press/",
        "/release/",
    ]

    # ニュース/プレスリリースのパターン
    NEWS_PATTERNS = [
        r"news",
        r"press",
        r"release",
        r"お知らせ",
        r"ニュース",
        r"プレスリリース",
    ]

    def __init__(self):
        super().__init__()
        # 追加のヘッダー
        self.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        })

    def crawl(
        self,
        company_url: str,
        company_code: str,
        max_items: int = 20
    ) -> List[Dict[str, Any]]:
        """
        企業サイトからIR情報を取得

        Args:
            company_url (str): 企業のウェブサイトURL
            company_code (str): 証券コード
            max_items (int): 取得する最大件数

        Returns:
            List[Dict[str, Any]]: IR資料情報のリスト
        """
        results = []

        try:
            # IRページを探索
            ir_page_url = self._find_ir_page(company_url)
            if not ir_page_url:
                ir_page_url = company_url

            # ページを取得してパース
            response = self._get(ir_page_url)
            soup = self._parse_html(response.text)

            # ニュース/IRリンクを抽出
            links = self._extract_ir_links(soup, ir_page_url)

            for link in links[:max_items]:
                try:
                    result = {
                        "company_code": company_code,
                        "title": link["title"],
                        "publish_date": link.get("date", ""),
                        "doc_type": self._determine_doc_type(link["title"]),
                        "source_url": link["url"],
                    }
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to parse IR link: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Company site crawling failed for {company_url}: {str(e)}")

        return results

    def _find_ir_page(self, base_url: str) -> Optional[str]:
        """IRページを探索"""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        for pattern in self.IR_PAGE_PATTERNS:
            try:
                url = urljoin(base, pattern)
                response = self.session.head(url, headers=self.headers, timeout=5)
                if response.status_code == 200:
                    return url
            except Exception:
                continue

        return None

    def _extract_ir_links(self, soup, base_url: str) -> List[Dict[str, Any]]:
        """ページからIR関連リンクを抽出"""
        links = []

        # aタグを探索
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)

            # PDF/IRリンクを抽出
            if not self._is_ir_link(href, text):
                continue

            # 絶対URLに変換
            full_url = urljoin(base_url, href)

            # 日付を抽出（近くのテキストから）
            date = self._extract_date_near_element(a_tag)

            links.append({
                "url": full_url,
                "title": text or self._extract_title_from_url(href),
                "date": date,
            })

        return links

    def _is_ir_link(self, href: str, text: str) -> bool:
        """IR関連リンクかどうかを判定"""
        # PDFリンク
        if href.lower().endswith(".pdf"):
            return True

        # IRキーワードを含む
        combined = f"{href} {text}".lower()
        ir_keywords = [
            "決算", "業績", "ir", "investor", "株主",
            "報告書", "説明資料", "開示", "適時開示"
        ]
        return any(keyword in combined for keyword in ir_keywords)

    def _extract_date_near_element(self, element) -> str:
        """要素の近くから日付を抽出"""
        # 親要素やsiblingから日付パターンを探す
        date_pattern = r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})"

        # 親要素のテキストをチェック
        parent = element.find_parent()
        if parent:
            text = parent.get_text()
            match = re.search(date_pattern, text)
            if match:
                year, month, day = match.groups()
                return f"{year}-{int(month):02d}-{int(day):02d}"

        return ""

    def _extract_title_from_url(self, url: str) -> str:
        """URLからタイトルを推測"""
        # ファイル名を取得
        path = urlparse(url).path
        filename = os.path.basename(path)
        # 拡張子を除去
        name = os.path.splitext(filename)[0]
        return name

    def _determine_doc_type(self, title: str) -> str:
        """タイトルから資料種別を判定"""
        title_lower = title.lower()

        if any(kw in title_lower for kw in ["決算短信", "四半期", "中間"]):
            return "financial_report"
        elif any(kw in title_lower for kw in ["有価証券報告書", "年次報告"]):
            return "annual_report"
        elif any(kw in title_lower for kw in ["説明資料", "プレゼン", "資料"]):
            return "presentation"
        elif any(kw in title_lower for kw in ["プレスリリース", "ニュース", "お知らせ"]):
            return "press_release"
        else:
            return "other"
