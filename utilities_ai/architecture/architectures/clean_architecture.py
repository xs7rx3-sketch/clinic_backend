from pathlib import Path

from ..commons.configs import Configs
from ..commons.essentials import Essentials
from ..interfaces import Structure
from ..layers.api import API
from ..layers.application import Application
from ..layers.domain import Domain
from ..layers.infrastructure import Infrastructure


class CleanArchitecture(Structure):
    def build(self, with_workflow: bool = True) -> None:
        Essentials(self.root_path).build()
        Configs(self.root_path).build(self.src_path / "shared")
        Domain(self.root_path).build()
        Application(self.root_path).build(with_workflow)
        API(self.root_path).build()
        Infrastructure(self.root_path).build()
