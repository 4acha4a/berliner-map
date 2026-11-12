from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.db import Base
from app.models import OccupationSector  # noqa: F401

config = context.config
target_metadata = Base.metadata


def offline():
    context.configure(url=get_settings().database_url.get_secret_value(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def online():
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(connection=supplied_connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(get_settings().database_url.get_secret_value(), poolclass=pool.NullPool, echo=False, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    offline()
else:
    online()
