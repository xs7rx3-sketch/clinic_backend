import os
from pathlib import Path

from ..commons.basics import Basics
from ..interfaces import ILayer


class Infrastructure(ILayer):
    def _build_db_infra(self):
        self._validate_layer_built()

        db_dir = Path(self.dir_path) / "db"
        os.makedirs(db_dir, exist_ok=True)
        Basics.build_init_file(db_dir)

        mappers_dir = db_dir / "mappers"
        os.makedirs(mappers_dir, exist_ok=True)
        Basics.build_init_file(mappers_dir)

        models_dir = db_dir / "models"
        os.makedirs(models_dir, exist_ok=True)
        Basics.build_init_file(models_dir)

        repos_dir = db_dir / "repositories"
        os.makedirs(repos_dir, exist_ok=True)
        Basics.build_init_file(repos_dir)

        database_path = db_dir / "database.py"
        open(database_path, "a").close()

    def _build_exceptions(self):
        self._validate_layer_built()

        exceptions_path = Path(self.dir_path) / "exceptions.py"
        open(exceptions_path, "a").close()

    def build(self) -> None:
        self._build_layer_dir("infrastructure")
        self._build_db_infra()
        self._build_exceptions()
