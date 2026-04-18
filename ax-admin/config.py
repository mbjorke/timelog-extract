from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    admin_api_key: str = "change-me-admin-key"

    nameserver1: str = "ns1.yourdomain.ax"
    nameserver2: str = "ns2.yourdomain.ax"

    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""

    registry_api_url: str = "https://registry.ax/api"
    registry_api_key: str = ""
    registry_reseller_id: str = ""

    database_url: str = "sqlite:///./ax_admin.db"
    secret_key: str = "change-me-secret-key-min-32-chars"

    model_config = {"env_file": ".env"}


settings = Settings()
