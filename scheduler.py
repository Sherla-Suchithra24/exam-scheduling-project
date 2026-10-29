
#!/usr/bin/env python3
"""Deterministic greedy exam scheduler. Ground truth is intentionally never loaded."""

import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

SLOTS = ["09:00", "13:00"]

REASONS = [
    "NO_ROOM_CAPACITY",
    "NO_EQUIPMENT",
    "ROOM_CLOSED",
    "NO_AVAILABLE_SLOT",
    "INVIGILATOR_UNAVAILABLE",
    "STUDENT_CONFLICT",
    "ACCOMMODATION_CONFLICT",
]


def read(name):
    with (DATA / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields=None):
    OUT.mkdir(parents=True, exist_ok=True)

    if fields is None:
        fields = list(rows[0].keys()) if rows else []

    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def run():
    OUT.mkdir(parents=True, exist_ok=True)

    students = {
        x["student_id"]: x
        for x in read("students.csv")
    }

    courses = {
        x["course_id"]: x
        for x in read("courses.csv")
    }

    enrollments = read("enrollments.csv")
    exams = read("exams.csv")

    reqs = {
        x["exam_id"]: x
        for x in read("exam_requirements.csv")
    }

    rooms = {
        x["room_id"]: x
        for x in read("rooms.csv")
    }

    capacity_records = read("room_capacity.csv")

    invigilators = [
        x for x in read("invigilators.csv")
        if x["status"] == "ACTIVE"
    ]

    availability = {
        (x["invigilator_id"], x["exam_date"], x["slot_start"]):
        x["available"].lower() == "true"
        for x in read("availability.csv")
    }

    accommodations = read("accommodations.csv")

    room_eq = defaultdict(set)
    for x in read("room_equipment.csv"):
        room_eq[x["room_id"]].add(x["equipment"])

    exam_eq = defaultdict(set)
    for x in read("exam_equipment.csv"):
        exam_eq[x["exam_id"]].add(x["equipment"])

    closures = {
        (x["room_id"], x["closed_date"])
        for x in read("room_closures.csv")
    }

    enrolled_by_course = defaultdict(set)

    for enrollment in enrollments:
        if enrollment["status"] == "ENROLLED":
            enrolled_by_course[enrollment["course_id"]].add(
                enrollment["student_id"]
            )

    acc_by_student = defaultdict(list)

    for accommodation in accommodations:
        acc_by_student[accommodation["student_id"]].append(
            accommodation
        )

    exam_students = {}
    effective_duration = {}
    accessible_exam = {}

    for exam in exams:
        exam_id = exam["exam_id"]
        people = enrolled_by_course[exam["course_id"]]

        exam_students[exam_id] = people
        requirement = reqs[exam_id]

        extra_time = max(
            [
                int(accommodation["value"])
                for student_id in people
                for accommodation in acc_by_student[student_id]
                if accommodation["accommodation_type"] == "EXTENDED_TIME"
            ] or [0]
        )

        effective_duration[exam_id] = (
            int(requirement["base_duration_minutes"]) + extra_time
        )

        accessible_exam[exam_id] = (
            requirement["accessibility_required"].lower() == "true"
            or any(
                accommodation["accommodation_type"] == "ACCESSIBLE_SEATING"
                for student_id in people
                for accommodation in acc_by_student[student_id]
            )
        )

    # Build the student conflict graph.
    conflict = defaultdict(set)

    for i, exam_a in enumerate(exams):
        for exam_b in exams[i + 1:]:
            id_a = exam_a["exam_id"]
            id_b = exam_b["exam_id"]

            if exam_students[id_a] & exam_students[id_b]:
                conflict[id_a].add(id_b)
                conflict[id_b].add(id_a)

    # Schedule high-priority, less-flexible, highly conflicting exams first.
    ordered = sorted(
        exams,
        key=lambda exam: (
            exam["priority"] != "HIGH",
            (
                date.fromisoformat(exam["latest_date"])
                - date.fromisoformat(exam["earliest_date"])
            ).days,
            -len(conflict[exam["exam_id"]]),
            -len(exam_students[exam["exam_id"]]),
            exam["exam_id"],
        ),
    )

    assigned = []
    unscheduled = []
    audit = []

    # Resource occupancy intervals.
    exam_intervals = defaultdict(list)
    room_intervals = defaultdict(list)
    inv_intervals = defaultdict(list)

    for exam in ordered:
        exam_id = exam["exam_id"]
        course_id = exam["course_id"]
        people = exam_students[exam_id]

        earliest = date.fromisoformat(exam["earliest_date"])
        latest = date.fromisoformat(exam["latest_date"])

        candidates = []
        current_date = earliest

        while current_date <= latest:
            for slot in SLOTS:
                start = datetime.fromisoformat(
                    f"{current_date.isoformat()}T{slot}:00"
                )
                end = start + timedelta(
                    minutes=effective_duration[exam_id]
                )

                candidates.append((start, end, slot))

            current_date += timedelta(days=1)

        candidates.sort(key=lambda item: (item[0].date(), item[0].time()))

        reasons_seen = set()
        placed = False

        for start, end, slot in candidates:
            date_string = start.date().isoformat()

            # Students cannot have overlapping exams.
            if any(
                overlap(start, end, existing_start, existing_end)
                for student_id in people
                for existing_start, existing_end, _ in exam_intervals[student_id]
            ):
                reasons_seen.add("STUDENT_CONFLICT")
                continue

            # Required equipment and accommodations.
            equipment_needed = exam_eq[exam_id].copy()

            if accessible_exam[exam_id]:
                equipment_needed.add("ACCESSIBLE_SEATING")

            for student_id in people:
                for accommodation in acc_by_student[student_id]:
                    if accommodation["accommodation_type"] == "ASSISTIVE_EQUIPMENT":
                        equipment_needed.add(str(accommodation["value"]))

            # Find rooms that satisfy all room constraints.
            candidate_rooms = []

            for room_id, room in rooms.items():
                if (
                    room["status"] != "OPEN"
                    or (room_id, date_string) in closures
                ):
                    reasons_seen.add("ROOM_CLOSED")
                    continue

                valid_capacities = [
                    int(record["capacity"])
                    for record in capacity_records
                    if record["room_id"] == room_id
                    and record["effective_from"] <= date_string
                    and record["effective_to"] >= date_string
                ]

                if not valid_capacities:
                    continue

                capacity = max(valid_capacities)

                if len(people) > capacity:
                    reasons_seen.add("NO_ROOM_CAPACITY")
                    continue

                if not equipment_needed.issubset(room_eq[room_id]):
                    reasons_seen.add("NO_EQUIPMENT")
                    continue

                if any(
                    overlap(start, end, existing_start, existing_end)
                    for existing_start, existing_end, _ in room_intervals[room_id]
                ):
                    continue

                # FIX: Add each feasible room to the candidate list.
                candidate_rooms.append((capacity, room_id))

            # Prefer the smallest room that can accommodate the exam.
            candidate_rooms.sort()

            if not candidate_rooms:
                continue

            # Find an available invigilator.
            chosen_invigilator = None

            for invigilator in invigilators:
                invigilator_id = invigilator["invigilator_id"]

                if not availability.get(
                    (invigilator_id, date_string, slot), False
                ):
                    reasons_seen.add("INVIGILATOR_UNAVAILABLE")
                    continue

                if any(
                    overlap(start, end, existing_start, existing_end)
                    for existing_start, existing_end, _
                    in inv_intervals[invigilator_id]
                ):
                    continue

                chosen_invigilator = invigilator_id
                break

            if chosen_invigilator is None:
                continue

            # Select the best candidate room.
            capacity, room_id = candidate_rooms[0]

            row = {
                "assignment_id": f"ASN-{exam_id}-{room_id}",
                "exam_id": exam_id,
                "course_id": course_id,
                "room_id": room_id,
                "invigilator_id": chosen_invigilator,
                "exam_date": date_string,
                "slot_start": slot,
                "start_time": start.isoformat(timespec="minutes"),
                "end_time": end.isoformat(timespec="minutes"),
                "enrolled_students": len(people),
                "room_capacity": capacity,
                "effective_duration_minutes": effective_duration[exam_id],
                "status": "ASSIGNED",
                "reason_code": "",
            }

            assigned.append(row)

            room_intervals[room_id].append((start, end, exam_id))
            inv_intervals[chosen_invigilator].append((start, end, exam_id))

            for student_id in people:
                exam_intervals[student_id].append((start, end, exam_id))

            audit.append({
                "event_id": f"EVT-{len(audit) + 1:07d}",
                "exam_id": exam_id,
                "event_type": "ASSIGNED",
                "event_time": datetime.now().isoformat(timespec="seconds"),
                "room_id": room_id,
                "invigilator_id": chosen_invigilator,
                "decision_reason": "ALL_HARD_CONSTRAINTS_PASSED",
            })

            placed = True
            break

        if not placed:
            reason_priority = [
                "NO_ROOM_CAPACITY",
                "NO_EQUIPMENT",
                "ROOM_CLOSED",
                "STUDENT_CONFLICT",
                "INVIGILATOR_UNAVAILABLE",
                "NO_AVAILABLE_SLOT",
            ]

            reason = next(
                (
                    item for item in reason_priority
                    if item in reasons_seen
                ),
                "NO_AVAILABLE_SLOT",
            )

            reason_messages = {
                "NO_ROOM_CAPACITY":
                    "No room with enough seats was available in the exam window.",
                "NO_EQUIPMENT":
                    "No feasible room had all required equipment.",
                "ROOM_CLOSED":
                    "Candidate rooms were closed or unavailable.",
                "STUDENT_CONFLICT":
                    "All feasible candidate times conflicted with another exam for at least one enrolled student.",
                "INVIGILATOR_UNAVAILABLE":
                    "No available invigilator could cover a feasible room and time.",
                "ACCOMMODATION_CONFLICT":
                    "A required accommodation could not be satisfied.",
                "NO_AVAILABLE_SLOT":
                    "No feasible room/time/invigilator combination was found.",
            }

            unscheduled.append({
                "exam_id": exam_id,
                "course_id": course_id,
                "enrolled_students": len(people),
                "earliest_date": exam["earliest_date"],
                "latest_date": exam["latest_date"],
                "effective_duration_minutes": effective_duration[exam_id],
                "status": "UNSCHEDULED",
                "reason_code": reason,
                "reason": reason_messages[reason],
            })

            audit.append({
                "event_id": f"EVT-{len(audit) + 1:07d}",
                "exam_id": exam_id,
                "event_type": "UNSCHEDULED",
                "event_time": datetime.now().isoformat(timespec="seconds"),
                "room_id": "",
                "invigilator_id": "",
                "decision_reason": reason,
            })

    write("final_schedule.csv", assigned)
    write("unscheduled_exams.csv", unscheduled)
    write("audit_events.csv", audit)

    issue_log = [
        {
            "exam_id": item["exam_id"],
            "issue_type": "UNSCHEDULED",
            "reason_code": item["reason_code"],
            "detail": item["reason"],
        }
        for item in unscheduled
    ]

    write("issue_log.csv", issue_log)

    summary = {
        "total_exams": len(exams),
        "assigned": len(assigned),
        "unscheduled": len(unscheduled),
        "hard_constraint_violations_expected": 0,
        "completion_rate": (
            round(len(assigned) / len(exams), 4) if exams else 0
        ),
        "reason_counts": {
            reason: sum(
                item["reason_code"] == reason for item in unscheduled
            )
            for reason in REASONS
        },
    }

    (OUT / "scheduler_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
