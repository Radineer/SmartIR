import pytest


class TestCompaniesAPI:
    """企業APIのテスト"""

    def test_get_companies_empty(self, client):
        """企業一覧取得（空）"""
        response = client.get("/api/companies/")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_companies(self, client, sample_company):
        """企業一覧取得"""
        response = client.get("/api/companies/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "テスト株式会社"
        assert data[0]["ticker_code"] == "9999"

    def test_get_company_by_id(self, client, sample_company):
        """企業詳細取得"""
        response = client.get(f"/api/companies/{sample_company.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "テスト株式会社"
        assert data["sector"] == "テクノロジー"

    def test_get_company_not_found(self, client):
        """存在しない企業"""
        response = client.get("/api/companies/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Company not found"
