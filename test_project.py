import csv, tempfile, unittest
from pathlib import Path
from generate_data import generate

class GeneratorTests(unittest.TestCase):
    def test_starter_counts_and_keys(self):
        with tempfile.TemporaryDirectory() as td:
            manifest=generate("starter",20261022,td)
            self.assertEqual(manifest["counts"]["students.csv"],250)
            with open(Path(td)/"students.csv",newline="",encoding="utf-8") as f:
                rows=list(csv.DictReader(f))
            ids=[r["student_id"] for r in rows]
            self.assertEqual(len(ids),len(set(ids)))
            self.assertEqual(ids[0],"STU-000001")
    def test_same_seed_same_csv(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate("starter",123,a); generate("starter",123,b)
            for name in ["students.csv","courses.csv","enrollments.csv","exams.csv","rooms.csv"]:
                self.assertEqual((Path(a)/name).read_bytes(),(Path(b)/name).read_bytes())
if __name__=="__main__": unittest.main()
