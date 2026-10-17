import zipfile

import pandas as pd
import pytest

from swing_engine.research import premise_library as pl


def test_month_parsing_and_mean_t():
    assert pl._month("07/31/1957") == "1957-07" and pl._month("31077") == "1985-01" and pl._month("DATE") is None
    m, t, n = pl.mean_t(pd.Series([0.01, 0.03] * 12))
    assert (m, n) == (pytest.approx(0.24), 24) and t > 0


def test_xlsx_reader_finds_header_and_drops_blank_dates(tmp_path):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    cell = lambda ref, v: f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'  # noqa: E731
    rows = [["note", ""], ["DATE", "USA"], ["01/31/2000", "0.01"], ["02/29/2000", "-0.02"], ["", ""]]
    body = "".join(f'<row r="{i + 1}">' + "".join(cell(f"{c}{i + 1}", v) for c, v in zip("AB", r, strict=True) if v)
                   + "</row>" for i, r in enumerate(rows))
    path = tmp_path / "f.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rel}><sheets><sheet name="F" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData>{body}</sheetData></worksheet>")
    df = pl.aqr_sheet(path, "F")
    assert list(df.index) == ["2000-01", "2000-02"] and df["USA"].tolist() == [0.01, -0.02]
