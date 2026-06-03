from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactUpdate


class ContactService:
    """Business-logic layer for contacts. All operations are scoped to the
    supplied ``User`` so tenants stay isolated.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.repository = ContactRepository(db)

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        return await self.repository.create_contact(body, user)

    async def get_contacts(
        self,
        user: User,
        skip: int,
        limit: int,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> Sequence[Contact]:
        return await self.repository.get_contacts(
            user=user,
            skip=skip,
            limit=limit,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

    async def get_contact(self, contact_id: int, user: User) -> Contact | None:
        return await self.repository.get_contact_by_id(contact_id, user)

    async def update_contact(
        self, contact_id: int, body: ContactUpdate, user: User
    ) -> Contact | None:
        return await self.repository.update_contact(contact_id, body, user)

    async def remove_contact(self, contact_id: int, user: User) -> Contact | None:
        return await self.repository.remove_contact(contact_id, user)

    async def get_upcoming_birthdays(
        self, user: User, days: int = 7
    ) -> Sequence[Contact]:
        return await self.repository.get_upcoming_birthdays(user, days=days)
