import json
from typing import Dict
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_connections: Dict[str, str] = {}
    allow_write: bool = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Backward compatibility for array env vars
        import os
        if not self.mongo_connections:
            uris = os.getenv("MONGO_URIS")
            names = os.getenv("MONGO_NAMES")
            if uris and names:
                try:
                    uri_list = json.loads(uris)
                    name_list = json.loads(names)
                    self.mongo_connections = dict(zip(name_list, uri_list))
                except Exception:
                    pass
            elif os.getenv("MONGO_CONNECTIONS"):
                try:
                    self.mongo_connections = json.loads(os.getenv("MONGO_CONNECTIONS"))
                except Exception:
                    pass

settings = Settings()
