from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    elevenlabs_api_key: str = ""
    # "auto" = first default/personal voice on your account (required for free API plan).
    elevenlabs_voice_id: str = "auto"
    tts_model_id: str = "eleven_turbo_v2_5"
    stt_model_id: str = "scribe_v2"
    language_code: str = "swe"


settings = Settings()
