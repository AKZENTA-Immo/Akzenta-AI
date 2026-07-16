import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import main


class DokumentTests(unittest.TestCase):
    def test_filter_und_statistik(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            basis = Path(temp_dir)
            (basis / "01_Exposes").mkdir()
            (basis / "01_Exposes" / "a.PDF").touch()
            (basis / "01_Exposes" / "b.jpg").touch()
            (basis / "notiz.txt").touch()

            with patch.object(main, "DROPBOX_PATH", basis):
                liste = main.dokumente()
                statistik = main.dokumente_statistik()

            self.assertEqual(liste["anzahl"], 2)
            self.assertEqual(statistik["gesamtzahl"], 2)
            self.assertEqual(statistik["nach_endung"], {".pdf": 1, ".txt": 1})
            self.assertEqual(
                statistik["nach_hauptordner"],
                {"01_Exposes": 1, "Stammordner": 1},
            )

    def test_fehlender_ordner(self):
        with patch.object(main, "DROPBOX_PATH", Path("Z:/nicht-vorhanden")):
            with self.assertRaises(HTTPException) as context:
                main.dokumente()
        self.assertEqual(context.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
