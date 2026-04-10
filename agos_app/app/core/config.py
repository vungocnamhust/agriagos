from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Agri OS Core API"
    version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos"
    postgres_write_path_enabled: bool = True

settings = Settings()
