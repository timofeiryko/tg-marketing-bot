from tortoise.models import Model
from tortoise import fields, Tortoise
import asyncio

class BaseModel(Model):
    id = fields.IntField(pk=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True

class TelegramUser(BaseModel):

    telegram_id = fields.IntField()
    username = fields.CharField(max_length=255, null=True)
    first_name = fields.CharField(max_length=255, null=True)
    last_name = fields.CharField(max_length=255, null=True)
    email = fields.CharField(max_length=255, null=True)

    invited_by = fields.ForeignKeyField('backend.TelegramUser', related_name='invited_users', null=True)

    @property
    async def invited_users_count(self):
        invited_users = await self.invited_users.filter(subscription_end_date__isnull=False)
        return len(invited_users)

    has_payed_for_intensive = fields.BooleanField(default=False)


async def init():
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'backend': ['backend']}
    )
    await Tortoise.generate_schemas()

async def shutdown():
    await Tortoise.close_connections()

async def main():
    await init()
    await shutdown()

if __name__ == '__main__':
    asyncio.run(main())

