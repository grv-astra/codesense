# common/db/__init__.py
# DEPRECATED during the SQLite migration. Kept only so legacy imports resolve
# until every model is ported. Removed in a later cleanup.

class _LazyCollection:
    def __getitem__(self, name):
        return self

    def __getattr__(self, name):
        raise RuntimeError(
            "MongoDBClient is deprecated; this module has been migrated to "
            "SQLite (Django ORM). Use the repository classes instead."
        )


class MongoDBClient:
    @classmethod
    def get_database(cls, db_name=None):
        return _LazyCollection()
