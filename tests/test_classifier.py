"""Tests for cell classification."""

from aou_cost_engine.classifier import (
    CellType,
    ComputeTier,
    classify_cell,
    estimate_compute_tier,
    extract_sql,
)


class TestClassifyCell:
    def test_bigquery_magic(self):
        assert classify_cell("%%bigquery df\nSELECT * FROM person") == CellType.BIGQUERY

    def test_read_gbq(self):
        code = 'df = pd.read_gbq("SELECT person_id FROM person")'
        assert classify_cell(code) == CellType.BIGQUERY

    def test_client_query_with_sql(self):
        code = 'result = client.query("SELECT * FROM measurement WHERE person_id = 123")'
        assert classify_cell(code) == CellType.BIGQUERY

    def test_raw_sql_with_cdr(self):
        code = "SELECT person_id FROM condition_occurrence"
        assert classify_cell(code) == CellType.BIGQUERY

    def test_compute_high(self):
        code = "model.fit(X_train, y_train)"
        assert classify_cell(code) == CellType.COMPUTE

    def test_compute_medium(self):
        code = "df.groupby('category').mean()"
        assert classify_cell(code) == CellType.COMPUTE

    def test_compute_low(self):
        code = "df.plot(kind='bar')"
        assert classify_cell(code) == CellType.COMPUTE

    def test_io(self):
        code = 'df = pd.read_csv("data.csv")'
        assert classify_cell(code) == CellType.IO

    def test_unknown(self):
        code = "x = 42"
        assert classify_cell(code) == CellType.UNKNOWN

    def test_client_query_without_sql_keywords(self):
        code = "result = client.query(some_variable)"
        assert classify_cell(code) == CellType.UNKNOWN


class TestComputeTier:
    def test_high(self):
        assert estimate_compute_tier("model.fit(X, y)") == ComputeTier.HIGH

    def test_medium(self):
        assert estimate_compute_tier("df.groupby('a').sum()") == ComputeTier.MEDIUM

    def test_low(self):
        assert estimate_compute_tier("print(df.head())") == ComputeTier.LOW


class TestExtractSql:
    def test_bigquery_magic(self):
        code = "%%bigquery df\nSELECT person_id FROM person"
        sql = extract_sql(code)
        assert sql == "SELECT person_id FROM person"

    def test_triple_quoted_sql(self):
        code = '''sql = """SELECT person_id FROM measurement WHERE value > 100"""'''
        sql = extract_sql(code)
        assert sql is not None
        assert "SELECT" in sql

    def test_raw_sql(self):
        code = "SELECT * FROM person"
        sql = extract_sql(code)
        assert sql == "SELECT * FROM person"

    def test_no_sql(self):
        code = "x = 42\nprint(x)"
        sql = extract_sql(code)
        assert sql is None
