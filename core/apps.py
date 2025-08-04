from django.apps import AppConfig
import atexit
# from .db_pool import DatabaseConnectionPool


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    # def ready(self):
    #     db_pool = DatabaseConnectionPool()
    #     atexit.register(db_pool.close_all_connections)
