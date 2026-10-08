from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    environment: str = 'development'
    enable_demo_data: bool = False
    database_url: str = 'sqlite:///./data/interview.db'
    app_secret: str = ''
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-2.5-flash'
    supabase_url: str = ''
    supabase_service_key: str = ''
    evidence_bucket: str = 'interview-evidence'
    detector_validation_file: str = './data/detector-validation.json'
    proctor_config_file: str = './data/proctor-config.json'
    public_url: str = 'http://localhost:5173'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_use_tls: bool = True
    data_dir: str = './data'
    evidence_retention_days: int = 30


settings = Settings()
if settings.environment == 'production':
    settings.enable_demo_data = False
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
if settings.environment == 'production':
    if not (len(settings.app_secret) >= 32 and settings.database_url.startswith('postgresql')
            and settings.supabase_url and settings.supabase_service_key):
        raise RuntimeError('Production requires Postgres, private Supabase storage, and APP_SECRET (32+ characters).')
else:
    secret_path = Path(settings.data_dir) / '.secret'
    if not settings.app_secret:
        if not secret_path.exists():
            secret_path.write_text(secrets.token_urlsafe(48))
        settings.app_secret = secret_path.read_text().strip()
