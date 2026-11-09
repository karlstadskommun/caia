"""Deterministic emission-calculation engine for CAIA."""
from .engine import compute, render_appendix, render_markdown
from .schema import CalcModel, Driver, Ramp, Triple

__all__ = ["compute", "render_appendix", "render_markdown", "CalcModel", "Driver", "Ramp", "Triple"]
