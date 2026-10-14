from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    environment: str = 'development'
    enable_demo_data: bool = False
    database_url: str = 'sqlite:///./data/interview.db'
    app_secret: str = ''
    ai_provider: str = 'gemini'
    groq_api_key: str = ''
    groq_model: str = 'llama-3.3-70b-versatile'
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
    email_provider: str = 'smtp'
    brevo_api_key: str = ''
    email_from: str = ''
    data_dir: str = './data'
    evidence_retention_days: int = 30


settings = Settings()
if settings.environment == 'production':
    settings.enable_demo_data = False
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
if settings.environment == 'production':
    invalid=[]
    if len(settings.app_secret)<32:invalid.append('APP_SECRET (at least 32 characters)')
    if not settings.database_url.startswith('postgresql+psycopg://'):invalid.append('DATABASE_URL (postgresql+psycopg:// connection string)')
    if not settings.supabase_url.startswith('https://'):invalid.append('SUPABASE_URL (HTTPS project URL)')
    if not settings.supabase_service_key:invalid.append('SUPABASE_SERVICE_KEY')
    if invalid:raise RuntimeError('Missing or invalid production settings: '+', '.join(invalid))
else:
    secret_path = Path(settings.data_dir) / '.secret'
    if not settings.app_secret:
        if not secret_path.exists():
            secret_path.write_text(secrets.token_urlsafe(48))
        settings.app_secret = secret_path.read_text().strip()
