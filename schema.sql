-- Reference relational schema. Run on SQLite 3.
PRAGMA foreign_keys = ON;
CREATE TABLE Student(student_id TEXT PRIMARY KEY, program TEXT NOT NULL, year_of_study INTEGER NOT NULL CHECK(year_of_study BETWEEN 1 AND 4), status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')));
CREATE TABLE Course(course_id TEXT PRIMARY KEY, course_code TEXT NOT NULL UNIQUE, credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 6));
CREATE TABLE Enrollment(enrollment_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES Student(student_id), course_id TEXT NOT NULL REFERENCES Course(course_id), status TEXT NOT NULL CHECK(status IN ('ENROLLED','WITHDRAWN')), UNIQUE(student_id,course_id));
CREATE TABLE Exam(exam_id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES Course(course_id), earliest_date TEXT NOT NULL, latest_date TEXT NOT NULL, priority TEXT NOT NULL CHECK(priority IN ('HIGH','NORMAL')), status TEXT NOT NULL CHECK(status IN ('PLANNED','CANCELLED')), CHECK(earliest_date <= latest_date));
CREATE TABLE ExamRequirement(requirement_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL REFERENCES Exam(exam_id), base_duration_minutes INTEGER NOT NULL CHECK(base_duration_minutes > 0), accessibility_required INTEGER NOT NULL CHECK(accessibility_required IN (0,1)));
CREATE TABLE Room(room_id TEXT PRIMARY KEY, building TEXT NOT NULL, room_type TEXT NOT NULL CHECK(room_type IN ('STANDARD','ACCESSIBLE','LAB')), status TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED')));
CREATE TABLE RoomCapacity(capacity_id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES Room(room_id), capacity INTEGER NOT NULL CHECK(capacity > 0), effective_from TEXT NOT NULL, effective_to TEXT NOT NULL, CHECK(effective_from <= effective_to));
CREATE TABLE Invigilator(invigilator_id TEXT PRIMARY KEY, department TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')));
CREATE TABLE Availability(availability_id TEXT PRIMARY KEY, invigilator_id TEXT NOT NULL REFERENCES Invigilator(invigilator_id), exam_date TEXT NOT NULL, slot_start TEXT NOT NULL, available INTEGER NOT NULL CHECK(available IN (0,1)), UNIQUE(invigilator_id,exam_date,slot_start));
CREATE TABLE Accommodation(accommodation_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES Student(student_id), accommodation_type TEXT NOT NULL CHECK(accommodation_type IN ('EXTENDED_TIME','ACCESSIBLE_SEATING','ASSISTIVE_EQUIPMENT')), value TEXT NOT NULL);
CREATE TABLE RoomEquipment(room_id TEXT NOT NULL REFERENCES Room(room_id), equipment TEXT NOT NULL, PRIMARY KEY(room_id,equipment));
CREATE TABLE ExamEquipment(exam_id TEXT NOT NULL REFERENCES Exam(exam_id), equipment TEXT NOT NULL, PRIMARY KEY(exam_id,equipment));
CREATE TABLE RoomClosure(closure_id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES Room(room_id), closed_date TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE ScheduleAssignment(assignment_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL UNIQUE REFERENCES Exam(exam_id), room_id TEXT NOT NULL REFERENCES Room(room_id), invigilator_id TEXT NOT NULL REFERENCES Invigilator(invigilator_id), start_time TEXT NOT NULL, end_time TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ASSIGNED','CANCELLED')), CHECK(start_time < end_time));
CREATE TABLE ScheduleEvent(event_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL REFERENCES Exam(exam_id), event_type TEXT NOT NULL, event_time TEXT NOT NULL, decision_reason TEXT NOT NULL);
