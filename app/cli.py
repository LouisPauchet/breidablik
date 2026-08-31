"""Admin CLI for operations that can't go through the app itself — chiefly creating the very
first superuser, since registration is deliberately not public (see app/routers/admin.py).

Usage:
    python -m app.cli create-superuser --email you@example.com --password ... --display-name "You"

Inside Docker:
    docker compose exec app python -m app.cli create-superuser --email ... --password ... --display-name "..."
"""

import argparse
import asyncio

from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.exceptions import UserAlreadyExists

from app.auth.users import UserManager
from app.db import session_scope
from app.models.user import User
from app.schemas.user import UserCreate


async def create_superuser(email: str, password: str, display_name: str) -> None:
    async with session_scope() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        try:
            user = await manager.create(
                UserCreate(
                    email=email, password=password, display_name=display_name, is_superuser=True
                ),
                safe=False,
            )
        except UserAlreadyExists:
            print(f"A user with email {email} already exists.")
            return
        print(f"Created superuser {user.email} ({user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Breidablik admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser(
        "create-superuser", help="Create an admin account (e.g. the very first one)"
    )
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--password", required=True)
    create_parser.add_argument("--display-name", required=True)

    args = parser.parse_args()

    if args.command == "create-superuser":
        asyncio.run(create_superuser(args.email, args.password, args.display_name))


if __name__ == "__main__":
    main()
