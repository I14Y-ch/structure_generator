"""
CSV Import wrapper for SHACL Creator
Provides a convenient interface to the CSV to SHACL conversion functionality
"""

try:
    from ..csv_converter import CSVToSHACL, csv_to_ttl
except ImportError:
    from csv_converter import CSVToSHACL, csv_to_ttl

__all__ = ['CSVToSHACL', 'csv_to_ttl']
