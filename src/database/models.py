import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_ar: Mapped[Optional[str]] = mapped_column(String)
    name_en: Mapped[Optional[str]] = mapped_column(String)
    phone: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    national_id: Mapped[Optional[str]] = mapped_column(String)
    gender: Mapped[Optional[str]] = mapped_column(String)
    patient_type: Mapped[Optional[str]] = mapped_column(String, default="NORMAL")
    official_title: Mapped[Optional[str]] = mapped_column(String)
    delegation_name: Mapped[Optional[str]] = mapped_column(String)
    protocol_officer_name: Mapped[Optional[str]] = mapped_column(String)
    protocol_officer_phone: Mapped[Optional[str]] = mapped_column(String)
    password_hash: Mapped[Optional[str]] = mapped_column(String)
    auth_pin: Mapped[Optional[str]] = mapped_column(String)
    is_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="patient")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    code: Mapped[Optional[str]] = mapped_column(String)
    name_ar: Mapped[str] = mapped_column(String)
    name_en: Mapped[str] = mapped_column(String)
    description_ar: Mapped[Optional[str]] = mapped_column(Text)
    description_en: Mapped[Optional[str]] = mapped_column(Text)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer)
    default_slot_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=30)
    is_vip_secured: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    doctors: Mapped[list["Doctor"]] = relationship(back_populates="department")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="department")


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))
    name_ar: Mapped[str] = mapped_column(String)
    name_en: Mapped[str] = mapped_column(String)
    title_ar: Mapped[Optional[str]] = mapped_column(String)
    title_en: Mapped[Optional[str]] = mapped_column(String)
    specialty_ar: Mapped[Optional[str]] = mapped_column(String)
    specialty_en: Mapped[Optional[str]] = mapped_column(String)
    experience_years: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    consultation_fee: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    rating: Mapped[Optional[float]] = mapped_column(Float, default=5.0)
    is_vip_physician: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    department: Mapped[Optional["Department"]] = relationship(back_populates="doctors")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"))
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="CONFIRMED")
    booking_source: Mapped[Optional[str]] = mapped_column(String, default="FLUTTER_APP")
    is_vip_booking: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    reason_for_visit: Mapped[Optional[str]] = mapped_column(String)
    diagnosis_notes: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    patient: Mapped[Optional["Patient"]] = relationship(back_populates="appointments")
    doctor: Mapped[Optional["Doctor"]] = relationship(back_populates="appointments")
    department: Mapped[Optional["Department"]] = relationship(back_populates="appointments")
    history: Mapped[list["AppointmentHistory"]] = relationship(back_populates="appointment")


class AppointmentHistory(Base):
    __tablename__ = "appointment_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"))
    action: Mapped[str] = mapped_column(String)
    old_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    new_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    old_status: Mapped[Optional[str]] = mapped_column(String)
    new_status: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    appointment: Mapped[Optional["Appointment"]] = relationship(back_populates="history")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String, default="FLUTTER_MOBILE")
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[Optional["Patient"]] = relationship(back_populates="chat_messages")


class VipDelegation(Base):
    __tablename__ = "vip_delegations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delegation_title: Mapped[str] = mapped_column(String)
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))
    secured_start_at: Mapped[datetime] = mapped_column(DateTime)
    secured_end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="SCHEDULED")
    displaced_count: Mapped[int] = mapped_column(Integer, default=0)
    protocol_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
