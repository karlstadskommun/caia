"""Deterministic emission-calculation engine for CAIA."""
from .engine import activity_changes, compute, render_activity, render_appendix, render_markdown
from .schema import CalcModel, Driver, Ramp, Triple

__all__ = ["activity_changes", "compute", "render_activity", "render_appendix", "render_markdown", "CalcModel", "Driver", "Ramp", "Triple"]
