from pathlib import Path
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicit application-owned file only. Never search another project's credentials.
if os.environ.get('YEATS_ENVIRONMENT','development') == 'development' and os.name == 'nt':
    secret_file=Path(os.environ.get('LOCALAPPDATA',''))/'YEATS/secrets/wechat.dev.env'
    if secret_file.is_file(): load_dotenv(secret_file,override=False)
    database_file=secret_file.parent/'database.dev.env'
    if database_file.is_file():load_dotenv(database_file,override=False)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='YEATS_', env_file='services/api/.env', extra='ignore')
    environment: str = 'development'
    database_url: str = 'sqlite:///runtime/yeats-development.db'
    file_root: Path = Path('runtime/private-files')
    public_base_url: str = 'http://127.0.0.1:8930'
    wechat_appid: str = ''
    wechat_secret: str = ''
    session_hours: int = 168
    upload_image_bytes: int = 10 * 1024 * 1024
    upload_image_count: int = 9
    policies_confirmed: bool = False
    subscription_templates: list[str] = []
    subscription_rules: dict = {}  # event kind -> approved template + field map
    # No implicit real UGC approval when WeChat safety is unconfigured.
    content_safety_required: bool = True
    enable_development_login: bool = False
    viewing_default_days: int = 7
    viewing_start_policy: str = 'approval_time'

settings = Settings()
if settings.enable_development_login and settings.environment!='development':
    raise RuntimeError('Development login is prohibited outside development')
if settings.environment not in {'development','test','acceptance','production'}:
    raise RuntimeError('Unknown YEATS environment')
if settings.environment in {'acceptance','production'}:
    if not settings.database_url.startswith('postgresql+psycopg://'):
        raise RuntimeError('PostgreSQL required outside local development/tests')
    if not settings.public_base_url.startswith('https://'):
        raise RuntimeError('HTTPS required')
    if not settings.content_safety_required:
        raise RuntimeError('Content safety cannot be disabled')
if settings.environment == 'production' and (not settings.policies_confirmed or not settings.wechat_appid or not settings.wechat_secret):
    raise RuntimeError('Production policy and WeChat configuration incomplete')
