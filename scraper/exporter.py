"""
Data Exporter Module
Exports cleaned business data to Excel (.xlsx) and CSV (.csv) files.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


class DataExporter:
    """Exports business data to Excel and CSV formats."""

    COLUMNS = ['Name', 'Phone', 'Email', 'Website', 'Services', 'Rendez-vous', 'Address', 'City', 'Category']
    EXTENDED_COLUMNS = ['Name', 'Phone', 'Email', 'Website', 'Services', 'Rendez-vous', 'Address', 'City', 'Category', 'Latitude', 'Longitude', 'Source']

    FIELD_MAP = {
        'Name': 'name',
        'Phone': 'phone',
        'Email': 'email',
        'Website': 'website',
        'Services': 'services',
        'Rendez-vous': 'booking',
        'Address': 'address',
        'City': 'city',
        'Category': 'category',
        'Latitude': 'latitude',
        'Longitude': 'longitude',
        'Source': 'source',
    }

    def __init__(self, output_dir: str = 'output'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _prepare_dataframe(self, data: List[Dict], include_extended: bool = True) -> pd.DataFrame:
        """Convert business data to a pandas DataFrame."""
        columns = self.EXTENDED_COLUMNS if include_extended else self.COLUMNS

        rows = []
        for record in data:
            row = {}
            for col in columns:
                field = self.FIELD_MAP.get(col, col.lower())
                row[col] = record.get(field, '')
            rows.append(row)

        df = pd.DataFrame(rows, columns=columns)

        # Sort by city, then category, then name
        df = df.sort_values(by=['City', 'Category', 'Name'], ignore_index=True)

        return df

    def export_csv(self, data: List[Dict], filename: str = None, city: str = "") -> str:
        """
        Export data to CSV file.

        Args:
            data: List of business data dictionaries
            filename: Optional custom filename
            city: City name for the filename

        Returns:
            Path to the created CSV file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            city_slug = city.lower().replace(' ', '_') if city else 'morocco'
            filename = f"businesses_{city_slug}_{timestamp}.csv"

        filepath = os.path.join(self.output_dir, filename)

        df = self._prepare_dataframe(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')

        logger.info(f"CSV exported: {filepath} ({len(data)} records)")
        return filepath

    def export_excel(self, data: List[Dict], filename: str = None, city: str = "") -> str:
        """
        Export data to styled Excel file.

        Args:
            data: List of business data dictionaries
            filename: Optional custom filename
            city: City name for the filename

        Returns:
            Path to the created Excel file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            city_slug = city.lower().replace(' ', '_') if city else 'morocco'
            filename = f"businesses_{city_slug}_{timestamp}.xlsx"

        filepath = os.path.join(self.output_dir, filename)

        df = self._prepare_dataframe(data)

        # Create styled workbook
        wb = Workbook()
        ws = wb.active
        ws.title = f"Businesses - {city.title() if city else 'Morocco'}"

        # Define styles
        header_font = Font(name='Calibri', bold=True, size=12, color='FFFFFF')
        header_fill = PatternFill(start_color='1B4F72', end_color='1B4F72', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        data_font = Font(name='Calibri', size=11)
        data_alignment = Alignment(vertical='center', wrap_text=True)

        alt_fill = PatternFill(start_color='EBF5FB', end_color='EBF5FB', fill_type='solid')

        thin_border = Border(
            left=Side(style='thin', color='D5D8DC'),
            right=Side(style='thin', color='D5D8DC'),
            top=Side(style='thin', color='D5D8DC'),
            bottom=Side(style='thin', color='D5D8DC')
        )

        # Title row
        ws.merge_cells(f'A1:{get_column_letter(len(df.columns))}1')
        title_cell = ws.cell(row=1, column=1)
        title_cell.value = f"📊 Morocco Business Data - {city.title() if city else 'All Cities'}"
        title_cell.font = Font(name='Calibri', bold=True, size=16, color='1B4F72')
        title_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 40

        # Subtitle row
        ws.merge_cells(f'A2:{get_column_letter(len(df.columns))}2')
        subtitle_cell = ws.cell(row=2, column=1)
        subtitle_cell.value = f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')} | Total Records: {len(data)}"
        subtitle_cell.font = Font(name='Calibri', size=10, italic=True, color='566573')
        subtitle_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 25

        # Empty row
        ws.row_dimensions[3].height = 10

        # Header row (row 4)
        header_row = 4
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.value = col_name
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        ws.row_dimensions[header_row].height = 30

        # Data rows
        for row_idx, (_, row_data) in enumerate(df.iterrows(), header_row + 1):
            for col_idx, col_name in enumerate(df.columns, 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                value = row_data[col_name]
                cell.value = value if pd.notna(value) else ''
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = thin_border

                # Make URLs clickable
                if col_name in ['Website', 'Services', 'Rendez-vous'] and value and pd.notna(value) and str(value).startswith('http'):
                    cell.hyperlink = str(value)
                    cell.font = Font(name='Calibri', size=11, color='2980B9', underline='single')

                # Make emails clickable
                if col_name == 'Email' and value and pd.notna(value) and '@' in str(value):
                    cell.hyperlink = f"mailto:{value}"
                    cell.font = Font(name='Calibri', size=11, color='2980B9', underline='single')

                # Make phone numbers styled
                if col_name == 'Phone' and value and pd.notna(value):
                    cell.font = Font(name='Calibri', size=11, color='1A5276')

            # Alternating row colors
            if row_idx % 2 == 0:
                for col_idx in range(1, len(df.columns) + 1):
                    ws.cell(row=row_idx, column=col_idx).fill = alt_fill

        # Auto-adjust column widths
        column_widths = {
            'Name': 35,
            'Phone': 22,
            'Email': 30,
            'Website': 35,
            'Services': 35,
            'Rendez-vous': 35,
            'Address': 40,
            'City': 18,
            'Category': 22,
            'Latitude': 15,
            'Longitude': 15,
            'Source': 20,
        }

        for col_idx, col_name in enumerate(df.columns, 1):
            width = column_widths.get(col_name, 20)
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Freeze header row
        ws.freeze_panes = f'A{header_row + 1}'

        # Add auto-filter
        ws.auto_filter.ref = f'A{header_row}:{get_column_letter(len(df.columns))}{header_row + len(df)}'

        # Save workbook
        wb.save(filepath)

        logger.info(f"Excel exported: {filepath} ({len(data)} records)")
        return filepath

    def export_by_category(self, data: List[Dict], city: str = "") -> Dict[str, Dict[str, str]]:
        """
        Export separate files per category.

        Args:
            data: List of business data
            city: City name

        Returns:
            Dictionary mapping category to file paths {category: {csv: path, xlsx: path}}
        """
        # Group by category
        categories = {}
        for record in data:
            cat = record.get('category', 'uncategorized') or 'uncategorized'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(record)

        exports = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        city_slug = city.lower().replace(' ', '_') if city else 'morocco'

        for cat, records in categories.items():
            cat_slug = cat.lower().replace(' ', '_').replace('/', '_')

            csv_name = f"businesses_{city_slug}_{cat_slug}_{timestamp}.csv"
            xlsx_name = f"businesses_{city_slug}_{cat_slug}_{timestamp}.xlsx"

            csv_path = self.export_csv(records, csv_name, city)
            xlsx_path = self.export_excel(records, xlsx_name, city)

            exports[cat] = {'csv': csv_path, 'xlsx': xlsx_path, 'count': len(records)}

        return exports

    def export_all(self, data: List[Dict], city: str = "") -> Dict[str, str]:
        """
        Export data in both CSV and Excel formats.

        Args:
            data: List of business data
            city: City name

        Returns:
            Dictionary with file paths {csv: path, xlsx: path}
        """
        csv_path = self.export_csv(data, city=city)
        xlsx_path = self.export_excel(data, city=city)

        return {
            'csv': csv_path,
            'xlsx': xlsx_path,
            'count': len(data)
        }
