#!/usr/bin/env python3
"""Deterministic synthetic exam-scheduling data generator."""
from __future__ import annotations
import argparse, csv, json, random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
EQUIPMENT = ["PROJECTOR", "COMPUTER", "ACCESSIBLE_SEATING", "LAB_KIT"]
PROGRAMS = ["CS", "IT", "EE", "ME", "BA"]
SLOTS = ["09:00", "13:00"]

def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def generate(scale="full", seed=20261022, out_dir=DATA):
    rng = random.Random(seed)
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    counts = cfg[scale]
    n_students, n_courses, n_exams = counts["students"], counts["courses"], counts["exams"]
    n_rooms, n_inv = counts["rooms"], counts["invigilators"]
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    students = [{
        "student_id": f"STU-{i:06d}", "program": rng.choice(PROGRAMS),
        "year_of_study": rng.randint(1, 4), "status": "ACTIVE"
    } for i in range(1, n_students + 1)]
    courses = [{
        "course_id": f"CRS-{i:06d}", "course_code": f"{rng.choice(['CSE','ITE','MAT','PHY','BUS'])}-{100+i:03d}",
        "credits": rng.randint(2, 5)
    } for i in range(1, n_courses + 1)]

    enrollments = []
    enrollment_counter = 1
    # Each student enrolls in 3-6 courses, without duplicate student-course pairs.
    for s in students:
        choices = rng.sample(courses, k=min(len(courses), rng.randint(3, min(6, len(courses)))))
        for c in choices:
            enrollments.append({
                "enrollment_id": f"ENR-{enrollment_counter:07d}", "student_id": s["student_id"],
                "course_id": c["course_id"], "status": "ENROLLED"
            })
            enrollment_counter += 1

    start_date = date.fromisoformat(cfg["schedule_start_date"])
    exams = []
    requirements = []
    exam_equipment = []
    for i in range(1, n_exams + 1):
        exam_id = f"EXAM-2026-{i:06d}"
        d0 = start_date + timedelta(days=rng.randint(0, cfg["days"] - 1))
        d1 = min(start_date + timedelta(days=cfg["days"] - 1), d0 + timedelta(days=rng.randint(1, 4)))
        course_id = courses[(i - 1) % len(courses)]["course_id"]
        exams.append({
            "exam_id": exam_id, "course_id": course_id,
            "earliest_date": d0.isoformat(), "latest_date": d1.isoformat(),
            "priority": "HIGH" if rng.random() < 0.15 else "NORMAL", "status": "PLANNED"
        })
        duration = rng.choice([60, 90, 120, 150, 180])
        accessible = rng.random() < 0.12
        requirements.append({
            "requirement_id": f"REQ-{i:06d}", "exam_id": exam_id,
            "base_duration_minutes": duration, "accessibility_required": str(accessible).lower()
        })
        if rng.random() < 0.25:
            exam_equipment.append({"exam_id": exam_id, "equipment": rng.choice(["PROJECTOR", "COMPUTER", "LAB_KIT"])})

    rooms = []
    capacities = []
    room_equipment = []
    closures = []
    for i in range(1, n_rooms + 1):
        room_id = f"ROOM-{i:06d}"
        rtype = rng.choices(["STANDARD", "ACCESSIBLE", "LAB"], weights=[0.62, 0.23, 0.15])[0]
        cap = rng.choice([30, 40, 60, 80, 100, 120, 150, 200, 250])
        rooms.append({
            "room_id": room_id, "building": f"BLD-{rng.randint(1, 8):02d}",
            "room_type": rtype, "status": "OPEN"
        })
        capacities.append({
            "capacity_id": f"CAP-{i:06d}", "room_id": room_id, "capacity": cap,
            "effective_from": start_date.isoformat(),
            "effective_to": (start_date + timedelta(days=cfg["days"] - 1)).isoformat()
        })
        available_equipment = {"PROJECTOR"}
        if rng.random() < 0.55: available_equipment.add("COMPUTER")
        if rtype == "ACCESSIBLE": available_equipment.add("ACCESSIBLE_SEATING")
        if rtype == "LAB": available_equipment.update(["COMPUTER", "LAB_KIT"])
        for eq in sorted(available_equipment):
            room_equipment.append({"room_id": room_id, "equipment": eq})
        if rng.random() < 0.10:
            close_date = start_date + timedelta(days=rng.randint(0, cfg["days"] - 1))
            closures.append({
                "closure_id": f"CLS-{len(closures)+1:05d}", "room_id": room_id,
                "closed_date": close_date.isoformat(), "reason": "MAINTENANCE"
            })

    invigilators = [{
        "invigilator_id": f"INV-{i:06d}", "department": rng.choice(PROGRAMS), "status": "ACTIVE"
    } for i in range(1, n_inv + 1)]
    availability = []
    avl_counter = 1
    for inv in invigilators:
        for day in range(cfg["days"]):
            d = (start_date + timedelta(days=day)).isoformat()
            for slot in SLOTS:
                availability.append({
                    "availability_id": f"AVL-{avl_counter:07d}", "invigilator_id": inv["invigilator_id"],
                    "exam_date": d, "slot_start": slot, "available": str(rng.random() > 0.10).lower()
                })
                avl_counter += 1

    accommodations = []
    acc_counter = 1
    for s in students:
        if rng.random() < 0.035:
            accommodations.append({
                "accommodation_id": f"ACC-{acc_counter:06d}", "student_id": s["student_id"],
                "accommodation_type": "EXTENDED_TIME", "value": rng.choice([15, 30, 45])
            }); acc_counter += 1
        if rng.random() < 0.018:
            accommodations.append({
                "accommodation_id": f"ACC-{acc_counter:06d}", "student_id": s["student_id"],
                "accommodation_type": "ACCESSIBLE_SEATING", "value": "ACCESSIBLE_SEATING"
            }); acc_counter += 1
        if rng.random() < 0.012:
            accommodations.append({
                "accommodation_id": f"ACC-{acc_counter:06d}", "student_id": s["student_id"],
                "accommodation_type": "ASSISTIVE_EQUIPMENT", "value": "COMPUTER"
            }); acc_counter += 1

    # Labelled negative scenarios live separately from clean baseline tables.
    gt = [
        {"case_id":"GT-001","issue_type":"STUDENT_OVERLAP","entity_type":"STUDENT","expected_decision":"REJECT_OR_RESCHEDULE","expected_reason_code":"STUDENT_CONFLICT","severity":"HIGH"},
        {"case_id":"GT-002","issue_type":"ROOM_CAPACITY_EXCEEDED","entity_type":"ROOM_ASSIGNMENT","expected_decision":"REJECT","expected_reason_code":"NO_ROOM_CAPACITY","severity":"HIGH"},
        {"case_id":"GT-003","issue_type":"INVIGILATOR_DOUBLE_BOOKED","entity_type":"INVIGILATOR_ASSIGNMENT","expected_decision":"REJECT_OR_REASSIGN","expected_reason_code":"INVIGILATOR_UNAVAILABLE","severity":"HIGH"},
        {"case_id":"GT-004","issue_type":"ACCOMMODATION_IGNORED","entity_type":"ACCOMMODATION","expected_decision":"REJECT","expected_reason_code":"ACCOMMODATION_CONFLICT","severity":"CRITICAL"},
        {"case_id":"GT-005","issue_type":"ROOM_CLOSED","entity_type":"ROOM_ASSIGNMENT","expected_decision":"REJECT","expected_reason_code":"ROOM_CLOSED","severity":"HIGH"},
        {"case_id":"GT-006","issue_type":"MISSING_EQUIPMENT","entity_type":"ROOM_ASSIGNMENT","expected_decision":"REJECT","expected_reason_code":"NO_EQUIPMENT","severity":"MEDIUM"},
    ]
    anomaly_cases = [
        {"case_id":"GT-001","proposed_issue":"Two exams for the same student overlap","synthetic_fixture":"student STU-000001; exams EXAM-2026-000001 and EXAM-2026-000002; same date and overlapping intervals"},
        {"case_id":"GT-002","proposed_issue":"Assigned room seats fewer students than enrolled","synthetic_fixture":"exam EXAM-2026-000001; proposed room capacity 30; enrolled count 45"},
        {"case_id":"GT-003","proposed_issue":"Same invigilator assigned to overlapping exams","synthetic_fixture":"invigilator INV-000001; two exams at the same start time"},
        {"case_id":"GT-004","proposed_issue":"Extended-time accommodation omitted from end time","synthetic_fixture":"student STU-000001; base duration 90 minutes; extra time 30 minutes; proposed end is base duration only"},
        {"case_id":"GT-005","proposed_issue":"Exam assigned during room closure","synthetic_fixture":"room ROOM-000001; closure date equals proposed exam date"},
        {"case_id":"GT-006","proposed_issue":"Exam assigned to room without required equipment","synthetic_fixture":"exam requires LAB_KIT; proposed room lacks LAB_KIT"},
    ]

    tables = {
        "students.csv": students, "courses.csv": courses, "enrollments.csv": enrollments,
        "exams.csv": exams, "exam_requirements.csv": requirements, "rooms.csv": rooms,
        "room_capacity.csv": capacities, "invigilators.csv": invigilators,
        "availability.csv": availability, "accommodations.csv": accommodations,
        "room_equipment.csv": room_equipment, "exam_equipment.csv": exam_equipment,
        "room_closures.csv": closures, "ground_truth.csv": gt, "anomaly_cases.csv": anomaly_cases
    }
    for name, rows in tables.items():
        write_csv(out_dir / name, rows)
    manifest = {
        "seed": seed, "scale": scale, "counts": {k: len(v) for k, v in tables.items()},
        "generator": "generate_data.py", "provenance": "Fully synthetic; no external personal data.",
        "ground_truth_separate_from_scheduler_inputs": True
    }
    (out_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scale", choices=["starter", "full"], default="full")
    p.add_argument("--seed", type=int, default=20261022)
    p.add_argument("--out", default=str(DATA))
    a = p.parse_args()
    result = generate(a.scale, a.seed, a.out)
    print(json.dumps(result, indent=2))
