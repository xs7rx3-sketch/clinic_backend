import os.path
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .commons.basics import Basics
from .types import PathLike


class Structure(ABC):
    def __init__(self, root_path: PathLike = "."):
        self._validate_path_existence(root_path)

        self.root_path = root_path
        self.src_path = Path(self.root_path) / "src"

    @staticmethod
    def _validate_path_existence(path: PathLike) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"The path `{path}` does not exist.")

    @abstractmethod
    def build(self) -> None:
        raise NotImplementedError()


class ILayer(Structure, ABC):
    def __init__(self, root_path: PathLike = "."):
        super().__init__(root_path)
        self.model_dir = Path(self.src_path) / "model"
        self.dir_path = None

    @property
    def dir_path(self) -> Optional[PathLike]:
        return self._dir_path

    @dir_path.setter
    def dir_path(self, path: Optional[PathLike]):
        self._dir_path = path

    def _build_layer_dir(self, layer: PathLike):
        self.dir_path = Path(self.model_dir) / layer
        os.makedirs(self.dir_path, exist_ok=True)

        Basics.build_init_file(self.dir_path)

    def _validate_layer_built(self):
        if self.dir_path is None:
            raise FileExistsError("Layer directory does not exist")
