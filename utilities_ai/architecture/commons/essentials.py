from pathlib import Path

from ..interfaces import Structure


class Essentials(Structure):
    def _build_requirements(self):
        requirements_path = Path(self.root_path) / "requirements.txt"
        open(requirements_path, "a").close()

    def _build_gitignore(self):
        gitignore_path = Path(self.root_path) / ".gitignore"
        open(gitignore_path, "a").close()

    def _build_readme(self):
        readme_path = Path(self.root_path) / "README.md"
        open(readme_path, "a").close()

    def build(self) -> None:
        self._build_requirements()
        self._build_gitignore()
        self._build_readme()
