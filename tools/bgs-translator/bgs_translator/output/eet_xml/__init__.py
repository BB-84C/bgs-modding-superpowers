"""ESP-ESM Translator XML output package for Morrowind dictionaries."""

from .reader import EETXMLEntry, read_eet_xml
from .writer import write_eet_xml

__all__ = ["EETXMLEntry", "read_eet_xml", "write_eet_xml"]
