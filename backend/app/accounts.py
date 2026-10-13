from .email_delivery import configured as email_configured
import hashlib
import hmac
import secrets
import time
import smtplib
from email.message import EmailMessage
from contextvars import ContextVar
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import DB, User, LoginSession, Recovery, Organization, Recruiter
from .config import settings

actor: ContextVar[User | None] = ContextVar('actor', default=None)
router=APIRouter(prefix='/api/auth')

def hashed(value): return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password):
    salt=secrets.token_hex(16)
    value=hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
    return salt+':'+value
def password_matches(password, encoded):
    salt,value=encoded.split(':')
    return hmac.compare_digest(hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex(),value)
def blocked(user):
    until=user.body.get('blocked_until')
    return user.body.get('blocked',False) and (until is None or until>time.time())
def require_user(*roles):
    user=actor.get()
    if not user: raise HTTPException(401,'Please sign in.')
    if blocked(user): raise HTTPException(403,'Your account has been blocked from accessing examinations. Please contact the administrator.')
    if roles and user.role not in roles: raise HTTPException(403,'This account is not authorized for this area.')
    return user
def organization_scope(user=None):
    user=user or require_user('hr','admin')
    if user.role not in ('hr','admin'):raise HTTPException(403,'Recruiter account required.')
    with DB() as db:
        membership=db.get(Recruiter,user.id)
        if not membership:raise HTTPException(403,'This recruiter has no organization.')
        return membership.organization_id

def organization_recruiters(user):
    org=organization_scope(user)
    with DB() as db:return list(db.scalars(select(Recruiter.user_id).where(Recruiter.organization_id==org)))

def public(user):
    result={'id':user.id,'name':user.name,'email':user.email,'role':user.role}
    if user.role in ('hr','admin'):
        with DB() as db:
            membership=db.get(Recruiter,user.id)
            if membership:
                result.update(organization_id=membership.organization_id,organization_name=db.get(Organization,membership.organization_id).name)
    return result

def send_recovery_email(user, token):
    from .email_delivery import configured, send_message
    if not configured():return False
    link=f'{settings.public_url.rstrip("/")}/?reset={token}'
    message=EmailMessage()
    message['Subject']='Reset your AI Interviewer password'
    message['From']=settings.email_from if settings.email_provider=='brevo' else settings.smtp_from
    message['To']=user.email
    message.set_content(f'''Hello {user.name},\n\nUse this link to reset your AI Interviewer password:\n{link}\n\nThis link expires in 30 minutes and can only be used once. If you did not request this, you can ignore this email.\n''')
    send_message(message)
    return True

class RegisterInput(BaseModel):
    company_name: str = Field(default='',max_length=180)
    email: str = Field(min_length=3,max_length=200)
    name: str = Field(min_length=2,max_length=150)
    password: str = Field(min_length=8,max_length=200)
    area: str = 'candidate'
    @field_validator('password')
    @classmethod
    def strong_password(cls,value):
        if not any(c.islower() for c in value) or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError('Password must include uppercase, lowercase, and a number.')
        return value
class LoginInput(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    area: str = 'candidate'
class ForgotInput(BaseModel):
    email: str = Field(max_length=200)
class ResetInput(BaseModel):
    token: str = Field(min_length=32,max_length=150)
    password: str = Field(min_length=8,max_length=200)
    @field_validator('password')
    @classmethod
    def strong_password(cls,value):
        if not any(c.islower() for c in value) or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError('Password must include uppercase, lowercase, and a number.')
        return value

def issue_login(db,user,response):
    token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32)
    db.add(LoginSession(id=hashed(token),user_id=user.id,csrf=hashed(csrf),expires=time.time()+8*3600));db.commit()
    secure=settings.environment=='production'
    response.set_cookie('interview_auth',token,max_age=8*3600,httponly=True,secure=secure,samesite='strict',path='/')
    response.set_cookie('interview_csrf',csrf,max_age=8*3600,httponly=False,secure=secure,samesite='strict',path='/')
    return public(user)

@router.post('/register')
def register(data:RegisterInput,response:Response):
    email=data.email.strip().lower()
    if '@' not in email or ' ' in email: raise HTTPException(422,'Enter a valid email address.')
    with DB() as db:
        if data.area not in ['candidate','hr']: raise HTTPException(422,'Invalid account type.')
        user=User(email=email,name=data.name.strip(),password_hash=password_hash(data.password),role=data.area,body={})
        db.add(user)
        try:db.flush()
        except IntegrityError:raise HTTPException(409,'An account already exists. Sign in or request password recovery.')
        if data.area=='hr':
            org=Organization(name=data.company_name.strip() or data.name.strip()+' organization');db.add(org);db.flush()
            db.add(Recruiter(user_id=user.id,organization_id=org.id))
            user.role='admin'
        try: db.commit()
        except IntegrityError: raise HTTPException(409,'An account already exists. Sign in or request password recovery.')
        return issue_login(db,user,response)

@router.post('/login')
def login(data:LoginInput,response:Response):
    with DB() as db:
        user=db.scalar(select(User).where(User.email==data.email.strip().lower()))
        # Equal-cost work for unknown accounts.
        if not user:
            password_hash(data.password);raise HTTPException(401,'Email or password is incorrect.')
        if not password_matches(data.password,user.password_hash): raise HTTPException(401,'Email or password is incorrect.')
        if blocked(user): raise HTTPException(403,'Your account has been blocked from accessing examinations. Please contact the administrator.')
        if (data.area=='hr') != (user.role in ['hr','admin']):
            expected = 'HR / Admin' if user.role in ['hr','admin'] else 'Candidate / Practice'
            raise HTTPException(403, f'This account is registered for {expected}. Select that login area or create an account for the other role.')
        return issue_login(db,user,response)

@router.get('/me')
def me(): return public(require_user())

@router.post('/logout')
def logout(response:Response):
    # Cookie deletion plus middleware revocation of the presented login session.
    response.delete_cookie('interview_auth',path='/');response.delete_cookie('interview_csrf',path='/')
    return {'signed_out':True}

@router.post('/forgot-password')
def forgot(data:ForgotInput):
    with DB() as db:
        user=db.scalar(select(User).where(User.email==data.email.strip().lower()))
        if user:
            pending=db.scalars(select(Recovery).where(Recovery.user_id==user.id)).all()
            if not any(r.body.get('requested_at',0)>time.time()-3600 for r in pending):
                token=secrets.token_urlsafe(40)
                row=Recovery(user_id=user.id,body={'requested_at':time.time(),'status':'issued','token_hash':hashed(token),'expires':time.time()+1800,'delivery':'email' if email_configured() else 'admin'})
                db.add(row);db.commit()
                try:
                    if send_recovery_email(user,token):
                        return {'message':'If this account exists, a password reset link has been sent to its email address. Check your inbox and spam folder.'}
                except Exception:
                    row.body=row.body|{'status':'requested','delivery_error':True};db.commit()
    return {'message':'If this account exists, a password reset link has been requested. If email delivery is unavailable, contact your administrator.'}

@router.post('/reset-password')
def reset(data:ResetInput):
    with DB() as db:
        row=next((r for r in db.scalars(select(Recovery)) if r.body.get('token_hash')==hashed(data.token) and r.body.get('expires',0)>time.time() and r.body.get('status')=='issued'),None)
        if not row: raise HTTPException(400,'Reset link is invalid, expired or already used.')
        user=db.get(User,row.user_id);user.password_hash=password_hash(data.password)
        row.body=row.body|{'status':'used','token_hash':None}
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id));db.commit()
    return {'message':'Password updated. Sign in with your new password.'}
