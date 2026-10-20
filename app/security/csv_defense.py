"""
Security defense against CSV Formula Injection (CWE-1236 / Excel Macro Injection).
Neutralizes dangerous formula execution payloads when CSV exports are opened
in spreadsheet applications such as Microsoft Excel, LibreOffice Calc, or Google Sheets.
"""

DANGEROUS_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')
LEADING_STRIP_CHARS = ' \t\r\n\x00\x0b\x0c'


def sanitize_csv_cell(value):
    """
    Hardens CSV cells against Formula / Dynamic Data Exchange (DDE) Injection.

    Spreadsheet software strips leading whitespace/control characters before evaluating formulas.
    Therefore, payloads such as '   =cmd' or '\t+1' can trigger formula execution.
    This sanitizer detects formula prefixes even when hidden behind whitespace or control bytes
    and prepends a single quote (') to force spreadsheet software to treat the cell strictly as literal text.

    Preserves legitimate integer and floating-point numeric values where safe.
    """
    if value is None:
        return ""

    # Preserve genuine numeric primitives
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value

    str_val = str(value)
    if not str_val:
        return ""

    # Inspect the first effective character after stripping whitespace and control bytes
    effective_content = str_val.lstrip(LEADING_STRIP_CHARS)
    if effective_content and effective_content[0] in DANGEROUS_FORMULA_PREFIXES:
        return f"'{str_val}"

    # Also catch cases where str_val starts directly with raw tab or return
    if str_val[0] in ('\t', '\r'):
        return f"'{str_val}"

    return str_val

