from pathlib import Path

from ..types import PathLike


class Basics:
    @staticmethod
    def build_init_file(dir_path: PathLike = ""):
        init_file_path = Path(dir_path) / "__init__.py"
        open(init_file_path, "a").close()

    @staticmethod
    def build_gitkeep_file(dir_path: PathLike = ""):
        gitkeep_file_path = Path(dir_path) / ".gitkeep"
        open(gitkeep_file_path, "a").close()
