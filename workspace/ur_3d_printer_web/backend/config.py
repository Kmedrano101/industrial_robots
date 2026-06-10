"""Environment-based configuration for the web interface backend."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    web_port: int = 8090
    upload_dir: str = "/uploads"
    max_upload_size_mb: int = 100
    cors_origins: str = "*"
    ros_domain_id: int = 0
    rmw_implementation: str = "rmw_cyclonedds_cpp"
    joint_state_throttle_hz: float = 10.0
    ur_type: str = "ur7e"
    ws_heartbeat_sec: float = 5.0
    static_dir: str = "/app/static"

    # Test panel — exposes manual jog / dashboard buttons through the
    # browser. Off by default; flip on with ENABLE_TEST_PANEL=true in .env
    # for bring-up / commissioning, off again for production deployments.
    enable_test_panel: bool = False
    # Hard safety caps applied server-side regardless of what the client
    # sends. The /jog endpoint clamps and refuses values past these.
    jog_max_delta_rad: float = 0.0872665  # 5°
    jog_max_velocity_rad_s: float = 0.5
    jog_min_duration_s: float = 0.5

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
