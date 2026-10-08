"""Integer minor-unit expenses and allocated settlements; balances are derived."""

from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import BigInteger, CheckConstraint, Column, ForeignKeyConstraint, UniqueConstraint
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Participant, now
from outthere.product import missing, plan_access, plan_state, version


class Expense(SQLModel, table=True):
    __table_args__ = (CheckConstraint("amount_minor > 0", name="ck_expense_amount"),)
    id: UUID = DBField(primary_key=True)
    plan_id: UUID = DBField(foreign_key="plan.id", index=True)
    payer_id: UUID = DBField(foreign_key="user.id", index=True)
    amount_minor: int = DBField(sa_column=Column(BigInteger, nullable=False))
    currency: str
    description: str
    operation_id: UUID = DBField(unique=True)
    state: str = "posted"
    replaces_id: UUID | None = DBField(default=None, foreign_key="expense.id", unique=True)
    version: int = 1
    created_at: int = DBField(default_factory=now)


class ExpenseShare(SQLModel, table=True):
    __table_args__ = (CheckConstraint("amount_minor >= 0", name="ck_share_amount"),)
    expense_id: UUID = DBField(foreign_key="expense.id", primary_key=True)
    user_id: UUID = DBField(foreign_key="user.id", primary_key=True, index=True)
    amount_minor: int = DBField(sa_column=Column(BigInteger, nullable=False))


class Settlement(SQLModel, table=True):
    __table_args__ = (CheckConstraint("amount_minor > 0", name="ck_settlement_amount"),)
    id: UUID = DBField(primary_key=True)
    plan_id: UUID = DBField(foreign_key="plan.id", index=True)
    from_user_id: UUID = DBField(foreign_key="user.id", index=True)
    to_user_id: UUID = DBField(foreign_key="user.id", index=True)
    currency: str
    amount_minor: int = DBField(sa_column=Column(BigInteger, nullable=False))
    operation_id: UUID = DBField(unique=True)
    state: str = "proposed"
    version: int = 1
    reversal_of: UUID | None = DBField(default=None, foreign_key="settlement.id", unique=True)


class Allocation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("settlement_id", "expense_id", "user_id"),
        CheckConstraint("amount_minor > 0", name="ck_allocation_amount"),
        ForeignKeyConstraint(
            ["expense_id", "user_id"],
            ["expenseshare.expense_id", "expenseshare.user_id"],
            name="fk_allocation_share",
        ),
    )
    settlement_id: UUID = DBField(foreign_key="settlement.id", primary_key=True)
    expense_id: UUID = DBField(foreign_key="expense.id", primary_key=True)
    user_id: UUID = DBField(foreign_key="user.id", primary_key=True)
    amount_minor: int = DBField(sa_column=Column(BigInteger, nullable=False))


class PlanId(Input):
    plan_id: UUID


class List(PlanId):
    after: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


class Share(Input):
    user_id: UUID
    amount_minor: int = Field(ge=0, le=10**12)


class Create(PlanId):
    expense_id: UUID
    payer_id: UUID
    amount_minor: int = Field(gt=0, le=10**12)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    description: str = Field(min_length=1, max_length=240)
    shares: list[Share] = Field(default_factory=list, max_length=100)
    equal_user_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_shares(self):
        if bool(self.shares) == bool(self.equal_user_ids):
            raise ValueError("Supply shares or equal_user_ids")
        ids = [s.user_id for s in self.shares] if self.shares else self.equal_user_ids
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate share users")
        if self.shares and sum(s.amount_minor for s in self.shares) != self.amount_minor:
            raise ValueError("Share total must equal expense")
        return self


class Correct(Create):
    replaces_id: UUID
    expected_version: int = Field(ge=1)


class Void(PlanId):
    expense_id: UUID
    expected_version: int = Field(ge=1)


class Allocate(Input):
    expense_id: UUID
    amount_minor: int = Field(gt=0, le=10**12)


