import os
from pathlib import Path

from ..commons.basics import Basics
from ..interfaces import ILayer


class Application(ILayer):
    def _build_services(self):
        self._validate_layer_built()

        services_dir = Path(self.dir_path) / "services"
        os.makedirs(services_dir, exist_ok=True)

        Basics.build_init_file(services_dir)

    def _build_ports(self):
        self._validate_layer_built()

        ports_dir = Path(self.dir_path) / "ports"
        os.makedirs(ports_dir, exist_ok=True)

        Basics.build_init_file(ports_dir)

    def _build_dtos(self):
        self._validate_layer_built()

        dtos_dir = Path(self.dir_path) / "dtos"
        os.makedirs(dtos_dir, exist_ok=True)

        Basics.build_init_file(dtos_dir)

    def _build_models(self):
        self._validate_layer_built()

        models_dir = Path(self.dir_path) / "models"
        os.makedirs(models_dir, exist_ok=True)

        Basics.build_init_file(models_dir)

    def _build_use_cases(self):
        self._validate_layer_built()

        use_cases_dir = Path(self.dir_path) / "use_cases"
        os.makedirs(use_cases_dir, exist_ok=True)

        Basics.build_init_file(use_cases_dir)

    def _build_exceptions(self):
        self._validate_layer_built()

        exceptions_path = Path(self.dir_path) / "exceptions.py"
        open(exceptions_path, "a").close()

    def _build_workflow(self):
        self._validate_layer_built()

        workflow_dir = Path(self.dir_path) / "workflow"
        os.makedirs(workflow_dir, exist_ok=True)

        Basics.build_init_file(workflow_dir)

        graph_path = Path(workflow_dir) / "graph.py"
        open(graph_path, "a").close()

        prompts_path = Path(workflow_dir) / "prompts.py"
        open(prompts_path, "a").close()

        nodes_path = Path(workflow_dir) / "nodes.py"
        open(nodes_path, "a").close()

        node_schemas_path = Path(workflow_dir) / "node_schemas.py"
        open(node_schemas_path, "a").close()

        state_schemas_path = Path(workflow_dir) / "state_schemas.py"
        open(state_schemas_path, "a").close()

    def build(self, with_workflow: bool = True) -> None:
        self._build_layer_dir("application")
        self._build_services()
        self._build_ports()
        self._build_dtos()
        self._build_models()
        self._build_use_cases()
        self._build_exceptions()

        if with_workflow:
            self._build_workflow()
