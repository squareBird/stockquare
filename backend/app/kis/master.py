"""KIS master-file downloaders and parsers.

KIS publishes daily stock listings as zipped flat files on a public CDN
(``new.real.download.dws.co.kr``). We download the five files we care
about on startup — KOSPI + KOSDAQ for the Korean market, NASDAQ + NYSE
+ AMEX for the US market — and parse them into :class:`StockMasterRow`
tuples that feed the in-memory :class:`~app.services.stock_index.StockMasterIndex`.

The parsers are pure functions over raw zip bytes so they can be unit
tested without touching the network.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

import httpx

from app.models.stocks import StockMarket

_MASTER_BASE_URL = "https://new.real.download.dws.co.kr/common/master/"

_KOSPI_URL = f"{_MASTER_BASE_URL}kospi_code.mst.zip"
_KOSDAQ_URL = f"{_MASTER_BASE_URL}kosdaq_code.mst.zip"
_NASDAQ_URL = f"{_MASTER_BASE_URL}nasmst.cod.zip"
_NYSE_URL = f"{_MASTER_BASE_URL}nysmst.cod.zip"
_AMEX_URL = f"{_MASTER_BASE_URL}amsmst.cod.zip"

_KOSPI_SUFFIX_LEN = 228
_KOSDAQ_SUFFIX_LEN = 222

_KR_SYMBOL_PATTERN = re.compile(r"^\d{6}$")

# US master columns are tab-delimited — we need 9 columns (through the
# security-type flag at index 8).
_US_MIN_COLS = 9
_US_COMMON_STOCK_FLAG = "2"


@dataclass(frozen=True, slots=True)
class StockMasterRow:
    """One row extracted from a KIS master file.

    Attributes:
        symbol: Ticker (e.g. ``"005930"`` for KR, ``"AMZN"`` for US).
        name_ko: Korean company name. Empty string if not present in
            the source file (common for US rows).
        name_en: English company name. Empty string for KR rows — the
            KR master files do not publish an English name column.
        market: Canonical market identifier.
    """

    symbol: str
    name_ko: str
    name_en: str
    market: StockMarket


def _read_single_zip_entry(zip_bytes: bytes) -> str:
    """Decompress a single-file zip and return its CP949-decoded text."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        if not names:
            return ""
        with archive.open(names[0]) as fh:
            return fh.read().decode("cp949", errors="replace")


def parse_kr_master(
    zip_bytes: bytes,
    *,
    market: StockMarket,
    suffix_len: int,
) -> list[StockMasterRow]:
    """Parse a KOSPI / KOSDAQ master zip into rows.

    Args:
        zip_bytes: Raw bytes of the ``*_code.mst.zip`` archive.
        market: :class:`StockMarket.KOSPI` or :class:`StockMarket.KOSDAQ`.
        suffix_len: Number of trailing characters that belong to the
            fixed-width Part 2 layout. 228 for KOSPI, 222 for KOSDAQ.

    Returns:
        Zero or more rows in source order. Rows whose symbol is not a
        6-digit number are skipped.
    """
    text = _read_single_zip_entry(zip_bytes)
    if not text:
        return []

    # TODO(phase2): filter out halted / delisted rows using the
    # suspension-flag fields in Part 2. See STOCKS.md.
    rows: list[StockMasterRow] = []
    for raw_line in text.splitlines():
        if len(raw_line) <= suffix_len:
            continue
        symbol = raw_line[0:9].rstrip()
        if not _KR_SYMBOL_PATTERN.match(symbol):
            continue
        name_ko = raw_line[21 : len(raw_line) - suffix_len].strip()
        rows.append(
            StockMasterRow(
                symbol=symbol,
                name_ko=name_ko,
                name_en="",
                market=market,
            )
        )
    return rows


def parse_us_master(
    zip_bytes: bytes,
    *,
    market: StockMarket,
) -> list[StockMasterRow]:
    """Parse a NASDAQ / NYSE / AMEX master zip into rows.

    Args:
        zip_bytes: Raw bytes of the ``*mst.cod.zip`` archive.
        market: :class:`StockMarket.NASDAQ`, ``NYSE``, or ``AMEX``.

    Returns:
        Rows whose security-type flag identifies them as common stock
        (column 8 == ``"2"``). Everything else (warrants, preferred,
        ETFs with a different flag) is dropped.
    """
    text = _read_single_zip_entry(zip_bytes)
    if not text:
        return []

    rows: list[StockMasterRow] = []
    for raw_line in text.splitlines():
        cols = raw_line.split("\t")
        if len(cols) < _US_MIN_COLS:
            continue
        if cols[8] != _US_COMMON_STOCK_FLAG:
            continue
        symbol = cols[4].strip().upper()
        if not symbol:
            continue
        rows.append(
            StockMasterRow(
                symbol=symbol,
                name_ko=cols[6].strip(),
                name_en=cols[7].strip(),
                market=market,
            )
        )
    return rows


async def _download_kr(
    http: httpx.AsyncClient,
    url: str,
    market: StockMarket,
    suffix_len: int,
) -> list[StockMasterRow]:
    response = await http.get(url)
    response.raise_for_status()
    return parse_kr_master(response.content, market=market, suffix_len=suffix_len)


async def _download_us(
    http: httpx.AsyncClient,
    url: str,
    market: StockMarket,
) -> list[StockMasterRow]:
    response = await http.get(url)
    response.raise_for_status()
    return parse_us_master(response.content, market=market)


async def download_kospi(http: httpx.AsyncClient) -> list[StockMasterRow]:
    """Download and parse the KOSPI master file."""
    return await _download_kr(http, _KOSPI_URL, StockMarket.KOSPI, _KOSPI_SUFFIX_LEN)


async def download_kosdaq(http: httpx.AsyncClient) -> list[StockMasterRow]:
    """Download and parse the KOSDAQ master file."""
    return await _download_kr(http, _KOSDAQ_URL, StockMarket.KOSDAQ, _KOSDAQ_SUFFIX_LEN)


async def download_nasdaq(http: httpx.AsyncClient) -> list[StockMasterRow]:
    """Download and parse the NASDAQ master file."""
    return await _download_us(http, _NASDAQ_URL, StockMarket.NASDAQ)


async def download_nyse(http: httpx.AsyncClient) -> list[StockMasterRow]:
    """Download and parse the NYSE master file."""
    return await _download_us(http, _NYSE_URL, StockMarket.NYSE)


async def download_amex(http: httpx.AsyncClient) -> list[StockMasterRow]:
    """Download and parse the AMEX master file."""
    return await _download_us(http, _AMEX_URL, StockMarket.AMEX)