class Propose(PlanId):
    settlement_id: UUID
    to_user_id: UUID
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    allocations: list[Allocate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len(set(a.expense_id for a in self.allocations)) != len(self.allocations):
            raise ValueError("Duplicate obligations")
        return self


class Remind(PlanId):
    expense_id: UUID
    user_id: UUID


class SettlementEdit(PlanId):
    settlement_id: UUID
    expected_version: int = Field(ge=1)


class Reverse(SettlementEdit):
    reversal_id: UUID


CONTRACTS = {
    "expense.list": ("query", List),
    "expense.create": ("command", Create),
    "expense.correct": ("command", Correct),
    "expense.void": ("command", Void),
    "balance.list": ("query", PlanId),
    "split.remind": ("command", Remind),
    "settlement.propose": ("command", Propose),
    "settlement.confirm": ("command", SettlementEdit),
    "settlement.reject": ("command", SettlementEdit),
    "settlement.reverse": ("command", Reverse),
}


def allocated(db, expense_id, user_id):
    return sum(
        a.amount_minor
        for a in db.exec(
            select(Allocation)
            .join(Settlement)
            .where(
                Allocation.expense_id == expense_id,
                Allocation.user_id == user_id,
                Settlement.state == "confirmed",
            )
        ).all()
    )


def change(db, plan_id):
    users = set(db.exec(select(Participant.user_id).where(Participant.plan_id == plan_id)).all())
    users.update(
        db.exec(select(ExpenseShare.user_id).join(Expense).where(Expense.plan_id == plan_id)).all()
    )
    for expense in db.exec(select(Expense).where(Expense.plan_id == plan_id)).all():
        emit(db, users, "v2.expense", expense.id)
    for settlement in db.exec(select(Settlement).where(Settlement.plan_id == plan_id)).all():
        emit(db, {settlement.from_user_id, settlement.to_user_id}, "v2.settlement", settlement.id)


def expense_view(db, expense, viewer, host):
    shares = db.exec(
        select(ExpenseShare)
        .where(ExpenseShare.expense_id == expense.id)
        .order_by(ExpenseShare.user_id)
    ).all()
    # A debtor sees their own obligation, payer and host see the full expense.
    visible = (
        shares if viewer in {expense.payer_id, host} else [s for s in shares if s.user_id == viewer]
    )
    return {
        "id": str(expense.id),
        "plan_id": str(expense.plan_id),
        "payer_id": str(expense.payer_id),
        "amount_minor": expense.amount_minor,
        "currency": expense.currency,
        "description": expense.description,
        "state": expense.state,
        "version": expense.version,
        "replaces_id": str(expense.replaces_id) if expense.replaces_id else None,
        "shares": [
            {
                "user_id": str(s.user_id),
                "amount_minor": s.amount_minor,
                "settled_minor": allocated(db, expense.id, s.user_id),
            }
            for s in visible
        ],
    }


def own_plan(db, user_id, plan_id):
    from outthere.models import Plan

    plan = db.get(Plan, plan_id)
    if plan is None:
        missing("Plan")
    if db.get(Participant, (plan_id, user_id)) or plan.host_id == user_id:
        return plan
    share = db.exec(
        select(ExpenseShare)
        .join(Expense)
        .where(Expense.plan_id == plan_id, ExpenseShare.user_id == user_id)
    ).first()
    paid = db.exec(
        select(Expense).where(Expense.plan_id == plan_id, Expense.payer_id == user_id)
    ).first()
    if share is None and paid is None:
        missing("Plan")
    return plan


def balances(db, user_id, plan_id):
    plan = own_plan(db, user_id, plan_id)
    positions = {}
    for expense in db.exec(
        select(Expense).where(Expense.plan_id == plan_id, Expense.state == "posted")
    ).all():
        for share in db.exec(
            select(ExpenseShare).where(ExpenseShare.expense_id == expense.id)
        ).all():
            remaining = share.amount_minor - allocated(db, expense.id, share.user_id)
            if share.user_id == expense.payer_id or not remaining:
                continue
            for person, delta in [(share.user_id, -remaining), (expense.payer_id, remaining)]:
                key = (person, expense.currency)
                positions[key] = positions.get(key, 0) + delta
    return {
        "plan_id": str(plan_id),
        "items": [
            {"user_id": str(person), "currency": currency, "net_minor": amount}
            for (person, currency), amount in sorted(
                positions.items(), key=lambda item: str(item[0])
            )
            if person == user_id or plan.host_id == user_id
        ],
    }


def handle(db, user, name, data, action_id=None):
    if name == "split.remind":
        plan = own_plan(db, user.id, data.plan_id)
        expense = db.get(Expense, data.expense_id)
        share = db.get(ExpenseShare, (data.expense_id, data.user_id))
        if (
            not expense
            or expense.plan_id != plan.id
            or not share
            or user.id not in {expense.payer_id, plan.host_id}
        ):
            missing("Obligation")
        if (
            expense.state != "posted"
            or data.user_id == expense.payer_id
            or share.amount_minor <= allocated(db, expense.id, share.user_id)
        ):
            raise AppError("invalid_input", "No outstanding obligation")
        from outthere.models import Device
        from outthere.push import enqueue

        for device in db.exec(
            select(Device).where(Device.user_id == data.user_id, Device.revoked_at.is_(None))
        ).all():
            enqueue(db, device, "splits", expense.id, f"push.split:{action_id}:{device.id}")
        return {"queued": True}
    if name == "balance.list":
        return balances(db, user.id, data.plan_id)
    if name == "expense.list":
        plan = own_plan(db, user.id, data.plan_id)
        statement = select(Expense).where(Expense.plan_id == plan.id)
        if user.id != plan.host_id:
            own = select(ExpenseShare.expense_id).where(ExpenseShare.user_id == user.id)
            statement = statement.where((Expense.payer_id == user.id) | Expense.id.in_(own))
        if data.after:
            statement = statement.where(Expense.id > data.after)
        rows = db.exec(statement.order_by(Expense.id).limit(data.limit + 1)).all()
        return {
            "items": [expense_view(db, e, user.id, plan.host_id) for e in rows[: data.limit]],
            "next_after": str(rows[data.limit - 1].id) if len(rows) > data.limit else None,
        }
    if name.startswith("expense."):
        plan = plan_access(db, user.id, data.plan_id)
        if name in {"expense.correct", "expense.void"}:
            old_id = data.replaces_id if name.endswith("correct") else data.expense_id
            old = db.get(Expense, old_id)
            if old is None or old.plan_id != plan.id:
                missing("Expense")
            if user.id not in {old.payer_id, plan.host_id}:
                raise AppError("forbidden", "Only payer or host can change expenses", 403)
            version(old, data.expected_version)
            if old.state != "posted":
                raise AppError("version_conflict", "Expense is no longer posted", 409)
            if any(
                allocated(db, old.id, s.user_id)
                for s in db.exec(
                    select(ExpenseShare).where(ExpenseShare.expense_id == old.id)
                ).all()
            ):
                raise AppError("version_conflict", "Reverse settlements before correcting", 409)
            old.state, old.version = (
                "superseded" if name.endswith("correct") else "void",
                old.version + 1,
            )
            if name.endswith("void"):
                change(db, plan.id)
                return {"expense_id": str(old.id), "state": old.state, "version": old.version}
        if user.id not in {data.payer_id, plan.host_id}:
            raise AppError("forbidden", "Only payer or host can add expenses", 403)
        if data.currency != plan_state(db, plan.id).currency:
            raise AppError("invalid_input", "Expense currency must match plan")
        if db.get(Expense, data.expense_id):
            raise AppError("action_conflict", "Expense ID already exists", 409)
        shares = data.shares
        if data.equal_user_ids:
            ids = sorted(data.equal_user_ids, key=str)
            quotient, remainder = divmod(data.amount_minor, len(ids))
            shares = [
                Share(user_id=person, amount_minor=quotient + (i < remainder))
                for i, person in enumerate(ids)
            ]
        for person in {data.payer_id} | {s.user_id for s in shares}:
            if not db.get(Participant, (plan.id, person)):
                missing("Participant")
        expense = Expense(
            id=data.expense_id,
            plan_id=plan.id,
            payer_id=data.payer_id,
            amount_minor=data.amount_minor,
            currency=data.currency,
            description=data.description,
            operation_id=action_id,
            replaces_id=data.replaces_id if name.endswith("correct") else None,
        )
        db.add(expense)
        db.flush()
        for share in shares:
            db.add(
                ExpenseShare(
                    expense_id=expense.id, user_id=share.user_id, amount_minor=share.amount_minor
                )
            )
        db.flush()
        change(db, plan.id)
        return expense_view(db, expense, user.id, plan.host_id)
    plan = own_plan(db, user.id, data.plan_id)
    if name == "settlement.propose":
        if data.to_user_id == user.id:
            raise AppError("invalid_input", "Cannot settle with yourself")
        if db.get(Settlement, data.settlement_id):
            raise AppError("action_conflict", "Settlement ID already exists", 409)
        settlement = Settlement(
            id=data.settlement_id,
            plan_id=plan.id,
            from_user_id=user.id,
            to_user_id=data.to_user_id,
            currency=data.currency,
            amount_minor=sum(a.amount_minor for a in data.allocations),
            operation_id=action_id,
        )
        db.add(settlement)
        db.flush()
        for allocation in data.allocations:
            check_allocation(db, settlement, allocation.expense_id, allocation.amount_minor)
            db.add(
                Allocation(
                    settlement_id=settlement.id,
                    expense_id=allocation.expense_id,
                    user_id=user.id,
                    amount_minor=allocation.amount_minor,
                )
            )
    else:
        settlement = db.get(Settlement, data.settlement_id)
        if (
            settlement is None
            or settlement.plan_id != plan.id
            or user.id not in {settlement.from_user_id, settlement.to_user_id}
        ):
            missing("Settlement")
        version(settlement, data.expected_version)
        if name == "settlement.confirm":
            if user.id != settlement.to_user_id:
                raise AppError("forbidden", "The recipient confirms receipt", 403)
            if settlement.state != "proposed":
                raise AppError("version_conflict", "Settlement is no longer proposed", 409)
            for allocation in db.exec(
                select(Allocation).where(Allocation.settlement_id == settlement.id)
            ).all():
                check_allocation(db, settlement, allocation.expense_id, allocation.amount_minor)
            settlement.state = "confirmed"
        elif name == "settlement.reject":
            if settlement.state != "proposed":
                raise AppError("version_conflict", "Settlement is no longer proposed", 409)
            settlement.state = "rejected"
        else:
            if user.id != settlement.to_user_id or settlement.state != "confirmed":
                raise AppError("forbidden", "Recipient can reverse a confirmed settlement", 403)
            if db.get(Settlement, data.reversal_id):
                raise AppError("action_conflict", "Reversal ID already exists", 409)
            db.add(
                Settlement(
                    id=data.reversal_id,
                    plan_id=plan.id,
                    from_user_id=settlement.to_user_id,
                    to_user_id=settlement.from_user_id,
                    currency=settlement.currency,
                    amount_minor=settlement.amount_minor,
                    operation_id=action_id,
                    state="reversal",
                    reversal_of=settlement.id,
                )
            )
            settlement.state = "reversed"
        settlement.version += 1
    db.flush()
    change(db, plan.id)
    return {
        "settlement_id": str(settlement.id),
        "state": settlement.state,
        "version": settlement.version,
        "amount_minor": settlement.amount_minor,
        "currency": settlement.currency,
    }


def check_allocation(db, settlement, expense_id, amount):
    expense = db.get(Expense, expense_id)
    share = db.get(ExpenseShare, (expense_id, settlement.from_user_id))
    if expense is None or share is None or expense.plan_id != settlement.plan_id:
        missing("Obligation")
    if (
        expense.state != "posted"
        or expense.payer_id != settlement.to_user_id
        or expense.currency != settlement.currency
    ):
        raise AppError("invalid_input", "Allocation does not match the obligation")
    if amount > share.amount_minor - allocated(db, expense_id, settlement.from_user_id):
        raise AppError("version_conflict", "Allocation exceeds remaining obligation", 409)


def settlement_view(db, row):
    return {
        "id": str(row.id),
        "plan_id": str(row.plan_id),
        "from_user_id": str(row.from_user_id),
        "to_user_id": str(row.to_user_id),
        "currency": row.currency,
        "amount_minor": row.amount_minor,
        "state": row.state,
        "version": row.version,
        "reversal_of": str(row.reversal_of) if row.reversal_of else None,
        "allocations": [
            {
                "expense_id": str(a.expense_id),
                "user_id": str(a.user_id),
                "amount_minor": a.amount_minor,
            }
            for a in db.exec(select(Allocation).where(Allocation.settlement_id == row.id)).all()
        ],
    }
