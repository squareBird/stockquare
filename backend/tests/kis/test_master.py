"""Tests for KIS master-file parsers."""

from __future__ import annotations

import io
import zipfile

from app.kis.master import parse_kr_master, parse_us_master
from app.models.stocks import StockMarket


def _zip(content: str, *, filename: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content.encode("cp949"))
    return buf.getvalue()


def _kr_line(symbol: str, name_ko: str, *, suffix_len: int) -> str:
    """Build a KOSPI/KOSDAQ master line in the documented layout."""
    symbol_field = symbol.ljust(9)  # row[0:9]
    isin_field = "X" * 12  # row[9:21]
    # Any non-empty suffix of the right length is fine for our parser.
    suffix = "Y" * suffix_len
    return f"{symbol_field}{isin_field}{name_ko}{suffix}"


def test_parse_kr_master_extracts_symbol_and_name() -> None:
    suffix_len = 228
    line = _kr_line("005930", "삼성전자", suffix_len=suffix_len)
    zip_bytes = _zip(line + "\n", filename="kospi_code.mst")

    rows = parse_kr_master(zip_bytes, market=StockMarket.KOSPI, suffix_len=suffix_len)

    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "005930"
    assert row.name_ko == "삼성전자"
    assert row.name_en == ""
    assert row.market == StockMarket.KOSPI


def test_parse_kr_master_skips_non_six_digit_rows() -> None:
    suffix_len = 228
    good = _kr_line("005930", "삼성전자", suffix_len=suffix_len)
    # Symbol field only 5 digits — should be skipped.
    bad = _kr_line("12345", "바뀐종목", suffix_len=suffix_len)
    # Contains letters — should be skipped.
    mixed = _kr_line("ABC123", "문자종목", suffix_len=suffix_len)
    content = "\n".join([good, bad, mixed]) + "\n"
    zip_bytes = _zip(content, filename="kospi_code.mst")

    rows = parse_kr_master(zip_bytes, market=StockMarket.KOSPI, suffix_len=suffix_len)

    assert [row.symbol for row in rows] == ["005930"]


def test_parse_us_master_filters_non_stock_security_type() -> None:
    common = "\t".join(["a", "b", "c", "d", "AMZN", "e", "아마존", "AMAZON.COM INC", "2"])
    warrant = "\t".join(["a", "b", "c", "d", "WRNT", "e", "", "SOME WARRANT", "4"])
    content = common + "\n" + warrant + "\n"
    zip_bytes = _zip(content, filename="nasmst.cod")

    rows = parse_us_master(zip_bytes, market=StockMarket.NASDAQ)

    assert len(rows) == 1
    assert rows[0].symbol == "AMZN"


def test_parse_us_master_extracts_symbol_name_ko_name_en() -> None:
    line = "\t".join(["a", "b", "c", "d", "amzn", "e", "아마존닷컴", "AMAZON.COM INC", "2"])
    zip_bytes = _zip(line + "\n", filename="nasmst.cod")

    rows = parse_us_master(zip_bytes, market=StockMarket.NASDAQ)

    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "AMZN"  # upper-cased
    assert row.name_ko == "아마존닷컴"
    assert row.name_en == "AMAZON.COM INC"
    assert row.market == StockMarket.NASDAQ
