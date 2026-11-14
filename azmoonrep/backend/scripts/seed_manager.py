"""Create or update the manager (admin) account. Run once:
    python -m scripts.seed_manager [username]
The password is always asked interactively (at least 10 characters), never passed
on the command line, so it does not end up in shell history.
"""
import getpass
import os
import sys
import datetime as dt
from app import db, auth

MIN_LEN = 10

def main():
    username = sys.argv[1] if len(sys.argv) > 1 else input("username [manager]: ") or "manager"
    # non-interactive (provisioning): MANAGER_PASSWORD from the environment / .env
    password = os.getenv("MANAGER_PASSWORD")
    if password:
        if len(password) < MIN_LEN:
            sys.exit(f"MANAGER_PASSWORD too short (min {MIN_LEN} characters)")
    else:
        password = getpass.getpass(f"password (min {MIN_LEN} chars): ")
        if len(password) < MIN_LEN:
            sys.exit(f"password too short (min {MIN_LEN} characters)")
        if getpass.getpass("repeat password: ") != password:
            sys.exit("passwords do not match")
    db.db.users.update_one(
        {"username": username},
        {"$set": {"username": username,
                  "password_hash": auth.hash_password(password),
                  "role": "admin",
                  "display_name": "Manager",
                  "updated_at": dt.datetime.utcnow()}},
        upsert=True)
    print(f"admin account ready: {username}")

if __name__ == "__main__":
    main()
