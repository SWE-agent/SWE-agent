"""
Module for defining PluginBaseModel, a base class to register and
load plugins via entry points.

Example:
    >>> # Define the base for repository configurations
    >>> class BaseRepoConfig(PluginBaseModel, plugin_category="repo_configs"): ...
    >>>
    >>> # Concrete plugin implementation:
    >>> class LocalRepoConfig(BaseRepoConfig):
    ...     type: Literal["local"] = "local"
    ...     path: Path
    ...     base_commit: str = "HEAD"
    >>>
    >>> # Obtain the union type for all repo config plugins
    >>> RepoConfigUnion = BaseRepoConfig.any()
    >>> # Use in another model:
    >>> class EnvConfig(BaseModel):
    ...     repo: RepoConfigUnion
"""

from __future__ import annotations

from functools import reduce
from importlib.metadata import entry_points
from operator import or_
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class PluginBaseModel(BaseModel):
    """
    Base class for plugin models, supporting plugin registration and
    loading via entry points.

    Class Attributes:
        registry (list[Type[PluginBaseModel]]): Registered plugin classes.
        plugin_category (str): Name of the plugin entry-point category for discovery.
        entrypoint_namespace (str): Entry-point namespace for plugin lookup.
    """

    entrypoint_namespace: ClassVar[str] = "sweagent_plugins"
    model_config = ConfigDict(extra="forbid")

    def __init_subclass__(cls, plugin_category: None = None, **kwargs):
        """
        Initialize a subclass, setting up the plugin registry and category.

        Args:
            plugin_category (str): Plugin entry-point category name for discovery.
        """
        super().__init_subclass__(**kwargs)

        # Initialize registry on direct subclasses of PluginBaseModel
        if PluginBaseModel in cls.__bases__:
            cls.registry: list[type[PluginBaseModel]] = []

        # Store category for plugin discovery
        if plugin_category is not None:
            cls.plugin_category = plugin_category

        # Automatically register subclasses defining a 'type' annotation
        if "type" in cls.__annotations__:
            for base in cls.__bases__:
                if PluginBaseModel in base.__bases__:
                    cls.registry.append(cls)
                    break

    @classmethod
    def load_plugins(cls) -> None:
        """
        Load additional plugin classes from plugin entry points and append to registry.

        Does nothing if plugin_category is empty.
        """
        if not cls.plugin_category:
            return

        # Discover plugin entry points for the configured category
        eps = entry_points(group=cls.entrypoint_namespace)
        for ep in eps:
            if ep.name != cls.plugin_category:
                continue

            # Load plugin classes and update registry
            loaded = ep.load()
            plugin_classes = loaded()
            for plugin_cls in plugin_classes:
                if plugin_cls not in cls.registry:
                    cls.registry.append(plugin_cls)
            break

    @classmethod
    def any(cls) -> Any:
        """
        Return an Annotated Union of registered plugin classes for
        Pydantic type discrimination.

        Returns:
            Any: Annotated Union of plugin classes with discriminator 'type'.
        """
        cls.load_plugins()

        if not cls.registry:
            msg = "Plugin registry is empty."
            raise RuntimeError(msg)

        # union_type = reduce(or_, cls.registry)
        # return Annotated[union_type, Field(discriminator="type")]

        return reduce(or_, cls.registry)
