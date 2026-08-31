from enum import StrEnum


class Division(StrEnum):
    BPH = "BPH"
    AKADEMIK_RISET = "Akademik Riset"
    PSDM = "PSDM"
    HUMAS_MULTIMEDIA = "Humas Multimedia"


class MemberRole(StrEnum):
    KETUA = "Ketua"
    WAKIL_KETUA = "Wakil Ketua"
    KEPALA_DIVISI = "Kepala Divisi"
    STAFF = "Staff"
    ANGGOTA = "Anggota"


class MemberStatus(StrEnum):
    AKTIF = "Aktif"
    TIDAK_AKTIF = "Tidak Aktif"
    ALUMNI = "Alumni"


class SelectionStatus(StrEnum):
    ACCEPTED = "Accepted"
    PENDING = "Pending"
    REJECTED = "Rejected"


class StudyProgram(StrEnum):
    S1_INFORMATIKA = "S1 Informatika"
    S1_SISTEM_INFORMASI = "S1 Sistem Informasi"
    S1_SAINS_DATA = "S1 Sains Data"
    D3_SISTEM_INFORMASI = "D3 Sistem Informasi"


class ResearchField(StrEnum):
    IOT_EMBEDDED = "IoT Embedded"
    AI = "AI"
    SOFTWARE_ENGINEER_CLOUD = "Software Engineer & Cloud"
