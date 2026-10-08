"""Local administrator bootstrap: python -m backend.app.manage create-admin"""
import argparse
import getpass
from sqlalchemy import select
from .db import DB, User, init_db
from .accounts import password_hash


def main():
    parser=argparse.ArgumentParser(description='Create the first administrator; never overwrites an existing account.')
    parser.add_argument('command',choices=['create-admin'])
    args=parser.parse_args()
    name=input('Administrator name: ').strip()
    email=input('Administrator email: ').strip().lower()
    password=getpass.getpass('Password (12+ characters): ')
    import re
    if len(name)<2 or '@' not in email or ' ' in email or not 8<=len(password)<=200 or not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$',password):
        raise SystemExit('Password must be 8+ characters with uppercase, lowercase and a number; name and email must also be valid.')
    if getpass.getpass('Confirm password: ')!=password:raise SystemExit('Passwords do not match.')
    init_db()
    with DB() as db:
        if db.scalar(select(User).where(User.email==email)):raise SystemExit('Account already exists; no changes made.')
        db.add(User(name=name,email=email,role='admin',password_hash=password_hash(password),body={}))
        db.commit()
    print('Administrator created. Use the HR / Admin login tab.')


if __name__=='__main__':main()
