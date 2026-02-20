"""Tests for sponsor API routes — CRUD with status management."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestSponsorListRoute:
    """Test GET /api/v1/sponsors."""

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_list_sponsors(
        self, mock_repo_factory: MagicMock, client: TestClient
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.find_all.return_value = [
            {"sponsor_id": "s1", "name": "Acme Corp", "status": "active"}
        ]
        mock_repo.count.return_value = 1
        mock_repo_factory.return_value = mock_repo
        resp = client.get("/api/v1/sponsors")
        assert resp.status_code == 200

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_list_sponsors_empty(
        self, mock_repo_factory: MagicMock, client: TestClient
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.find_all.return_value = []
        mock_repo.count.return_value = 0
        mock_repo_factory.return_value = mock_repo
        resp = client.get("/api/v1/sponsors")
        assert resp.status_code == 200


class TestSponsorGetRoute:
    """Test GET /api/v1/sponsors/{id}."""

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_get_sponsor(
        self, mock_repo_factory: MagicMock, client: TestClient
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = {
            "sponsor_id": "s1",
            "name": "Acme Corp",
            "status": "active",
        }
        mock_repo_factory.return_value = mock_repo
        resp = client.get("/api/v1/sponsors/s1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Acme Corp"

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_get_not_found(
        self, mock_repo_factory: MagicMock, client: TestClient
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        mock_repo_factory.return_value = mock_repo
        resp = client.get("/api/v1/sponsors/nope")
        assert resp.status_code == 404


class TestSponsorCreateRoute:
    """Test POST /api/v1/sponsors (admin)."""

    def test_create_requires_admin(
        self, client: TestClient, user_headers: dict
    ) -> None:
        resp = client.post(
            "/api/v1/sponsors",
            json={"name": "Test"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_create_sponsor(
        self,
        mock_repo_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.create.return_value = None
        mock_repo_factory.return_value = mock_repo
        resp = client.post(
            "/api/v1/sponsors",
            json={"name": "Acme Corp", "contact_email": "info@acme.com"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Acme Corp"


class TestSponsorDeleteRoute:
    """Test DELETE /api/v1/sponsors/{id} (admin)."""

    def test_delete_requires_admin(
        self, client: TestClient, user_headers: dict
    ) -> None:
        resp = client.delete(
            "/api/v1/sponsors/s1", headers=user_headers
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_delete_sponsor(
        self,
        mock_repo_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.delete.return_value = 1
        mock_repo_factory.return_value = mock_repo
        resp = client.delete(
            "/api/v1/sponsors/s1", headers=admin_headers
        )
        assert resp.status_code == 204

    @patch("fittrack.api.routes.sponsors._get_repo")
    def test_delete_not_found(
        self,
        mock_repo_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.delete.return_value = 0
        mock_repo_factory.return_value = mock_repo
        resp = client.delete(
            "/api/v1/sponsors/s1", headers=admin_headers
        )
        assert resp.status_code == 404


class TestSponsorServiceUnit:
    """Unit tests for SponsorService logic."""

    def test_create_sponsor(self):
        from fittrack.services.sponsors import SponsorService

        mock_repo = MagicMock()
        mock_repo.create.return_value = None
        svc = SponsorService(sponsor_repo=mock_repo)
        result = svc.create_sponsor(name="Test Corp", status="active")
        assert result["name"] == "Test Corp"
        assert result["sponsor_id"]

    def test_create_requires_name(self):
        from fittrack.services.sponsors import SponsorError, SponsorService

        svc = SponsorService(sponsor_repo=MagicMock())
        with pytest.raises(SponsorError, match="name is required"):
            svc.create_sponsor(status="active")

    def test_create_invalid_status(self):
        from fittrack.services.sponsors import SponsorError, SponsorService

        svc = SponsorService(sponsor_repo=MagicMock())
        with pytest.raises(SponsorError, match="Invalid status"):
            svc.create_sponsor(name="Test", status="bogus")

    def test_deactivate(self):
        from fittrack.services.sponsors import SponsorService

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = {
            "sponsor_id": "s1", "name": "Test", "status": "active"
        }
        mock_repo.update.return_value = 1
        svc = SponsorService(sponsor_repo=mock_repo)
        result = svc.deactivate_sponsor("s1")
        assert result["status"] == "inactive"

    def test_activate(self):
        from fittrack.services.sponsors import SponsorService

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = {
            "sponsor_id": "s1", "name": "Test", "status": "inactive"
        }
        mock_repo.update.return_value = 1
        svc = SponsorService(sponsor_repo=mock_repo)
        result = svc.activate_sponsor("s1")
        assert result["status"] == "active"

    def test_get_not_found(self):
        from fittrack.services.sponsors import SponsorError, SponsorService

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        svc = SponsorService(sponsor_repo=mock_repo)
        with pytest.raises(SponsorError, match="not found"):
            svc.get_sponsor("nope")

    def test_delete_sponsor(self):
        from fittrack.services.sponsors import SponsorService

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = {"sponsor_id": "s1", "name": "Test"}
        mock_repo.delete.return_value = 1
        svc = SponsorService(sponsor_repo=mock_repo)
        assert svc.delete_sponsor("s1") is True

    def test_list_with_status_filter(self):
        from fittrack.services.sponsors import SponsorService

        mock_repo = MagicMock()
        mock_repo.count.return_value = 2
        mock_repo.find_all.return_value = [
            {"sponsor_id": "s1"}, {"sponsor_id": "s2"}
        ]
        svc = SponsorService(sponsor_repo=mock_repo)
        result = svc.list_sponsors(status="active")
        assert result["pagination"]["total_items"] == 2

    def test_list_invalid_status(self):
        from fittrack.services.sponsors import SponsorError, SponsorService

        svc = SponsorService(sponsor_repo=MagicMock())
        with pytest.raises(SponsorError, match="Invalid status"):
            svc.list_sponsors(status="bogus")

    def test_update_no_fields(self):
        from fittrack.services.sponsors import SponsorError, SponsorService

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = {"sponsor_id": "s1", "name": "Test"}
        svc = SponsorService(sponsor_repo=mock_repo)
        with pytest.raises(SponsorError, match="No fields"):
            svc.update_sponsor("s1")
