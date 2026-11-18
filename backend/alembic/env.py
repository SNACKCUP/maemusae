from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.auth.models
import app.codes.models
import app.features.maemusae.ai_keys.models
import app.features.maemusae.analysis.models
import app.features.maemusae.documents.models
import app.features.maemusae.invitations.models
import app.features.maemusae.projects.models
import app.features.maemusae.review.models
import app.features.maemusae.versions.models
import app.social.models
import app.users.models  # noqa: F401
from alembic import context
from app.core.config import settings
from app.core.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# disable_existing_loggers=False: 기본값(True)이면 이미 만들어진 app.* 로거(위 import 로 생긴 app.crypto 등)가 꺼져서,
# 같은 프로세스에서 마이그레이션을 돌리는 pytest 에서 그 로그가 사라집니다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
