from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common import n2_theory_db as database


E6_SCFT = {
    "algebra": "E6",
    "hypermultiplets": [
        {"representation": "fundamental", "number": 4}
    ],
}

A1_PRODUCT_SCFT = {
    "gauge_groups": [
        {"id": "left", "algebra": "A1"},
        {"id": "right", "algebra": "A1"},
    ],
    "hypermultiplets": [
        {
            "representations": {
                "left": "fundamental",
                "right": "fundamental",
            },
            "number": 2,
        }
    ],
}


class _RecordingCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = None
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, parameters=()):
        normalized = " ".join(statement.split())
        self.connection.statements.append((normalized, parameters))
        if normalized.startswith("SELECT"):
            self._row = (
                self.connection.select_rows.pop(0)
                if self.connection.select_rows
                else None
            )
        if normalized.startswith("INSERT"):
            self.lastrowid = self.connection.next_id
            self.connection.next_id += 1
        return 1

    def fetchone(self):
        return self._row


class _RecordingConnection:
    def __init__(self, select_rows=None):
        self.statements = []
        self.select_rows = list(select_rows or [])
        self.next_id = 1

    def cursor(self, cursor=None):
        return _RecordingCursor(self)


class TheoryDatabaseUnitTests(unittest.TestCase):
    def test_schema_uses_mysql_types_and_innodb(self):
        self.assertIn("AUTO_INCREMENT", database.SCHEMA_SQL)
        self.assertIn("ENGINE=InnoDB", database.SCHEMA_SQL)
        self.assertIn("input_json JSON NOT NULL", database.SCHEMA_SQL)
        self.assertIn(
            "central_charge_a_decimal DECIMAL(65, 30)",
            database.SCHEMA_SQL,
        )
        self.assertIn(
            "central_charge_c_decimal DECIMAL(65, 30)",
            database.SCHEMA_SQL,
        )
        self.assertIn("GENERATED ALWAYS AS", database.SCHEMA_SQL)
        self.assertIn(
            "idx_theory_properties_central_charge_a",
            database.SCHEMA_SQL,
        )
        self.assertNotIn("AUTOINCREMENT", database.SCHEMA_SQL)
        self.assertNotIn("CREATE INDEX IF NOT EXISTS", database.SCHEMA_SQL)

    def test_initialize_database_executes_schema_and_records_version(self):
        connection = _RecordingConnection()

        database.initialize_database(connection)

        statements = [statement for statement, _ in connection.statements]
        self.assertTrue(
            any(
                statement.startswith("CREATE TABLE")
                for statement in statements
            )
        )
        self.assertTrue(
            any(
                "INSERT INTO schema_metadata" in statement
                for statement in statements
            )
        )
        metadata_parameters = next(
            parameters
            for statement, parameters in connection.statements
            if "INSERT INTO schema_metadata" in statement
        )
        self.assertEqual(metadata_parameters, ("schema_version", "2"))

    def test_initialize_database_migrates_version_one_schema(self):
        connection = _RecordingConnection(
            select_rows=[{"metadata_value": "1"}]
        )

        database.initialize_database(connection)

        migration = next(
            statement
            for statement, _ in connection.statements
            if statement.startswith("ALTER TABLE theory_properties")
        )
        self.assertIn("central_charge_a_decimal", migration)
        self.assertIn("central_charge_c_decimal", migration)
        metadata_parameters = next(
            parameters
            for statement, parameters in connection.statements
            if statement.startswith("UPDATE schema_metadata")
        )
        self.assertEqual(metadata_parameters, ("2", "schema_version"))

    def test_connect_database_uses_pymysql_options(self):
        connection = MagicMock()
        with (
            patch.object(
                database.pymysql, "connect", return_value=connection
            ) as connect,
            patch.object(database, "initialize_database") as initialize,
        ):
            result = database.connect_database(
                "n2_test",
                host="mysql.example",
                port=3307,
                user="researcher",
                password="secret",
                connect_timeout=4,
            )

        self.assertIs(result, connection)
        connect.assert_called_once_with(
            host="mysql.example",
            port=3307,
            user="researcher",
            password="secret",
            database="n2_test",
            unix_socket=None,
            charset="utf8mb4",
            cursorclass=database.DictCursor,
            autocommit=True,
            connect_timeout=4,
        )
        initialize.assert_called_once_with(connection)

    def test_realization_inserts_use_mysql_parameters(self):
        anomaly_result, properties = database._checked_results(E6_SCFT)
        connection = _RecordingConnection()

        realization_id = database._insert_realization(
            connection,
            theory_id=7,
            canonical_hash="a" * 64,
            data=E6_SCFT,
            anomaly_result=anomaly_result,
            properties=properties,
        )

        self.assertEqual(realization_id, 1)
        insert_statements = [
            (statement, parameters)
            for statement, parameters in connection.statements
            if statement.startswith("INSERT")
        ]
        self.assertEqual(len(insert_statements), 5)
        self.assertTrue(
            all("?" not in statement for statement, _ in insert_statements)
        )
        self.assertTrue(
            all("%s" in statement for statement, _ in insert_statements)
        )
        gauge_parameters = next(
            parameters
            for statement, parameters in insert_statements
            if "INSERT INTO gauge_factors" in statement
        )
        self.assertEqual(gauge_parameters[5], 6)
        self.assertEqual(gauge_parameters[10:12], (0, 1))

    def test_product_realization_inserts_every_factor_relation(self):
        anomaly_result, properties = database._checked_results(
            A1_PRODUCT_SCFT
        )
        connection = _RecordingConnection()

        database._insert_realization(
            connection,
            theory_id=9,
            canonical_hash="b" * 64,
            data=A1_PRODUCT_SCFT,
            anomaly_result=anomaly_result,
            properties=properties,
        )

        statements = [
            statement for statement, _ in connection.statements
        ]
        self.assertEqual(
            sum("INSERT INTO gauge_factors" in item for item in statements),
            2,
        )
        self.assertEqual(
            sum(
                "INSERT INTO hypermultiplet_representations" in item
                for item in statements
            ),
            2,
        )
        self.assertEqual(
            sum(
                "INSERT INTO exactly_marginal_couplings" in item
                for item in statements
            ),
            2,
        )

    def test_existing_mysql_json_properties_compare_structurally(self):
        _, properties = database._checked_results(E6_SCFT)
        stored_json = json.dumps(
            json.loads(
                database._json_text(
                    database._shared_properties(properties), canonical=True
                )
            ),
            indent=2,
        )
        connection = _RecordingConnection(
            select_rows=[{"properties_json": stored_json}]
        )

        database._insert_shared_properties(
            connection, theory_id=3, properties=properties
        )

        self.assertEqual(len(connection.statements), 1)
        self.assertTrue(connection.statements[0][0].startswith("SELECT"))

    def test_shared_properties_store_exact_central_charge_fractions(self):
        _, properties = database._checked_results(E6_SCFT)
        connection = _RecordingConnection()

        database._insert_shared_properties(
            connection, theory_id=3, properties=properties
        )

        _, parameters = next(
            item
            for item in connection.statements
            if item[0].startswith("INSERT INTO theory_properties")
        )
        expected = {
            "a": {"numerator": 83, "denominator": 4},
            "c": {"numerator": 22, "denominator": 1},
        }
        self.assertEqual(json.loads(parameters[5]), expected)
        self.assertEqual(
            json.loads(parameters[8])["central_charges"], expected
        )

    def test_store_commits_successful_transaction(self):
        connection = MagicMock()
        with (
            patch.object(database, "initialize_database"),
            patch.object(
                database,
                "_fetchone",
                side_effect=[None, {"name": "E6 test"}],
            ),
            patch.object(database, "_insert_theory", return_value=11),
            patch.object(database, "_insert_shared_properties"),
            patch.object(database, "_insert_realization", return_value=12),
            patch.object(database, "_execute"),
        ):
            stored = database.store_lagrangian_theory(
                connection, E6_SCFT, name="E6 test"
            )

        self.assertEqual(stored.theory_id, 11)
        self.assertEqual(stored.lagrangian_realization_id, 12)
        connection.begin.assert_called_once_with()
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()

    def test_store_rolls_back_failed_transaction(self):
        connection = MagicMock()
        with (
            patch.object(database, "initialize_database"),
            patch.object(database, "_fetchone", return_value=None),
            patch.object(database, "_insert_theory", return_value=11),
            patch.object(
                database,
                "_insert_shared_properties",
                side_effect=database.pymysql.IntegrityError("failed"),
            ),
        ):
            with self.assertRaises(database.pymysql.IntegrityError):
                database.store_lagrangian_theory(connection, E6_SCFT)

        connection.begin.assert_called_once_with()
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_rejects_anomalous_theory_before_transaction(self):
        connection = MagicMock()
        data = {
            "algebra": "A1",
            "hypermultiplets": [
                {
                    "representation": "fundamental",
                    "kind": "half",
                    "number": 1,
                }
            ],
        }
        with patch.object(database, "initialize_database"):
            with self.assertRaisesRegex(
                database.TheoryCheckError, "not gauge-anomaly-free"
            ):
                database.store_lagrangian_theory(connection, data)
        connection.begin.assert_not_called()

    def test_rejects_nonconformal_theory_before_transaction(self):
        connection = MagicMock()
        data = {"algebra": "A2", "hypermultiplets": []}
        with patch.object(database, "initialize_database"):
            with self.assertRaisesRegex(
                database.TheoryCheckError, "not conformal"
            ):
                database.store_lagrangian_theory(connection, data)
        connection.begin.assert_not_called()


