# Data Dictionary

All records are synthetic. Unless marked optional, fields are required. IDs are strings and unique within their entity. Dates use `YYYY-MM-DD`; timestamps use ISO 8601 local time.

| Entity / file | Field | Type | Required | Allowed values / units | Validation |
|---|---|---:|---|---|---|
| Student / students.csv | student_id | string | yes | `STU-000001` format | PK, immutable |
| | program | enum | yes | `CS, IT, EE, ME, BA` | controlled enum |
| | year_of_study | integer | yes | 1–4 | range check |
| | status | enum | yes | `ACTIVE, INACTIVE` | controlled enum |
| Course / courses.csv | course_id | string | yes | `CRS-000001` | PK |
| | course_code | string | yes | unique `CSE-101`-style code | unique |
| | credits | integer | yes | 1–6 | range check |
| Enrollment / enrollments.csv | enrollment_id | string | yes | `ENR-000001` | PK |
| | student_id, course_id | string | yes | existing parent IDs | FK; pair unique |
| | status | enum | yes | `ENROLLED, WITHDRAWN` | controlled enum |
| Exam / exams.csv | exam_id | string | yes | `EXAM-2026-000001` | PK |
| | course_id | string | yes | existing course | FK |
| | earliest_date, latest_date | date | yes | scheduling window | earliest <= latest |
| | priority, status | enum | yes | priority `HIGH, NORMAL`; status `PLANNED` | controlled enum |
| ExamRequirement / exam_requirements.csv | requirement_id | string | yes | `REQ-000001` | PK |
| | exam_id | string | yes | existing exam | FK |
| | base_duration_minutes | integer | yes | minutes, 60–180 | positive |
| | accessibility_required | boolean | yes | `true/false` | parse as boolean |
| Room / rooms.csv | room_id | string | yes | `ROOM-000001` | PK |
| | building | string | yes | synthetic building label | nonempty |
| | room_type, status | enum | yes | `STANDARD, ACCESSIBLE, LAB`; `OPEN, CLOSED` | controlled enum |
| RoomCapacity / room_capacity.csv | capacity_id | string | yes | `CAP-000001` | PK |
| | room_id | string | yes | existing room | FK |
| | capacity | integer | yes | seats | > 0 |
| | effective_from, effective_to | date | yes | inclusive validity | from <= to |
| Invigilator / invigilators.csv | invigilator_id | string | yes | `INV-000001` | PK |
| | department | string | yes | synthetic department | nonempty |
| | status | enum | yes | `ACTIVE, INACTIVE` | controlled enum |
| Availability / availability.csv | availability_id | string | yes | `AVL-000001` | PK |
| | invigilator_id | string | yes | existing invigilator | FK |
| | exam_date, slot_start | date/time | yes | defined timetable slots | slot-specific |
| | available | boolean | yes | `true/false` | controlled boolean |
| Accommodation / accommodations.csv | accommodation_id | string | yes | `ACC-000001` | PK |
| | student_id | string | yes | existing student | FK |
| | accommodation_type | enum | yes | `EXTENDED_TIME, ACCESSIBLE_SEATING, ASSISTIVE_EQUIPMENT` | controlled enum |
| | value | integer/string | yes | extra minutes or equipment code | type-specific validation |
| ScheduleAssignment / outputs/final_schedule.csv | assignment_id | string | yes | `ASN-<exam-id>-<room-id>` | unique per exam-room pair |
| | exam_id, room_id, invigilator_id | string | yes for assigned row | existing IDs | FKs |
| | start_time, end_time | datetime | yes | ISO local datetime | start < end |
| | status | enum | yes | `ASSIGNED` | hard constraints pass |
| Room/equipment bridge | room_id, equipment | string | yes | `PROJECTOR, COMPUTER, ACCESSIBLE_SEATING, LAB_KIT` | FK + enum |
| Exam/equipment bridge | exam_id, equipment | string | yes | same equipment enum | FK + enum |
| Audit event | event_id | string | yes | sequential event ID | PK |
| | exam_id, event_type, event_time | string/datetime | yes | `ASSIGNED, UNSCHEDULED` | append-only event |

## Relationship cardinality

- Student 1:N Enrollment; Course 1:N Enrollment; Student N:M Course through Enrollment.
- Course 1:N Exam in this sample model.
- Exam 1:N ExamRequirement (one row is generated per exam by default).
- Room 1:N RoomCapacity; historical capacity periods must not overlap for the same room.
- Invigilator 1:N Availability.
- Student 1:N Accommodation.
- Exam N:M Invigilator through exam_invigilators / assignments.
- Room N:M Equipment through room_equipment; Exam N:M Equipment through exam_equipment.
- Exam 0:1 current successful assignment in this implementation; audit history can contain multiple attempts/events.

## Lifecycle and effective dates

Enrollments may be `ENROLLED` or `WITHDRAWN`; only enrolled students count toward exam demand. Rooms and invigilators can be active/inactive; closed rooms and unavailable invigilators cannot be assigned. Capacity rows have inclusive effective dates. Schedule decisions are append-only in the audit event log.
