import os
from pathlib import Path

from ..commons.basics import Basics
from ..interfaces import ILayer


class API(ILayer):
    def _build_http(self):
        self._validate_layer_built()

        http_dir = Path(self.dir_path) / "http"
        os.makedirs(http_dir, exist_ok=True)

        Basics.build_gitkeep_file(http_dir)

    def _build_websocket(self):
        self._validate_layer_built()

        websocket_dir = Path(self.dir_path) / "websocket"
        os.makedirs(websocket_dir, exist_ok=True)

        Basics.build_gitkeep_file(websocket_dir)

    def _build_dependencies(self):
        self._validate_layer_built()

        dependencies_path = Path(self.dir_path) / "dependencies.py"
        open(dependencies_path, "a").close()
        

    def build(self) -> None:
        self._build_layer_dir("api")
        self._build_http()
        self._build_websocket()
        self._build_dependencies()
