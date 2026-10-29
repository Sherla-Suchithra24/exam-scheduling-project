#!/usr/bin/env python3
"""Validate relational integrity and all hard constraints in the generated schedule."""
import csv, json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent
DATA, OUT = ROOT / "data", ROOT / "outputs"

def read(path):
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))
def unique(rows, field, errors, label):
    vals = [r.get(field, "") for r in rows]
    dup = [k for k, n in Counter(vals).items() if n > 1]
    if dup: errors.append(f"{label}: duplicate {field}: {dup[:5]}")
def overlaps(a, b, c, d): return a < d and c < b

def run():
    errors = []
    tables = {p.stem: read(p) for p in DATA.glob("*.csv")}
    keys = {"students":"student_id","courses":"course_id","enrollments":"enrollment_id","exams":"exam_id",
            "exam_requirements":"requirement_id","rooms":"room_id","room_capacity":"capacity_id",
            "invigilators":"invigilator_id","availability":"availability_id","accommodations":"accommodation_id"}
    for table, key in keys.items(): unique(tables[table], key, errors, table)
    fk_rules = [
        ("enrollments","student_id","students","student_id"),("enrollments","course_id","courses","course_id"),
        ("exams","course_id","courses","course_id"),("exam_requirements","exam_id","exams","exam_id"),
        ("room_capacity","room_id","rooms","room_id"),("availability","invigilator_id","invigilators","invigilator_id"),
        ("accommodations","student_id","students","student_id"),("room_equipment","room_id","rooms","room_id"),
        ("exam_equipment","exam_id","exams","exam_id"),("room_closures","room_id","rooms","room_id")]
    for child, fk, parent, pk in fk_rules:
        parent_ids = {r[pk] for r in tables[parent]}
        bad = [r.get(fk, "") for r in tables[child] if r.get(fk, "") not in parent_ids]
        if bad: errors.append(f"{child}.{fk}: {len(bad)} foreign-key failures")
    pairs = [(r["student_id"],r["course_id"]) for r in tables["enrollments"]]
    if len(pairs) != len(set(pairs)): errors.append("enrollments: duplicate student-course pair")
    for r in tables["room_capacity"]:
        if int(r["capacity"]) <= 0: errors.append("room capacity must be positive")
        if r["effective_from"] > r["effective_to"]: errors.append("room capacity effective dates reversed")

    assignments = read(OUT/"final_schedule.csv") if (OUT/"final_schedule.csv").exists() else []
    unscheduled = read(OUT/"unscheduled_exams.csv") if (OUT/"unscheduled_exams.csv").exists() else []
    unique(assignments,"assignment_id",errors,"assignments")
    exams = {r["exam_id"]:r for r in tables["exams"]}
    rooms = {r["room_id"]:r for r in tables["rooms"]}
    invs = {r["invigilator_id"]:r for r in tables["invigilators"]}
    requirements = {r["exam_id"]:r for r in tables["exam_requirements"]}
    caps = {r["room_id"]:r for r in tables["room_capacity"]}
    room_eq = defaultdict(set)
    for x in tables["room_equipment"]: room_eq[x["room_id"]].add(x["equipment"])
    exam_eq = defaultdict(set)
    for x in tables["exam_equipment"]: exam_eq[x["exam_id"]].add(x["equipment"])
    closures = {(x["room_id"],x["closed_date"]) for x in tables["room_closures"]}
    availability = {(x["invigilator_id"],x["exam_date"],x["slot_start"]):x["available"]=="true" for x in tables["availability"]}
    enrolled_by_course = defaultdict(set)
    for e in tables["enrollments"]:
        if e["status"]=="ENROLLED": enrolled_by_course[e["course_id"]].add(e["student_id"])
    acc_by_student = defaultdict(list)
    for a in tables["accommodations"]: acc_by_student[a["student_id"]].append(a)
    exam_students = {eid:enrolled_by_course[e["course_id"]] for eid,e in exams.items()}

    by_room, by_inv, by_student = defaultdict(list), defaultdict(list), defaultdict(list)
    assigned_ids = []
    for a in assignments:
        eid, rid, iid = a["exam_id"], a["room_id"], a["invigilator_id"]
        assigned_ids.append(eid)
        if eid not in exams or rid not in rooms or iid not in invs:
            errors.append(f"assignment has unknown parent: {eid}/{rid}/{iid}"); continue
        start, end = datetime.fromisoformat(a["start_time"]), datetime.fromisoformat(a["end_time"])
        dstr = start.date().isoformat()
        if start >= end: errors.append(f"invalid interval {eid}")
        if int(a["enrolled_students"]) != len(exam_students[eid]): errors.append(f"enrollment count mismatch {eid}")
        cap = caps[rid]
        if not (cap["effective_from"] <= dstr <= cap["effective_to"]): errors.append(f"capacity not effective {eid}")
        if int(a["enrolled_students"]) > int(cap["capacity"]): errors.append(f"capacity violation {eid}")
        if rooms[rid]["status"] != "OPEN" or (rid,dstr) in closures: errors.append(f"closed room assigned {eid}")
        needed = set(exam_eq[eid])
        if requirements[eid]["accessibility_required"]=="true": needed.add("ACCESSIBLE_SEATING")
        for sid in exam_students[eid]:
            for acc in acc_by_student[sid]:
                if acc["accommodation_type"]=="ACCESSIBLE_SEATING": needed.add("ACCESSIBLE_SEATING")
                elif acc["accommodation_type"]=="ASSISTIVE_EQUIPMENT": needed.add(str(acc["value"]))
        if not needed.issubset(room_eq[rid]): errors.append(f"equipment/accommodation violation {eid}: {sorted(needed-room_eq[rid])}")
        duration = (end-start).total_seconds()/60
        max_extra = max([int(acc["value"]) for sid in exam_students[eid] for acc in acc_by_student[sid] if acc["accommodation_type"]=="EXTENDED_TIME"] or [0])
        expected = int(requirements[eid]["base_duration_minutes"])+max_extra
        if duration != expected: errors.append(f"duration/accommodation violation {eid}: expected {expected}, got {duration}")
        if not availability.get((iid,dstr,a["slot_start"]),False): errors.append(f"invigilator unavailable {eid}")
        by_room[rid].append((start,end,eid)); by_inv[iid].append((start,end,eid))
        for sid in exam_students[eid]: by_student[sid].append((start,end,eid))
    for label, grouped in [("room",by_room),("invigilator",by_inv),("student",by_student)]:
        for entity, rows in grouped.items():
            rows.sort()
            for prev,curr in zip(rows,rows[1:]):
                if overlaps(prev[0],prev[1],curr[0],curr[1]):
                    errors.append(f"{label} overlap for {entity}: {prev[2]} and {curr[2]}")
    if any(not x.get("reason_code") for x in unscheduled): errors.append("unscheduled exam missing reason code")
    scheduled_ids, unscheduled_ids = set(assigned_ids), {x["exam_id"] for x in unscheduled}
    if len(assigned_ids)!=len(scheduled_ids): errors.append("exam assigned more than once")
    if scheduled_ids & unscheduled_ids: errors.append("exam appears as both scheduled and unscheduled")
    if scheduled_ids | unscheduled_ids != set(exams): errors.append("scheduled/unscheduled exam reconciliation failure")
    summary = {"students":len(tables["students"]),"courses":len(tables["courses"]),"exams":len(tables["exams"]),
               "rooms":len(tables["rooms"]),"invigilators":len(tables["invigilators"]),
               "assignments":len(assignments),"unscheduled":len(unscheduled),"foreign_key_rules_checked":len(fk_rules),
               "errors":len(errors),"passed":not errors}
    OUT.mkdir(exist_ok=True)
    (OUT/"validation_summary.json").write_text(json.dumps({"summary":summary,"errors":errors},indent=2),encoding="utf-8")
    print(json.dumps({"summary":summary,"errors":errors[:30]},indent=2))
    if errors: raise SystemExit(1)
if __name__=="__main__": run()
