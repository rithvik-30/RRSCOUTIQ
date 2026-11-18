"""
RR ScoutIQ - M5.4 Full-scale Data Quality & Cricket Validation Engine.
This package provides comprehensive validation routines and anomaly registries
for the enriched delivery dataset and reconstructed pre-delivery match-state dataset.
"""

from .data_quality_validator import DataQualityValidator, ValidationResult

__all__ = ["DataQualityValidator", "ValidationResult"]
