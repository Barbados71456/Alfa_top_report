"""Экспорт отчётов в Excel. build_workbook(sheets) берёт уже посчитанные для рендера
данные (те же, что уходят в шаблон) и разворачивает их в .xlsx — без повторных запросов
к БД. Конкретное разворачивание rows->(headers, rows) живёт в export_rows() каждого
отчётного модуля (pl_report.py, fot_report.py, loans_report.py, investment_report.py)."""
from io import BytesIO

from openpyxl import Workbook


def build_workbook(sheets):
    """sheets: [(sheet_name, headers, rows), ...] -> BytesIO(.xlsx)"""
    wb = Workbook()
    wb.remove(wb.active)
    for name, headers, rows in sheets:
        ws = wb.create_sheet(name[:31])
        ws.append(headers)
        for row in rows:
            ws.append([_cell_safe(v) for v in row])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _cell_safe(v):
    """openpyxl не пишет кортежи/списки/словари в ячейку — приводим к строке."""
    if isinstance(v, (list, tuple, dict)):
        return str(v)
    return v


def flatten_rows(rows, val_fields):
    """rows: [{'label':, val_field: [..] или число, ...}, ...] -> [[label, *значения], ...].
    Используется свод-таблицами (Свод1/2, UNIT+PL, Dashboard1/2, ФОТ) — каждая строка уже
    содержит один или несколько списков значений по месяцам/сериям плюс, опционально,
    скалярные поля (например endpoint_delta на UNIT+PL)."""
    out = []
    for r in rows:
        row_out = [r.get('label', '')]
        for field in val_fields:
            v = r.get(field)
            if v is None:
                continue
            if isinstance(v, (list, tuple)):
                row_out.extend(v)
            else:
                row_out.append(v)
        out.append(row_out)
    return out
