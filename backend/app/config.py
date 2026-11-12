from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./social.db'
    redis_url: str = 'redis://localhost:6379/0'
    jwt_secret: str
    token_key: str
    admin_email: str = 'admin@localhost'
    admin_password: str
    frontend_origin: str = 'http://localhost:3000'
    cookie_secure: bool = False
    timezone: str = 'America/Bogota'
    demo_mode: bool = False
    meta_graph_version: str = ''
    public_cache_seconds: int = 60
    public_requests_per_minute: int = 120
    production: bool = False

@lru_cache
def settings():
    s = Settings()
    if len(s.jwt_secret) < 32 or len(s.admin_password) < 12:
        raise ValueError('JWT_SECRET >=32 y ADMIN_PASSWORD >=12 caracteres requeridos')
    return s
