"""
CTD Cast Processor — Automated quality control and parameter derivation for oceanographic CTD data.

Main exports:
- CTDProfile: Core class for reading, processing, and exporting CTD casts
- QCReport: Data quality assessment report
"""

__version__ = "1.0.0"
__author__ = "Ranjith Guggilla"

from ctd_processor.core import CTDProfile
from ctd_processor.qc import QCReport

__all__ = ["CTDProfile", "QCReport"]
