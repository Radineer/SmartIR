import pytest


class TestAuthAPI:
    """認証APIのテスト"""

    def test_register_user(self, client):
        """ユーザー登録"""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "name": "新規ユーザー",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "新規ユーザー"
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client, sample_user):
        """重複メールアドレスで登録"""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_login_success(self, client, sample_user):
        """ログイン成功"""
        response = client.post(
            "/api/auth/login",
            data={"username": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, sample_user):
        """パスワード間違い"""
        response = client.post(
            "/api/auth/login",
            data={"username": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_user_not_found(self, client):
        """存在しないユーザー"""
        response = client.post(
            "/api/auth/login",
            data={"username": "notexist@example.com", "password": "password123"},
        )
        assert response.status_code == 401

    def test_get_me(self, client, auth_headers):
        """現在のユーザー情報取得"""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    def test_get_me_unauthorized(self, client):
        """未認証でユーザー情報取得"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
