import pytest


class TestDocumentsAPI:
    """ドキュメントAPIのテスト"""

    def test_get_documents_empty(self, client):
        """ドキュメント一覧取得（空）"""
        response = client.get("/api/documents/")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_documents(self, client, sample_document):
        """ドキュメント一覧取得"""
        response = client.get("/api/documents/?days=365")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "2024年度決算短信"

    def test_get_document_by_id(self, client, sample_document):
        """ドキュメント詳細取得"""
        response = client.get(f"/api/documents/{sample_document.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "2024年度決算短信"
        assert data["doc_type"] == "financial_report"

    def test_get_document_not_found(self, client):
        """存在しないドキュメント"""
        response = client.get("/api/documents/9999")
        assert response.status_code == 404

    def test_create_document(self, client, sample_company):
        """ドキュメント作成"""
        response = client.post(
            "/api/documents/",
            json={
                "company_id": sample_company.id,
                "title": "新規レポート",
                "doc_type": "press_release",
                "publish_date": "2024-02-01",
                "source_url": "https://example.com/new.pdf",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "新規レポート"
        assert data["doc_type"] == "press_release"
