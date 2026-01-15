"""
Streaming XML parser for large files.

Uses lxml.etree.iterparse() to process XML files without loading
the entire document into memory. Essential for Apple Health exports
which can exceed 1GB.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from pathlib import Path
from typing import Iterator, Dict, Any, Optional, Callable, List
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class StreamingXMLParser:
    """
    Memory-efficient XML parser using iterparse.

    Processes XML files element by element, clearing each element
    after processing to maintain constant memory usage.

    Usage:
        parser = StreamingXMLParser()

        # Process all elements of a specific tag
        for record in parser.iter_elements(path, tag='Record'):
            process(record)

        # Or use a callback
        def handler(attrib, text):
            print(attrib.get('type'))

        parser.process_file(path, tag='Record', callback=handler)
    """

    def __init__(self, max_records: Optional[int] = None):
        """
        Initialize streaming parser.

        Args:
            max_records: Maximum records to process (None for unlimited)
        """
        self.max_records = max_records
        self._lxml_available = None

    @property
    def lxml_available(self) -> bool:
        """Check if lxml is available."""
        if self._lxml_available is None:
            try:
                from lxml import etree
                self._lxml_available = True
            except ImportError:
                self._lxml_available = False
                logger.warning(
                    "lxml not installed. Install with: pip install lxml"
                )
        return self._lxml_available

    def iter_elements(
        self,
        file_path: Path,
        tag: str,
        namespaces: Optional[Dict[str, str]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Iterate over elements matching tag, yielding dict for each.

        Clears each element after yielding to prevent memory buildup.

        Args:
            file_path: Path to XML file
            tag: Element tag to match (e.g., 'Record', 'Entry')
            namespaces: Optional namespace mapping

        Yields:
            Dict with 'attrib' (attributes) and 'text' (content)
        """
        if not self.lxml_available:
            logger.error("lxml required for streaming XML parsing")
            return

        from lxml import etree

        count = 0
        context = etree.iterparse(
            str(file_path),
            events=('end',),
            tag=tag
        )

        for event, elem in context:
            yield {
                'attrib': dict(elem.attrib),
                'text': elem.text,
                'children': [
                    {'tag': child.tag, 'attrib': dict(child.attrib), 'text': child.text}
                    for child in elem
                ]
            }

            # Clear element to free memory
            elem.clear()

            # Also clear preceding siblings (important for large files)
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            count += 1
            if self.max_records and count >= self.max_records:
                break

        # Clean up
        del context

    def process_file(
        self,
        file_path: Path,
        tag: str,
        callback: Callable[[Dict[str, str], Optional[str]], None],
        namespaces: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Process file with callback for each matching element.

        Args:
            file_path: Path to XML file
            tag: Element tag to match
            callback: Function(attrib_dict, text) called for each element
            namespaces: Optional namespace mapping

        Returns:
            Number of elements processed
        """
        count = 0
        for elem_data in self.iter_elements(file_path, tag, namespaces):
            callback(elem_data['attrib'], elem_data['text'])
            count += 1
        return count

    def get_summary(
        self,
        file_path: Path,
        tag: str,
        group_by: str = 'type',
        limit: int = 10000
    ) -> Dict[str, Any]:
        """
        Get summary statistics for elements without full processing.

        Args:
            file_path: Path to XML file
            tag: Element tag to match
            group_by: Attribute to group by
            limit: Maximum elements to scan

        Returns:
            Dict with counts, unique values, and sample data
        """
        counts = defaultdict(int)
        total = 0
        sample_values: List[Dict] = []

        old_max = self.max_records
        self.max_records = limit

        try:
            for elem_data in self.iter_elements(file_path, tag):
                total += 1
                attrib = elem_data['attrib']

                group_value = attrib.get(group_by, 'unknown')
                counts[group_value] += 1

                # Keep sample of first 10
                if len(sample_values) < 10:
                    sample_values.append(attrib)

        finally:
            self.max_records = old_max

        return {
            'total_scanned': total,
            'limit_reached': total >= limit,
            f'by_{group_by}': dict(counts),
            'unique_values': len(counts),
            'sample': sample_values,
        }


class AppleHealthParser:
    """
    Specialized parser for Apple Health export.xml files.

    Apple Health exports can be 1GB+ with millions of records.
    This parser streams the data without loading it all into memory.
    """

    # Common Apple Health record types
    RECORD_TYPES = {
        'HKQuantityTypeIdentifierStepCount': 'steps',
        'HKQuantityTypeIdentifierHeartRate': 'heart_rate',
        'HKQuantityTypeIdentifierActiveEnergyBurned': 'active_energy',
        'HKQuantityTypeIdentifierDistanceWalkingRunning': 'distance',
        'HKQuantityTypeIdentifierFlightsClimbed': 'flights',
        'HKCategoryTypeIdentifierSleepAnalysis': 'sleep',
        'HKQuantityTypeIdentifierBodyMass': 'weight',
        'HKQuantityTypeIdentifierHeight': 'height',
    }

    def __init__(self, max_records: int = 100000):
        self.xml_parser = StreamingXMLParser(max_records=max_records)

    def parse(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse Apple Health export.xml file.

        Args:
            file_path: Path to export.xml

        Returns:
            Dict with summary stats and sample data
        """
        if not self.xml_parser.lxml_available:
            return {
                'error': 'lxml_not_installed',
                'message': 'Install lxml for Apple Health parsing: pip install lxml'
            }

        # Get summary of Record elements
        summary = self.xml_parser.get_summary(
            file_path,
            tag='Record',
            group_by='type',
            limit=100000
        )

        # Translate type identifiers to friendly names
        friendly_counts = {}
        for type_id, count in summary.get('by_type', {}).items():
            friendly_name = self.RECORD_TYPES.get(type_id, type_id)
            friendly_counts[friendly_name] = count

        return {
            'total_records_scanned': summary['total_scanned'],
            'record_types': friendly_counts,
            'unique_record_types': summary['unique_values'],
            'sample_records': summary['sample'][:5],
            'truncated': summary['limit_reached'],
        }

    def iter_records(
        self,
        file_path: Path,
        record_type: Optional[str] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Iterate over health records.

        Args:
            file_path: Path to export.xml
            record_type: Optional filter by type (e.g., 'steps', 'heart_rate')

        Yields:
            Dict with record data
        """
        # Convert friendly name to identifier if needed
        type_filter = None
        if record_type:
            for type_id, friendly in self.RECORD_TYPES.items():
                if friendly == record_type:
                    type_filter = type_id
                    break
            if type_filter is None:
                type_filter = record_type  # Use as-is if not found

        for elem_data in self.xml_parser.iter_elements(file_path, 'Record'):
            attrib = elem_data['attrib']

            # Filter by type if specified
            if type_filter and attrib.get('type') != type_filter:
                continue

            yield {
                'type': self.RECORD_TYPES.get(attrib.get('type', ''), attrib.get('type', '')),
                'value': attrib.get('value'),
                'unit': attrib.get('unit'),
                'source': attrib.get('sourceName'),
                'start_date': attrib.get('startDate'),
                'end_date': attrib.get('endDate'),
            }


__all__ = [
    'StreamingXMLParser',
    'AppleHealthParser',
]
