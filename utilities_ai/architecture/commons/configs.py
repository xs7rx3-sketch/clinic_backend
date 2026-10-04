import os
from pathlib import Path
from typing import Optional

from ..interfaces import Structure
from ..types import PathLike
from .basics import Basics


class Configs(Structure):
    def _build_secret_containers(self):
        env_path = Path(self.root_path) / ".env"
        open(env_path, "a").close()

        env_example_path = Path(self.root_path) / ".env.example"
        open(env_example_path, "a").close()

    def _build_project_config(self, dir_path: Optional[PathLike]):
        if dir_path is None:
            dir_path = self.root_path

        config_dir = Path(dir_path) / "config"
        os.makedirs(config_dir, exist_ok=True)

        config_ini = Path(config_dir) / "config.ini"
        open(config_ini, "a").close()

        config_py = Path(config_dir) / "config.py"
        open(config_py, "a").close()

        Basics.build_init_file(config_dir)

    def build(self, config_dir: Optional[PathLike] = None) -> None:
        self._build_secret_containers()
        self._build_project_config(config_dir)
