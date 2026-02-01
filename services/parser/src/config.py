"""OCR service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OCR service settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Model settings
    model_name: str = "tencent/HunyuanOCR"
    device: str = "auto"  # "cuda", "mps", "cpu", or "auto"
    torch_dtype: str = "float16"  # "float16", "bfloat16", "float32"

    # S3 settings (for batch mode)
    s3_input_bucket: str = "palateful-ocr-inputs"
    s3_output_bucket: str = "palateful-ocr-outputs"
    aws_region: str = "us-east-1"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001


settings = Settings()
