from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Profile(BaseModel):
    skills: list[str] = Field(default_factory=list, max_length=30)
    projects: list[str] = Field(default_factory=list, max_length=15)
    responsibilities: list[str] = Field(default_factory=list, max_length=15)
    experience: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def limits(self):
        if any(len(x) > 1200 for x in self.skills + self.projects + self.responsibilities):
            raise ValueError('Profile entries must be under 1,200 characters.')
        return self


class SessionInput(BaseModel):
    assignment_id: str | None = Field(default=None,max_length=100)
    mode: Literal['practice', 'hr']
    name: str = Field(min_length=2, max_length=150)
    role: str = Field(min_length=2, max_length=150)
    level: Literal['intern', 'junior', 'mid-level', 'senior']
    profile: Profile
    processing_consent: bool
    evidence_consent: bool = False
    remote_access_attestation: bool = False
    skill_focus: list[Literal['technical','analytical','verbal']] = Field(default_factory=lambda:['technical','analytical','verbal'], max_length=3)

    @model_validator(mode='after')
    def require_name(self):
        self.name = ' '.join(self.name.split())
        if len(self.name.split()) < 2:
            raise ValueError('First and last name are required; middle name is optional.')
        return self


class Evaluation(BaseModel):
    correctness: int = Field(ge=0, le=4, strict=True)
    reasoning: int = Field(ge=0, le=4, strict=True)
    coverage: int = Field(ge=0, le=4, strict=True)
    structure: int = Field(ge=0, le=4, strict=True)
    relevance: int = Field(ge=0, le=4, strict=True)
    evidence: list[str] = Field(min_length=1, max_length=8)
    strengths: list[str] = Field(max_length=5)
    missing_concepts: list[str] = Field(max_length=5)
    improvements: list[str] = Field(max_length=5)


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=10, max_length=1200)
    resume_basis: str = Field(max_length=1200)
    category: Literal['skill', 'project_depth', 'fundamentals']
    expected_points: list[str] = Field(min_length=1, max_length=8)


class QuestionSet(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=5, max_length=5)


class TranscriptInput(BaseModel):
    transcript: str = Field(max_length=15000)
    approved: bool = True


class Feeling(BaseModel):
    label: Literal['confident', 'tense', 'stressed', 'neutral', 'prefer_not_to_answer']
    intensity: int | None = Field(default=None, ge=1, le=5)


class FeelingsInput(BaseModel):
    feelings: list[Feeling] = Field(default_factory=list, max_length=4)
    note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def exclusive(self):
        labels = [x.label for x in self.feelings]
        if len(set(labels)) != len(labels):
            raise ValueError('Duplicate feelings.')
        if 'prefer_not_to_answer' in labels and (len(labels) != 1 or self.note or self.feelings[0].intensity is not None):
            raise ValueError('Prefer not to answer must be used alone, without intensity or notes.')
        return self


class MCQSubmission(BaseModel):
    question_id: str = Field(min_length=1,max_length=100)
    selected: list[str] = Field(max_length=20)
    timed_out: bool = False
    duration: float = Field(default=0,ge=0)


class Heartbeat(BaseModel):
    camera: bool
    microphone: bool = False
    face_count: int | None = Field(default=None,ge=0,le=100)
    page_visible: bool = False
    fullscreen: bool = False
    face_age_ms: float = Field(ge=0)
    object_age_ms: float = Field(ge=0)
    object_latency_ms: float = Field(default=999999, ge=0)
    evidence_ready: bool
    face_coverage: float = Field(ge=0, le=1)
    object_coverage: float = Field(ge=0, le=1)


class ObservationInput(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
    type: Literal['device', 'no_face', 'multiple_faces', 'page_hidden', 'tracking_unavailable', 'tab_switch', 'window_blur', 'fullscreen_exit', 'copy_attempt', 'paste_attempt', 'cut_attempt', 'context_menu', 'camera_disconnected', 'microphone_disconnected', 'background_noise', 'screen_returned', 'gaze_sample', 'gaze_violation']
    metadata: dict[str, str | float | bool] = Field(default_factory=dict, max_length=12)
    timestamp: float = Field(ge=0)
    duration: float = Field(ge=0)
    question_id: str | None = None
    stage: str = Field(max_length=40)
    label: Literal['mobile phone', 'tablet computer', 'laptop computer', 'smartwatch', 'headphones', 'second monitor', 'positive expression cue', 'tension expression cue', 'neutral expression cue', 'unclassified'] | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    box: dict[str, float] | None = None
    face_coverage: float = Field(ge=0, le=1)
    object_coverage: float = Field(ge=0, le=1)
    gaze_direction: Literal['center','left','right','up','down','off_screen'] | None = None
    eye_contact_percent: float | None = Field(default=None, ge=0, le=100)
    head_pose_angle: float | None = Field(default=None, ge=-180, le=180)


class ViolationInput(BaseModel):
    type: Literal['tab_switch','fullscreen_exit','device_detected','multiple_faces']


class ConsentInput(BaseModel):
    share: bool


class ExplanationInput(BaseModel):
    explanation: str = Field(max_length=1000)
