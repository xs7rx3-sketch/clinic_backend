import os
from pathlib import Path

from ..commons.basics import Basics
from ..interfaces import ILayer


class Domain(ILayer):
    def _build_ports(self):
        self._validate_layer_built()

        ports_dir = Path(self.dir_path) / "ports"
        os.makedirs(ports_dir, exist_ok=True)

        Basics.build_init_file(ports_dir)

    def _build_services(self):
        self._validate_layer_built()

        ports_dir = Path(self.dir_path) / "services"
        os.makedirs(ports_dir, exist_ok=True)

        Basics.build_init_file(ports_dir)

    def _build_exceptions(self):
        self._validate_layer_built()

        exceptions_path = Path(self.dir_path) / "exceptions.py"
        open(exceptions_path, "a").close()

    def build(self) -> None:
        self._build_layer_dir("domain")
        self._build_ports()
        self._build_services()
        self._build_exceptions()
