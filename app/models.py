from typing import Optional

from database import BaseMongoCRUD, ObjectId


class BotState(BaseMongoCRUD):
    collection = "bot_states"

    @classmethod
    async def create(
            cls, user_id: str, invoice_id: str = None, item_id: str = None,
    ) -> str:
        return str(
            (
                await super().insert_one(
                    await cls.to_dict(user_id, invoice_id, item_id),
                )
            ).inserted_id
        )

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[dict]:
        return await super().find_one({"user_id": user_id})

    @classmethod
    async def edit(
            cls, user_id: str, invoice_id: str = None, item_id: str = None,
    ) -> Optional[dict]:
        return (
            await super().update_or_insert(
                {"user_id": user_id},
                await cls.to_dict(user_id, invoice_id, item_id),
            )
        )

    @classmethod
    async def to_dict(
            cls, user_id: str, invoice_id: str = None, item_id: str = None,
    ) -> dict:
        return {
            "user_id": user_id, "invoice_id": invoice_id, "item_id": item_id,
        }


class Operation(BaseMongoCRUD):
    collection = "operations"
    # status ["not_payed" | "verification" | "declined" | "accepted"]

    @classmethod
    async def create(
            cls, invoice_id: str, user_id: str, user_total: float, status: str = "not_payed",
    ) -> str:
        return str(
            (
                await super().insert_one(
                    await cls.to_dict(invoice_id, user_id, user_total, status),
                )
            ).inserted_id
        )

    @classmethod
    async def edit_status(cls, id: str, status: str = "not_payed") -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"status": status},
            )
        )

    @classmethod
    async def to_dict(
            cls,
            invoice_id: str,
            user_id: str,
            user_total: float,
            status: str = "not_payed",
    ) -> dict:
        return {
            "invoice_id": invoice_id,
            "user_id": user_id,
            "user_total": user_total,
            "status": status,
        }


class User(BaseMongoCRUD):
    collection = "users"

    @classmethod
    async def create(
            cls,
            tg_id: str,
            name: str,
            requisites: str = "",
            operations_ids: list[str] = [],
    ) -> str:
        return str(
            (
                await super().insert_one(
                    await cls.to_dict(tg_id, name, requisites, operations_ids),
                )
            ).inserted_id
        )

    @classmethod
    async def check_name_exists(cls, name: str):
        if await super().find_one({'name': name}):
            return True
        return False

    @classmethod
    async def delete(cls, id: str):
        return await super().delete_one(
            {"_id": ObjectId(str(id))},
        )


    @classmethod
    async def get_all(cls):
        return await super().find_many({})

    @classmethod
    async def find_by_tg_id(cls, tg_id: str) -> Optional[dict]:
        return await super().find_one({"tg_id": tg_id})

    @classmethod
    async def edit_requisites(cls, id: str, requisites: str = "") -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"requisites": requisites},
            )
        )

    @classmethod
    async def edit_name(cls, id: str, name: str = "") -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"name": name},
            )
        )

    @classmethod
    async def add_operation_id(cls, id: str, operation_id: str = None) -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"$addToSet": {"operations_ids": operation_id}}, with_set_option=False,
            )
        )

    @classmethod
    async def remove_operation_id(cls, id: str, operation_id: str = None) -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"$pull": {"operations_ids": operation_id}}, with_set_option=False,
            )
        )

    @classmethod
    async def to_dict(
            cls,
            tg_id: str,
            name: str = None,
            requisites: str = None,
            operations_ids: list[str] = [],
    ) -> dict:
        return {
            "tg_id": tg_id,
            "name": name,
            "requisites": requisites,
            "operations_ids": operations_ids,
        }


class Item(BaseMongoCRUD):
    collection = "items"

    @classmethod
    async def create(
            cls,
            total_price: float,
            name: str,
            details: str = "",
            users_division: dict[str, int] = dict(),
    ) -> str:
        return str(
            (
                await super().insert_one(
                    await cls.to_dict(
                        total_price,
                        name,
                        details,
                        users_division,
                    ),
                )
            ).inserted_id
        )

    @classmethod
    async def edit_user_division(cls, id: str, user_id: str, user_division: int = None) -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {f"users_division.{user_id}": user_division},
            )
        )

    @classmethod
    async def to_dict(
            cls,
            total_price: float,
            name: str,
            details: str = "",
            users_division: dict[str, int] = dict(),
    ) -> dict:
        return {
            "total_price": total_price,
            "name": name,
            "details": details,
            "users_division": users_division,
        }


class Invoice(BaseMongoCRUD):
    collection = "invoices"

    @classmethod
    async def create(
            cls,
            total_cost: float,
            owner_id: str,
            items_ids: list[str],
            users_group: list[str] = [],
            name: str = "",
            users_owe: dict[str, float] = dict(),
    ) -> str:
        return str(
            (
                await super().insert_one(
                    await cls.to_dict(
                        total_cost,
                        owner_id,
                        items_ids,
                        users_group,
                        name,
                        users_owe,
                    ),
                )
            ).inserted_id
        )

    @classmethod
    async def add_user_to_group(cls, id: str, user_id: str = None) -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"$addToSet": {"users_group": user_id}}, with_set_option=False,
            )
        )

    @classmethod
    async def remove_user_from_group(cls, id: str, user_id: str = None) -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"$pull": {"users_group": user_id}}, with_set_option=False,
            )
        )

    @classmethod
    async def edit_name(cls, id: str, name: str = "") -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {"name": name},
            )
        )

    @classmethod
    async def edit_user_owe(cls, id: str, user_id: str, user_owe: float = None) -> Optional[dict]:
        return (
            await super().update_one(
                {"_id": ObjectId(str(id))}, {f"users_owe.{user_id}": user_owe},
            )
        )

    @classmethod
    async def delete(cls, id: str):
        return (
            await super().delete_one(
                {"_id": ObjectId(str(id))},
            )
        )

    @classmethod
    async def to_dict(
            cls,
            total_cost: float,
            owner_id: str,
            items_ids: list[str],
            users_group: list[str] = [],
            name: str = "",
            users_owe: dict[str, float] = dict(),
    ) -> dict:
        return {
            "total_cost": total_cost,
            "owner_id": owner_id,
            "items_ids": items_ids,
            "users_group": users_group,
            "name": name,
            "users_owe": users_owe,
        }
