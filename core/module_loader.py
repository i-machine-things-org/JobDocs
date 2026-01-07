"""
Dynamic module loader for JobDocs

Discovers and loads modules from the modules directory,
validates them, and provides them to the main application.
"""

import importlib
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Type
import sys

from core.base_module import BaseModule
from core.app_context import AppContext


class ModuleLoader:
    """
    Discovers and loads JobDocs modules dynamically.

    Modules are discovered by scanning the modules/ directory for
    subdirectories containing a module.py file with a class that
    inherits from BaseModule.
    """

    def __init__(self, modules_dir: Path):
        """
        Initialize the module loader.

        Args:
            modules_dir: Path to the modules directory
        """
        self.modules_dir = modules_dir
        self.loaded_modules: List[BaseModule] = []
        self._module_classes: Dict[str, Type[BaseModule]] = {}

    def discover_modules(self) -> List[str]:
        """
        Discover all available modules in the modules directory.

        Returns:
            List of module names (directory names)
        """
        # Check if running in a PyInstaller frozen environment
        is_frozen = getattr(sys, 'frozen', False)

        # Deprecated modules (kept in codebase but not loaded)
        deprecated_modules = {'add_to_job'}

        if is_frozen:
            # In frozen mode, return hardcoded list of modules
            # These must match the modules in the spec file's hiddenimports
            all_modules = [
                'quote',
                'job',
                'add_to_job',
                'bulk',
                'search',
                'import_bp',
                'history',
                'reporting'
            ]
            return [m for m in all_modules if m not in deprecated_modules]
        else:
            # In development mode, discover from filesystem
            if not self.modules_dir.exists():
                return []

            module_names = []
            for item in self.modules_dir.iterdir():
                if item.is_dir() and not item.name.startswith('_'):
                    # Skip deprecated modules
                    if item.name in deprecated_modules:
                        continue
                    module_file = item / 'module.py'
                    if module_file.exists():
                        module_names.append(item.name)

            return module_names

    def load_module(self, module_name: str) -> Type[BaseModule]:
        """
        Load a module class from the modules directory.

        Args:
            module_name: Name of the module (directory name)

        Returns:
            The module class (not instantiated)

        Raises:
            ImportError: If module cannot be loaded
            ValueError: If module doesn't contain a valid BaseModule subclass
        """
        # Check if running in a PyInstaller frozen environment
        is_frozen = getattr(sys, 'frozen', False)

        if is_frozen:
            # In frozen mode, use standard import (modules are bundled in executable)
            module_import_name = f"modules.{module_name}.module"
            try:
                module = importlib.import_module(module_import_name)
            except ImportError as e:
                raise ImportError(f"Could not import frozen module {module_import_name}: {e}")
        else:
            # In development mode, load from file path
            module_path = self.modules_dir / module_name / 'module.py'

            if not module_path.exists():
                raise ImportError(f"Module file not found: {module_path}")

            # Load the module
            spec = importlib.util.spec_from_file_location(
                f"modules.{module_name}.module",
                module_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module spec for {module_name}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

        # Find the BaseModule subclass in the module
        module_class = None
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and
                issubclass(obj, BaseModule) and
                obj is not BaseModule):
                module_class = obj
                break

        if module_class is None:
            raise ValueError(
                f"Module {module_name} does not contain a BaseModule subclass"
            )

        self._module_classes[module_name] = module_class
        return module_class

    def load_all_modules(
        self,
        app_context: AppContext,
        experimental_enabled: bool = False,
        disabled_modules: List[str] = None
    ) -> List[BaseModule]:
        """
        Discover and load all modules.

        Args:
            app_context: Application context to pass to modules
            experimental_enabled: Whether to load experimental modules
            disabled_modules: List of module names to skip loading

        Returns:
            List of initialized module instances, sorted by order
        """
        module_names = self.discover_modules()
        self.loaded_modules = []
        errors = []
        disabled_modules = disabled_modules or []

        for module_name in module_names:
            try:
                # Skip disabled modules
                if module_name in disabled_modules:
                    app_context.log_message(
                        f"Skipping disabled module: {module_name}"
                    )
                    continue

                module_class = self.load_module(module_name)
                instance = module_class()

                # Skip experimental modules if not enabled
                if instance.is_experimental() and not experimental_enabled:
                    app_context.log_message(
                        f"Skipping experimental module: {module_name}"
                    )
                    continue

                # Initialize the module
                instance.initialize(app_context)
                self.loaded_modules.append(instance)

                app_context.log_message(
                    f"Loaded module: {module_name} ({instance.get_name()})"
                )

            except Exception as e:
                error_msg = f"Failed to load module {module_name}: {str(e)}"
                errors.append(error_msg)
                app_context.log_message(f"ERROR: {error_msg}")

        # Sort modules by order
        self.loaded_modules.sort(key=lambda m: m.get_order())

        # Show errors if any
        if errors:
            app_context.show_error(
                "Module Loading Errors",
                f"Some modules failed to load:\n\n" + "\n".join(errors)
            )

        return self.loaded_modules

    def get_module(self, module_name: str) -> BaseModule:
        """
        Get a loaded module by name.

        Args:
            module_name: Name of the module

        Returns:
            The module instance

        Raises:
            KeyError: If module not found
        """
        for module in self.loaded_modules:
            if module.__class__.__name__.lower() == module_name.lower():
                return module
        raise KeyError(f"Module not found: {module_name}")

    def unload_all(self):
        """Cleanup and unload all modules"""
        for module in self.loaded_modules:
            try:
                module.cleanup()
            except Exception as e:
                print(f"Error cleaning up module {module.get_name()}: {e}")
        self.loaded_modules.clear()
