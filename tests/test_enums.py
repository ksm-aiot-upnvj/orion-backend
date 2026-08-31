import pytest
from pydantic import ValidationError

from models.enums import (
    Division,
    MemberRole,
    MemberStatus,
    ResearchField,
    SelectionStatus,
    StudyProgram,
)
from schemas.member import MemberCreate
from schemas.registration import RegistrationCreate, RegistrationReview
from schemas.user import UserBase


def test_enum_values():
    assert Division.BPH == "BPH"
    assert Division.AKADEMIK_RISET == "Akademik Riset"
    assert Division.PSDM == "PSDM"
    assert Division.HUMAS_MULTIMEDIA == "Humas Multimedia"

    assert MemberRole.KETUA == "Ketua"
    assert MemberRole.WAKIL_KETUA == "Wakil Ketua"
    assert MemberRole.KEPALA_DIVISI == "Kepala Divisi"
    assert MemberRole.STAFF == "Staff"
    assert MemberRole.ANGGOTA == "Anggota"

    assert MemberStatus.AKTIF == "Aktif"
    assert MemberStatus.TIDAK_AKTIF == "Tidak Aktif"
    assert MemberStatus.ALUMNI == "Alumni"

    assert SelectionStatus.ACCEPTED == "Accepted"
    assert SelectionStatus.PENDING == "Pending"
    assert SelectionStatus.REJECTED == "Rejected"

    assert StudyProgram.S1_INFORMATIKA == "S1 Informatika"
    assert StudyProgram.S1_SISTEM_INFORMASI == "S1 Sistem Informasi"
    assert StudyProgram.S1_SAINS_DATA == "S1 Sains Data"
    assert StudyProgram.D3_SISTEM_INFORMASI == "D3 Sistem Informasi"

    assert ResearchField.IOT_EMBEDDED == "IoT Embedded"
    assert ResearchField.AI == "AI"
    assert ResearchField.SOFTWARE_ENGINEER_CLOUD == "Software Engineer & Cloud"


def test_member_schema_enums():
    payload = {
        "member_id": "AIOT-2026-001",
        "student_id": "2410511001",
        "full_name": "Test Candidate",
        "program_of_study": "S1 Informatika",
        "division": "Akademik Riset",
        "role": "Staff",
        "intake_period": "2026",
        "interest_track": ["IoT Embedded", "AI"],
        "email": "test@upnvj.ac.id",
        "status": "Aktif",
    }
    member = MemberCreate(**payload)
    assert member.program_of_study == StudyProgram.S1_INFORMATIKA
    assert member.division == Division.AKADEMIK_RISET
    assert member.role == MemberRole.STAFF
    assert member.status == MemberStatus.AKTIF
    assert member.interest_track == [ResearchField.IOT_EMBEDDED, ResearchField.AI]


def test_registration_schema_enums():
    payload = {
        "student_id": "2410511002",
        "full_name": "Recruit Candidate",
        "program_of_study": "S1 Sains Data",
        "email": "recruit@upnvj.ac.id",
        "interest_track": "IoT Embedded, AI",
    }
    reg = RegistrationCreate(**payload)
    assert reg.program_of_study == StudyProgram.S1_SAINS_DATA
    assert reg.interest_track == [ResearchField.IOT_EMBEDDED, ResearchField.AI]

    review = RegistrationReview(status=SelectionStatus.ACCEPTED)
    assert review.status == SelectionStatus.ACCEPTED


def test_invalid_enum_validation():
    with pytest.raises(ValidationError):
        UserBase(
            student_id="2410511003",
            full_name="Invalid User",
            email="invalid@upnvj.ac.id",
            division="NonExistentDivision",
        )
