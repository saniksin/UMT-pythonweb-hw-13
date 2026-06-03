from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import and_, extract, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.schemas import ContactCreate, ContactUpdate


class ContactRepository:
    """Data-access layer for the Contact entity.

    Every query is scoped to a particular ``User`` so that users can never
    read or mutate another user's contacts.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        :param session: An open async SQLAlchemy session.
        :type session: AsyncSession
        """
        self.db = session

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
        stmt = select(Contact).where(Contact.user_id == user.id)

        text_filters = []
        if first_name:
            text_filters.append(Contact.first_name.ilike(f"%{first_name}%"))
        if last_name:
            text_filters.append(Contact.last_name.ilike(f"%{last_name}%"))
        if email:
            text_filters.append(Contact.email.ilike(f"%{email}%"))
        if text_filters:
            stmt = stmt.where(or_(*text_filters))

        stmt = stmt.order_by(Contact.id).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_contact_by_id(
        self, contact_id: int, user: User
    ) -> Contact | None:
        """Return a single contact by id, scoped to the owner.

        :param contact_id: The contact's id.
        :type contact_id: int
        :param user: The owner of the contact.
        :type user: User
        :return: The contact, or ``None`` if not found / not owned.
        :rtype: Contact | None
        """
        stmt = select(Contact).where(
            Contact.id == contact_id, Contact.user_id == user.id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        """Create a new contact owned by ``user``.

        :param body: The contact payload.
        :type body: ContactCreate
        :param user: The owner of the new contact.
        :type user: User
        :return: The created contact.
        :rtype: Contact
        """
        contact = Contact(**body.model_dump(exclude_unset=False), user_id=user.id)
        self.db.add(contact)
        await self.db.commit()
        await self.db.refresh(contact)
        return contact

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
        contact = await self.get_contact_by_id(contact_id, user)
        if contact is None:
            return None

        for key, value in body.model_dump(exclude_unset=False).items():
            setattr(contact, key, value)

        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def remove_contact(
        self, contact_id: int, user: User
    ) -> Contact | None:
        """Delete a contact owned by ``user``.

        :param contact_id: The id of the contact to delete.
        :type contact_id: int
        :param user: The owner of the contact.
        :type user: User
        :return: The deleted contact, or ``None`` if not found.
        :rtype: Contact | None
        """
        contact = await self.get_contact_by_id(contact_id, user)
        if contact is None:
            return None
        await self.db.delete(contact)
        await self.db.commit()
        return contact

    async def get_upcoming_birthdays(
        self, user: User, days: int = 7
    ) -> Sequence[Contact]:
        """Return contacts whose birthday falls within the next ``days`` days
        (inclusive of today). Year of birth is ignored — we compare only
        month/day. Scoped to the owning user.
        """
        today = date.today()
        window = [today + timedelta(days=offset) for offset in range(days)]
        month_day_pairs = [(d.month, d.day) for d in window]

        stmt = (
            select(Contact)
            .where(
                and_(
                    Contact.user_id == user.id,
                    or_(
                        *[
                            (extract("month", Contact.birthday) == month)
                            & (extract("day", Contact.birthday) == day)
                            for month, day in month_day_pairs
                        ]
                    ),
                )
            )
            .order_by(Contact.birthday)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()
