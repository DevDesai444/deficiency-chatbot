"""Reconstruction is pure geometry, so it is tested with synthetic OCR regions --
no Databricks endpoint required. The regions below mimic the diluent peak table on
page 38 of the validation report, the case the old flat-text OCR mangled worst.
"""
from parse.layout import OCRRegion, reconstruct_page


def _cell(text, x_center, y, half_width=18.0, height=12.0):
    """A region centred at (x_center, y) -- how a single OCR'd cell looks."""
    return OCRRegion(
        text=text,
        x0=x_center - half_width,
        y0=y,
        x1=x_center + half_width,
        y1=y + height,
        score=0.99,
    )


# Six columns, centred at these x positions, well beyond the column-gap threshold.
COLS = {"name": 40, "rt": 130, "area": 190, "pct": 250, "int": 310, "res": 380}


def _peak_table_regions():
    regions = []
    # A prose caption above the table (two fragments -> must be re-joined with a space).
    regions.append(_cell("Typical chromatogram", 120, 40, half_width=90))
    regions.append(_cell("of Diluent", 330, 40, half_width=60))
    # Header row -- all six columns present.
    header_y = 100
    regions.append(_cell("Peak Name", COLS["name"], header_y))
    regions.append(_cell("RT", COLS["rt"], header_y))
    regions.append(_cell("Area", COLS["area"], header_y))
    regions.append(_cell("% Area", COLS["pct"], header_y))
    regions.append(_cell("Int Type", COLS["int"], header_y))
    regions.append(_cell("USP Resolution", COLS["res"], header_y, half_width=40))
    # Row 1 -- NO resolution cell. The old flat OCR dropped it and shifted the rest.
    regions.append(_cell("1", COLS["name"], 130))
    regions.append(_cell("0.1", COLS["rt"], 130))
    regions.append(_cell("201", COLS["area"], 130))
    regions.append(_cell("1.2", COLS["pct"], 130))
    regions.append(_cell("BB", COLS["int"], 130))
    # Row 2 -- all six columns present.
    regions.append(_cell("2", COLS["name"], 160))
    regions.append(_cell("2.1", COLS["rt"], 160))
    regions.append(_cell("13439", COLS["area"], 160))
    regions.append(_cell("80.0", COLS["pct"], 160))
    regions.append(_cell("BB", COLS["int"], 160))
    regions.append(_cell("3.6", COLS["res"], 160))
    return regions


def test_prose_line_spaces_restored():
    text, _ = reconstruct_page(_peak_table_regions(), page_number=38)
    assert "Typical chromatogram of Diluent" in text


def test_table_detected_with_all_columns():
    _, tables = reconstruct_page(_peak_table_regions(), page_number=38)
    assert len(tables) == 1
    table = tables[0]
    assert table.page == 38
    assert len(table.headers) == 6
    assert "USP Resolution" in table.headers


def test_missing_cell_stays_empty_not_shifted():
    _, tables = reconstruct_page(_peak_table_regions(), page_number=38)
    rows = tables[0].rows
    assert len(rows) == 2

    # Row 1 is missing its resolution value: BB must stay in the Int Type column and
    # the resolution column must be blank -- not "BB" shifted one place to the right.
    row1 = rows[0]
    assert row1 == ["1", "0.1", "201", "1.2", "BB", ""]

    # Row 2 has every cell, in order.
    assert rows[1] == ["2", "2.1", "13439", "80.0", "BB", "3.6"]


def test_table_title_comes_from_preceding_prose():
    _, tables = reconstruct_page(_peak_table_regions(), page_number=38)
    assert tables[0].title == "Typical chromatogram of Diluent"


def test_empty_input_is_safe():
    assert reconstruct_page([], page_number=1) == ("", [])
    blanks = [OCRRegion(text="   ", x0=0, y0=0, x1=5, y1=5)]
    assert reconstruct_page(blanks, page_number=1) == ("", [])
