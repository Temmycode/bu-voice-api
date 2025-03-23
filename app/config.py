from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expiration_minutes: int
    google_client_id: str
    google_client_secret: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_secret_key: str
    mailgun_api_key: str
    novu_secret_key: str
    gemini_api_key: str

    model_config = {
        "env_file": ".env",
    }


settings = Settings()
