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
        """Initialize the service with a database session.

        :param db: An open async SQLAlchemy session.
        :type db: AsyncSession
        """
        self.repository = ContactRepository(db)

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        """Create a new contact for ``user``.

        :param body: The contact payload.
        :type body: ContactCreate
        :param user: The owner of the new contact.
        :type user: User
        :return: The created contact.
        :rtype: Contact
        """
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
        """Return a page of the user's contacts, optionally filtered.

        :param user: The owner of the contacts.
        :type user: User
        :param skip: Number of rows to skip (offset).
        :type skip: int
        :param limit: Maximum number of rows to return.
        :type limit: int
        :param first_name: Optional case-insensitive first-name filter.
        :type first_name: str | None
        :param last_name: Optional case-insensitive last-name filter.
        :type last_name: str | None
        :param email: Optional case-insensitive email filter.
        :type email: str | None
        :return: The matching contacts.
        :rtype: Sequence[Contact]
        """
        return await self.repository.get_contacts(
            user=user,
            skip=skip,
            limit=limit,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

    async def get_contact(self, contact_id: int, user: User) -> Contact | None:
        """Return a single contact owned by ``user`` (or ``None``).

        :param contact_id: The contact's id.
        :type contact_id: int
        :param user: The owner of the contact.
        :type user: User
        :return: The contact, or ``None`` if not found.
        :rtype: Contact | None
        """
        return await self.repository.get_contact_by_id(contact_id, user)

    async def update_contact(
        self, contact_id: int, body: ContactUpdate, user: User
    ) -> Contact | None:
        """Update a contact owned by ``user``.

        :param contact_id: The id of the contact to update.
        :type contact_id: int
        :param body: The new contact data.
        :type body: ContactUpdate
        :param user: The owner of the contact.
        :type user: User
        :return: The updated contact, or ``None`` if not found.
        :rtype: Contact | None
        """
        return await self.repository.update_contact(contact_id, body, user)

    async def remove_contact(self, contact_id: int, user: User) -> Contact | None:
        """Delete a contact owned by ``user``.

        :param contact_id: The id of the contact to delete.
        :type contact_id: int
        :param user: The owner of the contact.
        :type user: User
        :return: The deleted contact, or ``None`` if not found.
        :rtype: Contact | None
        """
        return await self.repository.remove_contact(contact_id, user)

    async def get_upcoming_birthdays(
        self, user: User, days: int = 7
    ) -> Sequence[Contact]:
        """Return the user's contacts with a birthday in the next ``days`` days.

        :param user: The owner of the contacts.
        :type user: User
        :param days: Size of the look-ahead window in days.
        :type days: int
        :return: The matching contacts.
        :rtype: Sequence[Contact]
        """
        return await self.repository.get_upcoming_birthdays(user, days=days)
