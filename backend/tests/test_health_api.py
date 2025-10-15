import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime


@pytest.fixture
def client():
    """Create test client"""
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_services():
    """Mock all services for health checks"""
    with patch("api.health.ConversionService") as mock_conversion, \
         patch("api.health.batch_conversion_service") as mock_batch, \
         patch("api.health.ai_config") as mock_ai_config:

        mock_batch.active_batches = {}
        mock_ai_config.get_available_providers.return_value = ["deepseek", "openai"]
        mock_ai_config.DEFAULT_AI_PROVIDER = "deepseek"

        yield {
            "conversion": mock_conversion,
            "batch": mock_batch,
            "ai_config": mock_ai_config
        }


class TestBasicHealthCheck:
    """Test basic health check endpoint"""

    def test_health_check_success(self, client):
        """Test basic health check returns success"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "EBookAI"
        assert data["version"] == "1.0.0"

    def test_health_check_timestamp_format(self, client):
        """Test health check timestamp is in ISO format"""
        response = client.get("/api/health")
        data = response.json()

        timestamp = data["timestamp"]
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))


class TestDetailedHealthCheck:
    """Test detailed health check endpoint"""

    def test_detailed_health_check_all_healthy(self, client, mock_services):
        """Test detailed health check when all services are healthy"""
        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "components" in data
        assert "check_duration" in data
        assert data["check_duration"] >= 0

        assert "conversion_service" in data["components"]
        assert data["components"]["conversion_service"]["status"] == "healthy"

        assert "batch_conversion_service" in data["components"]
        assert data["components"]["batch_conversion_service"]["status"] == "healthy"

        assert "ai_service" in data["components"]
        assert data["components"]["ai_service"]["status"] == "healthy"

    def test_detailed_health_check_conversion_service_error(self, client, mock_services):
        """Test detailed health check when conversion service fails"""
        mock_services["conversion"].side_effect = Exception("Calibre not found")

        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["components"]["conversion_service"]["status"] == "unhealthy"
        assert "Calibre not found" in data["components"]["conversion_service"]["message"]

    def test_detailed_health_check_batch_service_error(self, client, mock_services):
        """Test detailed health check when batch service fails"""
        mock_services["batch"].active_batches = Mock(side_effect=Exception("Batch service error"))

        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["components"]["batch_conversion_service"]["status"] == "unhealthy"

    def test_detailed_health_check_no_ai_providers(self, client, mock_services):
        """Test detailed health check when no AI providers are configured"""
        mock_services["ai_config"].get_available_providers.return_value = []

        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["components"]["ai_service"]["status"] == "degraded"
        assert data["components"]["ai_service"]["message"] == "No AI providers configured"
        assert data["components"]["ai_service"]["available_providers"] == []

    def test_detailed_health_check_ai_service_error(self, client, mock_services):
        """Test detailed health check when AI service fails"""
        mock_services["ai_config"].get_available_providers.side_effect = Exception("AI config error")

        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["components"]["ai_service"]["status"] == "unhealthy"

    def test_detailed_health_check_includes_batch_count(self, client, mock_services):
        """Test detailed health check includes active batch count"""
        mock_services["batch"].active_batches = {"batch1": {}, "batch2": {}}

        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert data["components"]["batch_conversion_service"]["active_batches"] == 2

    def test_detailed_health_check_includes_ai_providers(self, client, mock_services):
        """Test detailed health check includes AI provider information"""
        response = client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()

        ai_component = data["components"]["ai_service"]
        assert "available_providers" in ai_component
        assert "deepseek" in ai_component["available_providers"]
        assert ai_component["default_provider"] == "deepseek"


class TestSystemMetrics:
    """Test system metrics endpoint"""

    def test_get_system_metrics_success(self, client, mock_services):
        """Test successful retrieval of system metrics"""
        response = client.get("/api/health/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "timestamp" in data
        assert "batch_conversion" in data
        assert "ai_service" in data
        assert "system" in data

    def test_get_system_metrics_batch_info(self, client, mock_services):
        """Test system metrics includes batch conversion info"""
        mock_services["batch"].active_batches = {"batch1": {}}

        response = client.get("/api/health/metrics")
        data = response.json()

        assert data["batch_conversion"]["active_batches"] == 1
        assert "total_batches_processed" in data["batch_conversion"]
        assert "average_processing_time" in data["batch_conversion"]

    def test_get_system_metrics_ai_info(self, client, mock_services):
        """Test system metrics includes AI service info"""
        response = client.get("/api/health/metrics")
        data = response.json()

        assert data["ai_service"]["configured_providers"] == 2
        assert data["ai_service"]["default_provider"] == "deepseek"
        assert "total_requests" in data["ai_service"]
        assert "success_rate" in data["ai_service"]

    def test_get_system_metrics_error_handling(self, client, mock_services):
        """Test system metrics error handling"""
        mock_services["batch"].active_batches = Mock(side_effect=Exception("Metrics error"))

        response = client.get("/api/health/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "error" in data
        assert "Failed to retrieve system metrics" in data["error"]


class TestReadinessCheck:
    """Test readiness check endpoint"""

    def test_readiness_check_ready(self, client, mock_services):
        """Test readiness check when service is ready"""
        response = client.get("/api/health/readiness")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "ready to accept requests" in data["message"]

    def test_readiness_check_no_ai_providers(self, client, mock_services):
        """Test readiness check when no AI providers configured"""
        mock_services["ai_config"].get_available_providers.return_value = []

        response = client.get("/api/health/readiness")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "not_ready"
        assert "No AI providers configured" in data["message"]

    def test_readiness_check_service_error(self, client, mock_services):
        """Test readiness check when service initialization fails"""
        mock_services["conversion"].side_effect = Exception("Service initialization failed")

        response = client.get("/api/health/readiness")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "not_ready"
        assert "Service not ready" in data["message"]


class TestLivenessCheck:
    """Test liveness check endpoint"""

    def test_liveness_check_success(self, client):
        """Test liveness check always returns success"""
        response = client.get("/api/health/liveness")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "alive"
        assert "timestamp" in data
        assert data["message"] == "Service is alive"

    def test_liveness_check_timestamp_format(self, client):
        """Test liveness check timestamp is in ISO format"""
        response = client.get("/api/health/liveness")
        data = response.json()

        timestamp = data["timestamp"]
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))


class TestHealthCheckIntegration:
    """Integration tests for health checks"""

    def test_all_health_endpoints_available(self, client):
        """Test all health endpoints are accessible"""
        endpoints = [
            "/api/health",
            "/api/health/detailed",
            "/api/health/metrics",
            "/api/health/readiness",
            "/api/health/liveness"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """Test health check responses have consistent structure"""
        response = client.get("/api/health")
        data = response.json()

        required_fields = ["status", "timestamp", "service", "version"]
        for field in required_fields:
            assert field in data

    def test_detailed_health_check_duration_reasonable(self, client, mock_services):
        """Test detailed health check completes in reasonable time"""
        response = client.get("/api/health/detailed")
        data = response.json()

        assert data["check_duration"] < 5.0
