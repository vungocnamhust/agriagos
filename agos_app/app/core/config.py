from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Agri OS Core API"
    version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agriagos"

settings = Settings()
