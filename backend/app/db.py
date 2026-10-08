from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Float, ForeignKey, JSON, LargeBinary, event, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings
import time
import uuid


class Base(DeclarativeBase):
    pass


def uid():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='ready')
    created: Mapped[float] = mapped_column(Float, default=time.time)
    expires: Mapped[float] = mapped_column(Float)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class RecordMixin:
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.id', ondelete='CASCADE'), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class Question(RecordMixin, Base):
    __tablename__ = 'questions'


class InterviewInteraction(RecordMixin, Base):
    __tablename__ = 'interview_interactions'


class AssessmentResource(Base):
    __tablename__ = 'assessment_resources'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class Answer(RecordMixin, Base):
    __tablename__ = 'answers'


class Observation(RecordMixin, Base):
    __tablename__ = 'observations'


class Snapshot(RecordMixin, Base):
    __tablename__ = 'snapshots'


class Feelings(RecordMixin, Base):
    __tablename__ = 'answer_feelings'


class Consent(RecordMixin, Base):
    __tablename__ = 'consent_events'


class Job(RecordMixin, Base):
    __tablename__ = 'jobs'


class Report(RecordMixin, Base):
    __tablename__ = 'reports'
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    role: Mapped[str] = mapped_column(String)


class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Recruiter(Base):
    __tablename__ = 'recruiters'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default='candidate')
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    csrf: Mapped[str] = mapped_column(String)
    expires: Mapped[float] = mapped_column(Float)


class Examination(Base):
    __tablename__ = 'examinations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    hr_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class Assignment(Base):
    __tablename__ = 'exam_assignments'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey('examinations.id'))
    candidate_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    session_id: Mapped[str | None] = mapped_column(ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    hr_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.id', ondelete='CASCADE'))
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class RecruitmentPosition(Base):
    __tablename__ = 'recruitment_positions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    hr_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey('organizations.id'), nullable=True, index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class RecruitmentCandidate(Base):
    __tablename__ = 'recruitment_candidates'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    hr_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class Application(Base):
    __tablename__ = 'applications'
    __table_args__ = (UniqueConstraint('candidate_id','position_id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    position_id: Mapped[str] = mapped_column(ForeignKey('recruitment_positions.id'), index=True)
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey('exam_assignments.id'), nullable=True)
    status: Mapped[str] = mapped_column(String, default='applied', index=True)
    applied_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    hr_notes: Mapped[str] = mapped_column(String, default='')


class CandidateResume(Base):
    __tablename__ = 'candidate_resumes'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    filename: Mapped[str] = mapped_column(String)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

class RoleCriterion(Base):
    __tablename__ = 'role_criteria'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    position_id: Mapped[str] = mapped_column(ForeignKey('recruitment_positions.id'), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)

class ResumeExtraction(Base):
    __tablename__ = 'resume_extractions'
    id: Mapped[str] = mapped_column(ForeignKey('candidate_resumes.id'), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)

class ScreeningSummary(Base):
    __tablename__ = 'screening_summary'
    id: Mapped[str] = mapped_column(ForeignKey('applications.id'), primary_key=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)

class ScreeningResult(Base):
    __tablename__ = 'screening_results'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    criterion_id: Mapped[str] = mapped_column(ForeignKey('role_criteria.id'))
    body: Mapped[dict] = mapped_column(JSON, default=dict)

class ApplicationResume(Base):
    __tablename__ = 'application_resumes'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), primary_key=True)
    resume_id: Mapped[str] = mapped_column(ForeignKey('candidate_resumes.id'))

class RecruitmentActivity(Base):
    __tablename__ = 'recruitment_activity'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    hr_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class PracticeAttempt(Base):
    __tablename__ = 'candidate_practice_attempts'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    revision: Mapped[int] = mapped_column(default=0)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class PracticeQuestion(Base):
    __tablename__ = 'candidate_question_bank'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class IdentityPhoto(Base):
    __tablename__ = 'identity_photos'
    candidate_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    version: Mapped[str] = mapped_column(String, default=uid)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class EmailDelivery(Base):
    __tablename__ = 'email_deliveries'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default='pending', index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt: Mapped[float] = mapped_column(Float, default=0)


class CandidateNotice(Base):
    __tablename__ = 'candidate_notices'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)


class Recovery(Base):
    __tablename__ = 'password_recovery'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[dict] = mapped_column(JSON, default=dict)


engine = create_engine(settings.database_url, connect_args={'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}, pool_pre_ping=True)
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_setup(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')

DB = sessionmaker(engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)
    from sqlalchemy import inspect, text, select
    if 'organization_id' not in {c['name'] for c in inspect(engine).get_columns('recruitment_positions')}:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE recruitment_positions ADD COLUMN organization_id VARCHAR REFERENCES organizations(id)'))
    with DB() as db:
        for user in db.scalars(select(User).where(User.role.in_(['hr','admin']))):
            if not db.get(Recruiter,user.id):
                org=Organization(name=user.name+' organization');db.add(org);db.flush()
                db.add(Recruiter(user_id=user.id,organization_id=org.id))
        db.flush()
        for position in db.scalars(select(RecruitmentPosition)):
            membership=db.get(Recruiter,position.hr_id)
            if not position.organization_id and membership:position.organization_id=membership.organization_id
        db.commit()

class InterviewRound(Base):
    __tablename__ = 'interview_rounds'
    __table_args__ = (UniqueConstraint('position_id', 'round_order'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    position_id: Mapped[str] = mapped_column(ForeignKey('recruitment_positions.id'), index=True)
    round_order: Mapped[int] = mapped_column()
    round_type: Mapped[str] = mapped_column(String)
    round_name: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(default=True)


class ApplicationRound(Base):
    __tablename__ = 'application_rounds'
    __table_args__ = (UniqueConstraint('application_id', 'round_id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    round_id: Mapped[str] = mapped_column(ForeignKey('interview_rounds.id'))
    status: Mapped[str] = mapped_column(String, default='pending')
    interview_session_id: Mapped[str | None] = mapped_column(ForeignKey('sessions.id'), nullable=True)
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey('exam_assignments.id'), nullable=True)
    invited_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hr_notes: Mapped[str] = mapped_column(String, default='')
