"""
UR Pick and Place Package

ROS2 package for pick and place operations with UR robots.
Includes simulated parallel gripper and industrial table scene.

Note: Imports are lazy to avoid requiring all dependencies for each module.
"""

__all__ = [
    'PickPlaceNode',
    'GripperController',
    'SceneObjectManager',
]

__version__ = '1.0.0'


def __getattr__(name):
    """Lazy import for modules to avoid dependency issues."""
    if name == 'PickPlaceNode':
        from .pick_place_node import PickPlaceNode
        return PickPlaceNode
    elif name == 'GripperController':
        from .gripper_controller import GripperController
        return GripperController
    elif name == 'SceneObjectManager':
        from .scene_objects import SceneObjectManager
        return SceneObjectManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
