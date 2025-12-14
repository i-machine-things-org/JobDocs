"""
Core framework for JobDocs modular architecture
"""

from core.base_module import BaseModule
from core.app_context import AppContext
from core.module_loader import ModuleLoader

__all__ = ['BaseModule', 'AppContext', 'ModuleLoader']
