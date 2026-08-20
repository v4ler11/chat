from core import BASE_DIR


LOGS_DIR = BASE_DIR / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

OTEL_ENDPOINT = "https://otel.olap.valerii.casa/v1/traces"
OTEL_SERVICE_NAME = "tmp_python_service"
OTEL_NAMESPACE = "production"
OTEL_DEPLOYMENT_ENV = "maxine"