MYSQL_TEST_DATABASE = os.environ.get("N2_TEST_MYSQL_DATABASE")


@unittest.skipUnless(
    MYSQL_TEST_DATABASE,
    "set N2_TEST_MYSQL_DATABASE to run live MySQL integration tests",
)
class TheoryDatabaseMySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "test" not in MYSQL_TEST_DATABASE.lower():
            raise RuntimeError(
                "N2_TEST_MYSQL_DATABASE must name a dedicated test database"
            )
        cls.settings = {
            "host": os.environ.get("N2_TEST_MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("N2_TEST_MYSQL_PORT", "3306")),
            "user": os.environ.get("N2_TEST_MYSQL_USER", "root"),
            "password": os.environ.get("N2_TEST_MYSQL_PASSWORD", ""),
            "unix_socket": os.environ.get("N2_TEST_MYSQL_UNIX_SOCKET"),
        }
        cls.connection = database.connect_database(
            MYSQL_TEST_DATABASE, **cls.settings
        )

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def setUp(self):
        database._execute(self.connection, "DELETE FROM theories")

    def test_writes_and_reads_mysql_database(self):
        stored = database.store_lagrangian_theory(
            self.connection, E6_SCFT, name="E6 MySQL test"
        )

        row = database._fetchone(
            self.connection,
            """
            SELECT
                t.name,
                p.flavor_symmetry,
                p.conformal_manifold_dimension,
                p.central_charges_json,
                p.central_charge_a_decimal,
                p.central_charge_c_decimal
            FROM theories AS t
            JOIN theory_properties AS p ON p.theory_id = t.id
            WHERE t.id = %s
            """,
            (stored.theory_id,),
        )
        central_charges = json.loads(row.pop("central_charges_json"))
        a_decimal = row.pop("central_charge_a_decimal")
        c_decimal = row.pop("central_charge_c_decimal")
        self.assertEqual(
            row,
            {
                "name": "E6 MySQL test",
                "flavor_symmetry": "U(4)",
                "conformal_manifold_dimension": 1,
            },
        )
        self.assertEqual(
            central_charges,
            {
                "a": {"numerator": 83, "denominator": 4},
                "c": {"numerator": 22, "denominator": 1},
            },
        )
        self.assertEqual(a_decimal, Decimal("20.75"))
        self.assertEqual(c_decimal, Decimal("22"))

    def test_file_api_writes_existing_json_to_mysql(self):
        input_path = PROJECT_ROOT / "anomalies" / "example_e6.json"

        stored = database.store_lagrangian_theory_from_file(
            MYSQL_TEST_DATABASE,
            input_path,
            name="E6 file API test",
            **self.settings,
        )

        row = database._fetchone(
            self.connection,
            """
            SELECT input_json
            FROM lagrangian_realizations
            WHERE id = %s
            """,
            (stored.lagrangian_realization_id,),
        )
        self.assertEqual(json.loads(row["input_json"])["algebra"], "E6")


if __name__ == "__main__":
    unittest.main()
