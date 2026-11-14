"""Bower procedural design system.

`centreline` and `member` are pure Python (no bpy) so they run in tests and
exporters as well as inside Blender. `blender_scene` is the only module that
touches the Blender scene. Units are metres; axes are Z up, Y north.
"""
