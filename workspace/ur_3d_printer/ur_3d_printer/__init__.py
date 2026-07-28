# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
UR 3D Printer Package

ROS2 package that turns UR robot arms into 3D printers by parsing G-code,
converting toolpaths to joint trajectories via IK, and controlling an extruder.

Note: Imports are lazy to avoid requiring all dependencies for each module.
"""

__all__ = [
    'GCodeParser',
    'Toolpath',
    'Layer',
    'Waypoint',
    'TrajectoryPlanner',
    'VelocityProfiler',
    'ExtruderControllerNode',
    'PrintNode',
    'ToolpathVisualizer',
    'WorkspaceValidator',
    'SelfCollisionChecker',
    'MultiAxisToolpathGenerator',
    'MultiAxisConfig',
    'DepositionVisualizer',
    'Pattern',
    'generate_infill',
    'line_spacing_from_density',
    'OverhangConfig',
    'OverhangReport',
    'FaceOverhang',
    'analyze_overhangs',
    'analyze_stl_overhangs',
    'SegmentationConfig',
    'SegmentationResult',
    'BuildSegment',
    'segment_by_build_direction',
    'segment_stl_by_build_direction',
]

__version__ = '1.0.0'


def __getattr__(name):
    """Lazy import for modules to avoid dependency issues."""
    if name == 'GCodeParser':
        from .gcode_parser import GCodeParser
        return GCodeParser
    elif name in ('Toolpath', 'Layer', 'Waypoint'):
        from . import toolpath
        return getattr(toolpath, name)
    elif name == 'TrajectoryPlanner':
        from .trajectory_planner import TrajectoryPlanner
        return TrajectoryPlanner
    elif name == 'VelocityProfiler':
        from .velocity_profiler import VelocityProfiler
        return VelocityProfiler
    elif name == 'ExtruderControllerNode':
        from .extruder_controller import ExtruderControllerNode
        return ExtruderControllerNode
    elif name == 'PrintNode':
        from .print_node import PrintNode
        return PrintNode
    elif name == 'ToolpathVisualizer':
        from .toolpath_visualizer import ToolpathVisualizer
        return ToolpathVisualizer
    elif name == 'WorkspaceValidator':
        from .workspace_validator import WorkspaceValidator
        return WorkspaceValidator
    elif name == 'SelfCollisionChecker':
        from .collision_checker import SelfCollisionChecker
        return SelfCollisionChecker
    elif name in ('MultiAxisToolpathGenerator', 'MultiAxisConfig'):
        from . import multiaxis_planner
        return getattr(multiaxis_planner, name)
    elif name == 'DepositionVisualizer':
        from .deposition_visualizer import DepositionVisualizer
        return DepositionVisualizer
    elif name in ('Pattern', 'generate_infill', 'line_spacing_from_density'):
        from . import infill
        return getattr(infill, name)
    elif name in (
        'OverhangConfig', 'OverhangReport', 'FaceOverhang',
        'analyze_overhangs', 'analyze_stl_overhangs',
    ):
        from . import overhang_analyzer
        return getattr(overhang_analyzer, name)
    elif name in (
        'SegmentationConfig', 'SegmentationResult', 'BuildSegment',
        'segment_by_build_direction', 'segment_stl_by_build_direction',
    ):
        from . import build_segmentation
        return getattr(build_segmentation, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
