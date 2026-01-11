import ssl
import os
import urllib.parse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.engine import URL
from app.core.config import settings

def get_engine_settings():
    # Construct URL object directly to avoid parsing/escaping issues
    url = URL.create(
        drivername="postgresql+asyncpg",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
    )
    
    connect_args = {}
    ssl_mode = settings.DB_SSL_MODE
    ssl_root_cert = settings.DB_SSL_ROOT_CERT
    
    if ssl_mode and ssl_mode != "disable":
        if ssl_mode in ['verify-ca', 'verify-full']:
            if ssl_root_cert:
                if os.path.exists(ssl_root_cert):
                    ssl_context = ssl.create_default_context(cafile=ssl_root_cert)
                else:
                    ssl_context = ssl.create_default_context()
            else:
                ssl_context = ssl.create_default_context()
                
            if ssl_mode == 'verify-ca':
                ssl_context.check_hostname = False
            
            connect_args["ssl"] = ssl_context
        elif ssl_mode in ['require', 'prefer']:
            # asyncpg handles 'require' and 'prefer' through SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context
            
    return url, connect_args

database_url, connect_args = get_engine_settings()

engine = create_async_engine(database_url, echo=True, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
