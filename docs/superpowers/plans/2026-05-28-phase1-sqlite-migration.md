# Phase 1 — SQLite Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the MongoDB/pymongo data layer with an embedded SQLite (Django ORM) layer, preserving every model class's public method signatures and JSON response shapes so views, serializers, and the scanner are untouched in behaviour.

**Architecture:** Each Django app gets real ORM models (in its `models/` package). The existing document-style classes (`UserModel`, `ProjectModel`, `ScanModel`, `FindingModel`, `SbomModel`, `PermissionModel`) are rewritten as thin repositories over those ORM models, returning the same dicts they return today. Mongo-specific concerns (`ObjectId`, `.collection` access, aggregation pipelines) are removed and replaced with ORM queries. References between entities stay loosely coupled as UUID-hex strings (no FKs), matching today's behaviour.

**Tech Stack:** Django 5.2 ORM, SQLite (JSON1), Django's built-in test runner (`manage.py test`). No new third-party dependencies; `pymongo`/`bson` are removed at the end.

**Plan series:** This is **plan 1 of 7** from the spec `docs/superpowers/specs/2026-05-28-windows-offline-tauri-packaging-design.md` (§16). It must produce a working, test-passing Django backend on SQLite on its own. Later plans: 2 Offline AI, 3 Offline SBOM, 4 Offline licensing, 5 Frontend, 6 Tauri shell, 7 Packaging.

---

## File Structure

**Create:**
- `server/common/orm.py` — `UUIDModel` abstract base (uuid-hex string PK).
- `server/local/auth_app/models/orm.py` — `User`, `RolePermission` ORM models.
- `server/local/auth_app/migrations/__init__.py` + generated migration.
- `server/local/api_app/models/orm.py` — `Project`, `Scan`, `Finding`, `SbomScan`, `SbomFinding`, `SbomLicenseFinding` ORM models.
- `server/local/api_app/migrations/__init__.py` + generated migration.
- `server/local/auth_app/tests/__init__.py`, `server/local/auth_app/tests/test_user_model.py`, `.../test_permission_model.py`
- `server/local/api_app/tests/__init__.py`, `.../test_project_model.py`, `.../test_scan_model.py`, `.../test_finding_model.py`, `.../test_sbom_model.py`, `.../test_dashboard.py`
- `server/local/auth_app/services/setup.py` — first-run admin/permission seeding (backend half of spec §9).
- `server/local/auth_app/views/setup_views.py` — `GET/POST /api/auth/setup/`.

**Modify (rewrite internals, keep public API):**
- `server/codesense/settings.py` — `DATABASES` (SQLite), data-dir path, drop `common.db` app.
- `server/common/db/__init__.py` — make the Mongo client lazy during migration, then remove at the end.
- `server/local/auth_app/models/user_model.py`, `.../permission_model.py`
- `server/local/api_app/models/project_models.py`, `.../scan_models.py`, `.../finding_models.py`, `.../sbom_models.py`
- `server/local/api_app/models/__init__.py`, `server/local/auth_app/models/__init__.py` — import ORM classes so Django discovers them.
- `server/local/api_app/views/project_views.py` — drop `ObjectId`.
- `server/local/api_app/views/dashboard_views.py` — ORM aggregations.
- `server/scanner/rag/progress.py` — ORM update instead of Mongo.
- `server/scanner/rag/extract.py` — pass string ids, drop unknown keys.
- `server/scanner/services/sbom_pipeline.py` — use repo insert methods, drop `ObjectId`.
- `server/local/auth_app/utils/account_integrity.py` — replace `.collection` access.
- `server/local/auth_app/urls/__init__.py` — register setup route.
- `server/requirements.txt` — remove `pymongo`.

---

## Task 1: SQLite settings, data dir, and UUID base model

**Files:**
- Modify: `server/codesense/settings.py`
- Create: `server/common/orm.py`
- Modify: `server/common/db/__init__.py`

- [ ] **Step 1: Configure SQLite and the data directory in settings**

In `server/codesense/settings.py`, replace the empty `DATABASES = {}` block (lines ~85-89, the `DATABASES`, `MONGO_URI`, `MONGO_DB_NAME` lines) with:

```python
# Per-user writable data directory (overridable by the desktop launcher).
DATA_DIR = Path(os.getenv("CODESENSE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DATA_DIR / "app.sqlite3"),
    }
}
```

- [ ] **Step 2: Remove `common.db` from INSTALLED_APPS**

In `server/codesense/settings.py`, delete the line `'common.db',` from `INSTALLED_APPS` (it holds no ORM models). Keep `local.auth_app`, `local.api_app`, `scanner`, `licenses`, `corsheaders`.

- [ ] **Step 3: Make the legacy Mongo client lazy so imports don't connect**

During the migration, not-yet-rewritten modules still import `MongoDBClient`. Replace `server/common/db/__init__.py` entirely with a lazy stub (no network on import):

```python
# common/db/__init__.py
# DEPRECATED during the SQLite migration. Kept only so legacy imports resolve
# until every model is ported. Removed in the final cleanup task.

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
```

- [ ] **Step 4: Create the UUID base model**

Create `server/common/orm.py`:

```python
import uuid
from django.db import models


def new_uuid_hex() -> str:
    return uuid.uuid4().hex


class UUIDModel(models.Model):
    """Abstract base: 32-char uuid-hex string primary key, exposed as `id`."""

    id = models.CharField(primary_key=True, max_length=32, default=new_uuid_hex, editable=False)

    class Meta:
        abstract = True
```

- [ ] **Step 5: Verify settings load**

Run: `cd server && python manage.py check`
Expected: `System check identified no issues (0 silenced).` (No DB connection errors; Mongo no longer contacted.)

- [ ] **Step 6: Commit**

```bash
git add server/codesense/settings.py server/common/orm.py server/common/db/__init__.py
git commit -m "feat(db): configure SQLite, data dir, and UUID base model"
```

---

## Task 2: auth_app ORM models + migration

**Files:**
- Create: `server/local/auth_app/models/orm.py`
- Modify: `server/local/auth_app/models/__init__.py`
- Create: `server/local/auth_app/migrations/__init__.py`

- [ ] **Step 1: Create the ORM models**

Create `server/local/auth_app/models/orm.py`:

```python
from django.db import models
from common.orm import UUIDModel


class User(UUIDModel):
    email = models.CharField(max_length=255, db_index=True)
    password = models.CharField(max_length=255)
    name = models.CharField(max_length=255, blank=True, default="")
    company = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=50, default="User")
    deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "auth_app"
        db_table = "users"


class RolePermission(models.Model):
    role = models.CharField(max_length=50, unique=True)
    permissions = models.JSONField(default=dict)
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "auth_app"
        db_table = "permissions"
```

- [ ] **Step 2: Make Django discover the models**

Edit `server/local/auth_app/models/__init__.py` to add at the top (preserve any existing re-exports):

```python
from local.auth_app.models.orm import User, RolePermission  # noqa: F401
```

- [ ] **Step 3: Create the migrations package**

Create empty file `server/local/auth_app/migrations/__init__.py` (no contents).

- [ ] **Step 4: Generate and apply the migration**

Run:
```bash
cd server && python manage.py makemigrations auth_app && python manage.py migrate
```
Expected: `Migrations for 'auth_app':` listing a `0001_initial.py`, then `Applying auth_app.0001_initial... OK`.

- [ ] **Step 5: Commit**

```bash
git add server/local/auth_app/models/orm.py server/local/auth_app/models/__init__.py server/local/auth_app/migrations/
git commit -m "feat(auth): add User and RolePermission ORM models"
```

---

## Task 3: Rewrite UserModel + PermissionModel repositories

**Files:**
- Modify: `server/local/auth_app/models/user_model.py`
- Modify: `server/local/auth_app/models/permission_model.py`
- Test: `server/local/auth_app/tests/test_user_model.py`, `.../test_permission_model.py`

- [ ] **Step 1: Write failing tests**

Create `server/local/auth_app/tests/__init__.py` (empty), then `server/local/auth_app/tests/test_user_model.py`:

```python
from django.test import TestCase
from local.auth_app.models.user_model import UserModel


class UserModelTests(TestCase):
    def test_create_returns_serialized_user(self):
        user = UserModel.create_user(
            email="a@x.com", hashed_password="h", name="Ann", company="X", role="Admin"
        )
        self.assertEqual(user["email"], "a@x.com")
        self.assertEqual(user["role"], "Admin")
        self.assertFalse(user["deleted"])
        self.assertIn("id", user)
        self.assertIsNotNone(user["created_at"])

    def test_find_by_email_returns_raw_doc_with_password_and_id(self):
        UserModel.create_user(email="b@x.com", hashed_password="secret", name="B")
        raw = UserModel.find_by_email("b@x.com")
        self.assertEqual(raw["password"], "secret")
        self.assertEqual(raw["email"], "b@x.com")
        self.assertIn("_id", raw)
        self.assertEqual(raw["role"], "User")

    def test_find_by_email_excludes_deleted(self):
        UserModel.create_user(email="c@x.com", hashed_password="h", name="C", deleted=True)
        self.assertIsNone(UserModel.find_by_email("c@x.com"))

    def test_find_by_id_serializes_and_find_raw_by_id_is_raw(self):
        created = UserModel.create_user(email="d@x.com", hashed_password="h", name="D")
        uid = created["id"]
        self.assertEqual(UserModel.find_by_id(uid)["email"], "d@x.com")
        self.assertEqual(UserModel.find_raw_by_id(uid)["password"], "h")
        self.assertIsNone(UserModel.find_by_id("nonexistent"))

    def test_update_user_sets_fields_and_updated_at(self):
        created = UserModel.create_user(email="e@x.com", hashed_password="h", name="E")
        updated = UserModel.update_user(created["id"], {"name": "E2"})
        self.assertEqual(updated["name"], "E2")

    def test_find_all_pagination_and_manager_excludes_admin(self):
        UserModel.create_user(email="m@x.com", hashed_password="h", name="M", role="manager")
        UserModel.create_user(email="ad@x.com", hashed_password="h", name="Ad", role="admin")
        as_manager = UserModel.find_all(page=1, limit=10, role="manager")
        emails = [u["email"] for u in as_manager["users"]]
        self.assertIn("m@x.com", emails)
        self.assertNotIn("ad@x.com", emails)
        self.assertEqual(as_manager["pagination"]["page"], 1)

    def test_exists_counts_regardless_of_deleted(self):
        UserModel.create_user(email="f@x.com", hashed_password="h", name="F", deleted=True)
        self.assertTrue(UserModel.exists("f@x.com"))
        self.assertFalse(UserModel.exists("none@x.com"))

    def test_delete_user_hard_deletes(self):
        created = UserModel.create_user(email="g@x.com", hashed_password="h", name="G")
        UserModel.delete_user(created["id"])
        self.assertIsNone(UserModel.find_raw_by_id(created["id"]))

    def test_find_protected_returns_raw_docs(self):
        UserModel.create_user(email="p@x.com", hashed_password="h", name="P", role="admin")
        rows = UserModel.find_protected(["admin", "manager", "user"])
        self.assertEqual(rows[0]["email"], "p@x.com")
        self.assertIn("_id", rows[0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python manage.py test local.auth_app.tests.test_user_model -v 2`
Expected: FAIL (current `UserModel` still references the lazy Mongo stub / `RuntimeError`).

- [ ] **Step 3: Rewrite UserModel as an ORM repository**

Replace `server/local/auth_app/models/user_model.py` entirely:

```python
from datetime import datetime, timezone
from local.auth_app.models.orm import User


def _iso(dt):
    return dt.isoformat() if dt else None


class UserModel:
    @staticmethod
    def serialize_user(user):
        """Accepts an ORM User or a raw dict; returns the public user dict."""
        if user is None:
            return None
        if isinstance(user, dict):
            return {
                "id": str(user.get("_id") or user.get("id")),
                "email": user.get("email"),
                "name": user.get("name"),
                "company": user.get("company"),
                "role": user.get("role", "User"),
                "deleted": user.get("deleted", True),
                "created_at": _iso(user.get("created_at")),
                "updated_at": _iso(user.get("updated_at")),
            }
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "company": user.company,
            "role": user.role or "User",
            "deleted": user.deleted,
            "created_at": _iso(user.created_at),
            "updated_at": _iso(user.updated_at),
        }

    @staticmethod
    def _raw(user):
        """Raw-doc shape that auth/account-integrity code expects (incl. password, _id)."""
        if user is None:
            return None
        return {
            "_id": str(user.id),
            "email": user.email,
            "password": user.password,
            "name": user.name,
            "company": user.company,
            "role": user.role or "User",
            "deleted": user.deleted,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    @staticmethod
    def find_all(page=1, limit=10, role="user"):
        skip = (page - 1) * limit
        qs = User.objects.filter(deleted=False)
        if role == "manager":
            qs = qs.exclude(role="admin")
        total = qs.count()
        rows = list(qs.order_by("created_at")[skip:skip + limit])
        return {
            "users": [UserModel.serialize_user(u) for u in rows],
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @staticmethod
    def find_by_email(email: str):
        user = User.objects.filter(email=email, deleted=False).first()
        return UserModel._raw(user)

    @staticmethod
    def find_by_id(user_id: str):
        return UserModel.serialize_user(
            User.objects.filter(id=user_id, deleted=False).first()
        )

    @staticmethod
    def find_raw_by_id(user_id: str):
        return UserModel._raw(User.objects.filter(id=user_id).first())

    @staticmethod
    def create_user(email, hashed_password, name, company=None, role="User", deleted=False):
        now = datetime.now(timezone.utc)
        user = User.objects.create(
            email=email, password=hashed_password, name=name, company=company,
            role=role, deleted=deleted, created_at=now, updated_at=now,
        )
        return UserModel.find_by_id(user.id)

    @staticmethod
    def update_user(user_id: str, update_data: dict):
        fields = dict(update_data)
        fields["updated_at"] = datetime.now(timezone.utc)
        User.objects.filter(id=user_id).update(**fields)
        return UserModel.find_by_id(user_id)

    @staticmethod
    def delete_user(user_id: str):
        return User.objects.filter(id=user_id).delete()

    @staticmethod
    def exists(email: str) -> bool:
        return User.objects.filter(email=email).exists()

    @staticmethod
    def find_protected(roles):
        rows = User.objects.filter(role__in=list(roles), deleted=False)
        return [UserModel._raw(u) for u in rows]
```

- [ ] **Step 4: Write failing test for PermissionModel**

Create `server/local/auth_app/tests/test_permission_model.py`:

```python
from django.test import TestCase
from local.auth_app.models.permission_model import PermissionModel


class PermissionModelTests(TestCase):
    def test_admin_role_grants_all_keys(self):
        perms = PermissionModel.get_permissions_for_role("Admin")
        self.assertEqual(set(perms.keys()), set(PermissionModel.get_all_permission_keys()))
        self.assertTrue(all(perms.values()))

    def test_set_then_get_roundtrip_and_upsert(self):
        PermissionModel.set_permissions_for_role("manager", {"view_projects": True})
        self.assertEqual(PermissionModel.get_permissions_for_role("manager"), {"view_projects": True})
        PermissionModel.set_permissions_for_role("manager", {"view_projects": False})
        self.assertEqual(PermissionModel.get_permissions_for_role("manager"), {"view_projects": False})

    def test_unknown_role_returns_empty(self):
        self.assertEqual(PermissionModel.get_permissions_for_role("ghost"), {})
```

- [ ] **Step 5: Rewrite PermissionModel as an ORM repository**

Replace `server/local/auth_app/models/permission_model.py` entirely:

```python
from datetime import datetime, timezone
from local.auth_app.models.orm import RolePermission


class PermissionModel:
    @staticmethod
    def get_permissions_for_role(role: str) -> dict:
        if (role or "").lower() == "admin":
            return {key: True for key in PermissionModel.get_all_permission_keys()}
        row = RolePermission.objects.filter(role=role).first()
        return row.permissions if row else {}

    @staticmethod
    def set_permissions_for_role(role: str, permissions: dict):
        RolePermission.objects.update_or_create(
            role=role,
            defaults={"permissions": permissions, "updated_at": datetime.now(timezone.utc)},
        )

    @staticmethod
    def get_all_permission_keys() -> list:
        return [
            "create_project", "delete_project", "update_project", "view_projects",
            "view_scans", "create_scan", "update_scan", "delete_scan",
            "view_findings", "validate_finding", "delete_finding",
            "create_report", "update_report", "delete_report", "view_reports",
        ]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd server && python manage.py test local.auth_app.tests -v 2`
Expected: PASS (all UserModel + PermissionModel tests green).

- [ ] **Step 7: Commit**

```bash
git add server/local/auth_app/models/user_model.py server/local/auth_app/models/permission_model.py server/local/auth_app/tests/
git commit -m "feat(auth): port UserModel and PermissionModel to SQLite ORM repositories"
```

---

## Task 4: api_app ORM models + migration

**Files:**
- Create: `server/local/api_app/models/orm.py`
- Modify: `server/local/api_app/models/__init__.py`
- Create: `server/local/api_app/migrations/__init__.py`

- [ ] **Step 1: Create the ORM models**

Create `server/local/api_app/models/orm.py`:

```python
from django.db import models
from common.orm import UUIDModel


def _severity_counts_default():
    return {"critical": 0, "high": 0, "medium": 0, "low": 0, "negligible": 0}


def _scan_metrics_default():
    return {"total_functions": 0, "total_loc": 0, "languages": []}


class Project(UUIDModel):
    name = models.CharField(max_length=255)
    preset = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    created_by = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField()
    deleted = models.BooleanField(default=False)

    class Meta:
        app_label = "api_app"
        db_table = "projects"


class Scan(UUIDModel):
    project_id = models.CharField(max_length=32, db_index=True)
    scan_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=32, default="queued")
    source = models.CharField(max_length=32, default="zip")
    created_at = models.DateTimeField()
    last_updated = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    triggered_by = models.CharField(max_length=32, blank=True, default="")
    total_files = models.IntegerField(default=0)
    files_scanned = models.IntegerField(default=0)
    findings = models.IntegerField(default=0)
    error = models.TextField(blank=True, default="")
    deleted = models.BooleanField(default=False)
    metrics = models.JSONField(default=_scan_metrics_default)

    class Meta:
        app_label = "api_app"
        db_table = "scans"


class Finding(UUIDModel):
    scan_id = models.CharField(max_length=32, db_index=True)
    created_by = models.CharField(max_length=32, blank=True, default="")
    cwe = models.CharField(max_length=255, blank=True, default="")
    cvss_vector = models.CharField(max_length=255, blank=True, default="")
    cvss_score = models.CharField(max_length=32, blank=True, default="")
    code = models.CharField(max_length=64, blank=True, default="")
    title = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=32, blank=True, default="")
    file_path = models.CharField(max_length=512, blank=True, default="")
    code_snip = models.TextField(blank=True, default="")
    security_risk = models.TextField(blank=True, default="")
    mitigation = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, default="open")
    deleted = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    reference = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField()

    class Meta:
        app_label = "api_app"
        db_table = "findings"


class SbomScan(UUIDModel):
    project_id = models.CharField(max_length=32, db_index=True)
    scan_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=32, default="queued")
    created_at = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    triggered_by = models.CharField(max_length=32, blank=True, default="")
    dependencies_scanned = models.IntegerField(default=0)
    vulnerabilities = models.IntegerField(default=0)
    severity_counts = models.JSONField(default=_severity_counts_default)
    ecosystems = models.JSONField(default=list)
    sbom_format = models.CharField(max_length=32, default="syft-json")
    deleted = models.BooleanField(default=False)
    sbom_signing = models.JSONField(default=dict)
    sbom_artifact = models.CharField(max_length=512, blank=True, default="")
    license_policy = models.JSONField(default=dict)

    class Meta:
        app_label = "api_app"
        db_table = "sbom_scans"


class SbomFinding(UUIDModel):
    scan_id = models.CharField(max_length=32, db_index=True)
    package_name = models.CharField(max_length=255, blank=True, default="")
    package_version = models.CharField(max_length=128, blank=True, default="")
    package_type = models.CharField(max_length=64, blank=True, default="")
    cve_id = models.CharField(max_length=64, blank=True, default="")
    severity = models.CharField(max_length=32, blank=True, default="")
    description = models.TextField(blank=True, default="")
    cvss = models.JSONField(default=list)
    fix_versions = models.JSONField(default=list)
    created_at = models.DateTimeField()

    class Meta:
        app_label = "api_app"
        db_table = "sbom_findings"


class SbomLicenseFinding(UUIDModel):
    scan_id = models.CharField(max_length=32, db_index=True)
    package_name = models.CharField(max_length=255, blank=True, default="")
    package_version = models.CharField(max_length=128, blank=True, default="")
    package_type = models.CharField(max_length=64, blank=True, default="")
    license = models.JSONField(default=dict)
    decision = models.CharField(max_length=64, blank=True, default="")
    locations = models.JSONField(default=list)
    created_at = models.DateTimeField()

    class Meta:
        app_label = "api_app"
        db_table = "sbom_licenses_findings"
```

- [ ] **Step 2: Make Django discover the models**

Edit `server/local/api_app/models/__init__.py`, add at the top:

```python
from local.api_app.models.orm import (  # noqa: F401
    Project, Scan, Finding, SbomScan, SbomFinding, SbomLicenseFinding,
)
```

- [ ] **Step 3: Create the migrations package**

Create empty file `server/local/api_app/migrations/__init__.py`.

- [ ] **Step 4: Generate and apply the migration**

Run:
```bash
cd server && python manage.py makemigrations api_app && python manage.py migrate
```
Expected: `0001_initial.py` created and applied OK.

- [ ] **Step 5: Commit**

```bash
git add server/local/api_app/models/orm.py server/local/api_app/models/__init__.py server/local/api_app/migrations/
git commit -m "feat(api): add Project/Scan/Finding/Sbom ORM models"
```

---

## Task 5: Rewrite ProjectModel + drop ObjectId in project_views

**Files:**
- Modify: `server/local/api_app/models/project_models.py`
- Modify: `server/local/api_app/views/project_views.py`
- Test: `server/local/api_app/tests/test_project_model.py`

- [ ] **Step 1: Write failing test**

Create `server/local/api_app/tests/__init__.py` (empty), then `server/local/api_app/tests/test_project_model.py`:

```python
from django.test import TestCase
from local.api_app.models.project_models import ProjectModel


class ProjectModelTests(TestCase):
    def test_create_serializes_with_string_ids(self):
        p = ProjectModel.create({"name": "P1", "description": "d", "created_by": "user123"})
        self.assertEqual(p["name"], "P1")
        self.assertEqual(p["created_by"], "user123")
        self.assertFalse(p["deleted"])
        self.assertIsNotNone(p["created_at"])

    def test_find_by_id_and_fetch_names(self):
        p = ProjectModel.create({"name": "P2", "created_by": "u"})
        self.assertEqual(ProjectModel.find_by_id(p["id"])["name"], "P2")
        names = ProjectModel.fetch_names()
        self.assertIn({"id": p["id"], "name": "P2"}, names)

    def test_find_all_excludes_deleted_and_paginates(self):
        ProjectModel.create({"name": "A", "created_by": "u"})
        d = ProjectModel.create({"name": "B", "created_by": "u"})
        ProjectModel.soft_delete(d["id"])
        result = ProjectModel.find_all(page=1, limit=10)
        names = [p["name"] for p in result["projects"]]
        self.assertIn("A", names)
        self.assertNotIn("B", names)
        self.assertEqual(result["pagination"]["total"], 1)

    def test_update(self):
        p = ProjectModel.create({"name": "C", "created_by": "u"})
        updated = ProjectModel.update(p["id"], {"name": "C2"})
        self.assertEqual(updated["name"], "C2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python manage.py test local.api_app.tests.test_project_model -v 2`
Expected: FAIL (RuntimeError from lazy Mongo stub).

- [ ] **Step 3: Rewrite ProjectModel**

Replace `server/local/api_app/models/project_models.py` entirely:

```python
from datetime import datetime, timezone
from local.api_app.models.orm import Project


def _iso(dt):
    return dt.isoformat() if dt else None


class ProjectModel:
    @staticmethod
    def serialize(project):
        if project is None:
            return None
        return {
            "id": str(project.id),
            "name": project.name,
            "preset": project.preset or "",
            "description": project.description or "",
            "created_by": str(project.created_by),
            "created_at": _iso(project.created_at),
            "deleted": project.deleted,
        }

    @classmethod
    def create(cls, data):
        project = Project.objects.create(
            name=data["name"],
            preset=data.get("preset", ""),
            description=data.get("description", ""),
            created_by=str(data.get("created_by", "")),
            created_at=datetime.now(timezone.utc),
            deleted=False,
        )
        return cls.serialize(project)

    @classmethod
    def fetch_names(cls):
        return [
            {"id": str(p.id), "name": p.name}
            for p in Project.objects.filter(deleted=False).only("id", "name")
        ]

    @classmethod
    def find_all(cls, page=1, limit=10):
        skip = (page - 1) * limit
        qs = Project.objects.filter(deleted=False)
        total = qs.count()
        rows = list(qs.order_by("created_at")[skip:skip + limit])
        return {
            "projects": [cls.serialize(p) for p in rows],
            "pagination": {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @classmethod
    def find_by_id(cls, project_id):
        return cls.serialize(Project.objects.filter(id=project_id).first())

    @classmethod
    def update(cls, project_id, data):
        Project.objects.filter(id=project_id).update(**data)
        return cls.find_by_id(project_id)

    @classmethod
    def soft_delete(cls, project_id):
        Project.objects.filter(id=project_id).update(deleted=True)
        return True
```

- [ ] **Step 4: Drop ObjectId in project_views.py**

In `server/local/api_app/views/project_views.py`:
- Delete the import line `from bson import ObjectId`.
- Change line ~26 from:
  ```python
  project = ProjectModel.create({**serializer.validated_data, "created_by": ObjectId(user_id)})
  ```
  to:
  ```python
  project = ProjectModel.create({**serializer.validated_data, "created_by": user_id})
  ```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python manage.py test local.api_app.tests.test_project_model -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/local/api_app/models/project_models.py server/local/api_app/views/project_views.py server/local/api_app/tests/test_project_model.py server/local/api_app/tests/__init__.py
git commit -m "feat(api): port ProjectModel to ORM; drop ObjectId in project views"
```

---

## Task 6: Rewrite ScanModel + scanner progress

**Files:**
- Modify: `server/local/api_app/models/scan_models.py`
- Modify: `server/scanner/rag/progress.py`
- Test: `server/local/api_app/tests/test_scan_model.py`

- [ ] **Step 1: Write failing test**

Create `server/local/api_app/tests/test_scan_model.py`:

```python
from django.test import TestCase
from local.api_app.models.scan_models import ScanModel
from local.api_app.models.orm import Finding
from datetime import datetime, timezone


class ScanModelTests(TestCase):
    def test_create_defaults_and_string_ids(self):
        s = ScanModel.create({"project_id": "proj1", "scan_name": "S1", "triggered_by": "u1"})
        self.assertEqual(s["project_id"], "proj1")
        self.assertEqual(s["status"], "queued")
        self.assertEqual(s["source"], "zip")
        self.assertEqual(s["metrics"], {"total_functions": 0, "total_loc": 0, "languages": []})

    def test_update_status_and_progress(self):
        s = ScanModel.create({"project_id": "p", "scan_name": "S"})
        ScanModel.update_status(s["id"], "in_progress")
        self.assertEqual(ScanModel.find_by_id(s["id"])["status"], "in_progress")
        updated = ScanModel.update_progress(s["id"], files_scanned=3, findings=7)
        self.assertEqual(updated["files_scanned"], 3)
        self.assertEqual(updated["findings"], 7)

    def test_find_by_project_pagination(self):
        ScanModel.create({"project_id": "shared", "scan_name": "A"})
        ScanModel.create({"project_id": "shared", "scan_name": "B"})
        result = ScanModel.find_by_project("shared", page=1, limit=1)
        self.assertEqual(result["pagination"]["total"], 2)
        self.assertEqual(len(result["scans"]), 1)

    def test_delete_scan_removes_scan_and_findings(self):
        s = ScanModel.create({"project_id": "p", "scan_name": "S"})
        Finding.objects.create(scan_id=s["id"], created_at=datetime.now(timezone.utc))
        self.assertTrue(ScanModel.delete_scan(s["id"]))
        self.assertIsNone(ScanModel.find_by_id(s["id"]))
        self.assertEqual(Finding.objects.filter(scan_id=s["id"]).count(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python manage.py test local.api_app.tests.test_scan_model -v 2`
Expected: FAIL.

- [ ] **Step 3: Rewrite ScanModel**

Replace `server/local/api_app/models/scan_models.py` entirely:

```python
from datetime import datetime, timezone
from local.api_app.models.orm import Scan, Finding


def _iso(dt):
    return dt.isoformat() if dt else None


class ScanModel:
    @staticmethod
    def serialize(scan):
        if scan is None:
            return None
        return {
            "id": str(scan.id),
            "project_id": str(scan.project_id),
            "scan_name": scan.scan_name or "",
            "status": scan.status or "queued",
            "source": scan.source or "zip",
            "created_at": _iso(scan.created_at),
            "triggered_by": str(scan.triggered_by or ""),
            "total_files": scan.total_files,
            "files_scanned": scan.files_scanned,
            "findings": scan.findings,
            "error": scan.error or "",
            "end_time": _iso(scan.end_time),
            "metrics": scan.metrics or {"total_functions": 0, "total_loc": 0, "languages": []},
        }

    @classmethod
    def create(cls, data: dict):
        scan = Scan.objects.create(
            project_id=str(data["project_id"]),
            scan_name=data.get("scan_name", ""),
            triggered_by=str(data.get("triggered_by", "")),
            source=data.get("source", "zip"),
            status="queued",
            created_at=datetime.now(timezone.utc),
            deleted=False,
            total_files=0, files_scanned=0, findings=0, end_time=None,
        )
        return cls.find_by_id(scan.id)

    @classmethod
    def update_status(cls, scan_id: str, new_status: str):
        Scan.objects.filter(id=scan_id).update(status=new_status)
        return cls.find_by_id(scan_id)

    @classmethod
    def update_progress(cls, scan_id: str, **kwargs):
        allowed = ["total_files", "files_scanned", "findings", "end_time", "status"]
        fields = {k: kwargs[k] for k in allowed if k in kwargs}
        if fields:
            Scan.objects.filter(id=scan_id).update(**fields)
        return cls.find_by_id(scan_id)

    @classmethod
    def find_by_id(cls, scan_id: str):
        return cls.serialize(Scan.objects.filter(id=scan_id).first())

    @classmethod
    def find_by_project(cls, project_id: str, page=1, limit=10):
        skip = (page - 1) * limit
        qs = Scan.objects.filter(project_id=project_id)
        total = qs.count()
        rows = list(qs.order_by("created_at")[skip:skip + limit])
        return {
            "scans": [cls.serialize(s) for s in rows],
            "pagination": {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @classmethod
    def delete_scan(cls, scan_id: str):
        try:
            deleted, _ = Scan.objects.filter(id=scan_id).delete()
            Finding.objects.filter(scan_id=scan_id).delete()
            return bool(deleted)
        except Exception:
            return False
```

- [ ] **Step 4: Rewrite scanner progress.py to use the ORM**

Replace `server/scanner/rag/progress.py` entirely:

```python
from datetime import datetime, timezone
from local.api_app.models.orm import Scan


def update_progress(scan_id, scanned=None, total=None, status=None,
                    end_time=None, findings=None, error=None, metrics=None):
    """Update scan progress + AST metrics on the SQLite Scan row."""
    fields = {"last_updated": datetime.now(timezone.utc)}
    if scanned is not None:
        fields["files_scanned"] = scanned
    if total is not None:
        fields["total_files"] = total
    if status is not None:
        fields["status"] = status
    if end_time is not None:
        fields["end_time"] = end_time
    if findings is not None:
        fields["findings"] = findings
    if error is not None:
        fields["error"] = error
    if metrics is not None:
        fields["metrics"] = metrics
    Scan.objects.filter(id=scan_id).update(**fields)


def get_scan_progress(scan_id):
    scan = Scan.objects.filter(id=scan_id).first()
    if not scan:
        return None
    progress = {
        "project_name": scan.scan_name or "Unknown",
        "status": scan.status or "unknown",
        "start_time": scan.created_at,
        "end_time": scan.end_time,
        "total": scan.total_files or 0,
        "scanned": scan.files_scanned or 0,
        "findings": scan.findings or 0,
        "error": scan.error,
        "metrics": scan.metrics or {},
    }
    progress["percentage"] = (
        int((progress["scanned"] / progress["total"]) * 100) if progress["total"] else 0
    )
    return progress


def display_progress(scan_id):
    progress = get_scan_progress(scan_id)
    if not progress:
        print("No progress found for given scan ID.")
        return
    print("\n" + "=" * 50)
    print("SCAN PROGRESS")
    print("=" * 50)
    print(f"Project          : {progress['project_name']}")
    print(f"Status           : {progress['status'].upper()}")
    print(f"Total Files      : {progress['total']}")
    print(f"Files Scanned    : {progress['scanned']}")
    print(f"Completed        : {progress['percentage']}%")
    print(f"Findings         : {progress['findings']}")
    if progress.get("error"):
        print(f"Error            : {progress['error']}")
    print("=" * 50 + "\n")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python manage.py test local.api_app.tests.test_scan_model -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/local/api_app/models/scan_models.py server/scanner/rag/progress.py server/local/api_app/tests/test_scan_model.py
git commit -m "feat(api): port ScanModel and scanner progress to ORM"
```

---

## Task 7: Rewrite FindingModel + fix extract.py

**Files:**
- Modify: `server/local/api_app/models/finding_models.py`
- Modify: `server/scanner/rag/extract.py`
- Test: `server/local/api_app/tests/test_finding_model.py`

- [ ] **Step 1: Write failing test**

Create `server/local/api_app/tests/test_finding_model.py`:

```python
from django.test import TestCase
from local.api_app.models.finding_models import FindingModel


class FindingModelTests(TestCase):
    def _finding(self, scan_id="scan1", **over):
        base = {"scan_id": scan_id, "created_by": "u1", "cwe": "CWE-89",
                "title": "SQLi", "severity": "high"}
        base.update(over)
        return base

    def test_insert_many_ignores_unknown_keys_and_serializes(self):
        out = FindingModel.insert_many([
            self._finding(lines=[1, 2], affected="foo()")  # unknown keys must be dropped
        ])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["cwe"], "CWE-89")
        self.assertEqual(out[0]["status"], "open")
        self.assertFalse(out[0]["approved"])
        self.assertNotIn("lines", out[0])

    def test_find_by_scan_pagination_and_excludes_deleted(self):
        FindingModel.insert_many([self._finding(), self._finding()])
        result = FindingModel.find_by_scan("scan1", page=1, limit=1)
        self.assertEqual(result["pagination"]["total"], 2)
        self.assertEqual(len(result["findings"]), 1)

    def test_soft_delete_and_toggle_approved(self):
        out = FindingModel.insert_many([self._finding()])
        fid = out[0]["id"]
        self.assertEqual(FindingModel.toggle_approved(fid), {"id": fid, "approved": True})
        self.assertEqual(FindingModel.soft_delete(fid), 1)
        self.assertNotIn(fid, [f["id"] for f in FindingModel.find_all_by_scan("scan1")])

    def test_find_by_project_via_scan_ids(self):
        from local.api_app.models.scan_models import ScanModel
        s = ScanModel.create({"project_id": "projX", "scan_name": "S"})
        FindingModel.insert_many([self._finding(scan_id=s["id"])])
        rows = FindingModel.find_by_project("projX")
        self.assertEqual(len(rows), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python manage.py test local.api_app.tests.test_finding_model -v 2`
Expected: FAIL.

- [ ] **Step 3: Rewrite FindingModel**

Replace `server/local/api_app/models/finding_models.py` entirely:

```python
from datetime import datetime, timezone
from local.api_app.models.orm import Finding, Scan

_FIELDS = [
    "scan_id", "created_by", "cwe", "cvss_vector", "cvss_score", "code", "title",
    "description", "severity", "file_path", "code_snip", "security_risk",
    "mitigation", "status", "deleted", "approved", "reference", "created_at",
]


def _iso(dt):
    return dt.isoformat() if dt else None


class FindingModel:
    @staticmethod
    def serialize(finding):
        if finding is None:
            return None
        return {
            "id": str(finding.id),
            "scan_id": str(finding.scan_id),
            "created_by": str(finding.created_by or ""),
            "cwe": finding.cwe or "",
            "cvss_vector": finding.cvss_vector or "",
            "cvss_score": finding.cvss_score or "",
            "code": finding.code or "",
            "title": finding.title or "",
            "description": finding.description or "",
            "severity": finding.severity or "",
            "file_path": finding.file_path or "",
            "code_snip": finding.code_snip or "",
            "security_risk": finding.security_risk or "",
            "mitigation": finding.mitigation or "",
            "status": finding.status or "open",
            "deleted": finding.deleted,
            "approved": finding.approved,
            "reference": finding.reference or "",
            "created_at": _iso(finding.created_at),
        }

    @classmethod
    def insert_many(cls, findings: list[dict]):
        if not findings:
            return []
        objs = []
        for f in findings:
            data = {k: f[k] for k in _FIELDS if k in f}  # drop unknown keys (lines, affected, ...)
            data["scan_id"] = str(data.get("scan_id", ""))
            data["created_by"] = str(data.get("created_by", ""))
            data.setdefault("created_at", datetime.now(timezone.utc))
            data.setdefault("status", "open")
            data.setdefault("deleted", False)
            data.setdefault("approved", False)
            objs.append(Finding(**data))
        created = Finding.objects.bulk_create(objs)
        return [cls.serialize(o) for o in created]

    @classmethod
    def find_by_id(cls, finding_id: str):
        return cls.serialize(Finding.objects.filter(id=finding_id).first())

    @classmethod
    def find_all(cls):
        return [cls.serialize(f) for f in Finding.objects.filter(deleted=False)]

    @classmethod
    def find_all_by_scan(cls, scan_id: str):
        return [cls.serialize(f) for f in Finding.objects.filter(scan_id=scan_id, deleted=False)]

    @classmethod
    def find_by_scan(cls, scan_id: str, page=1, limit=10):
        skip = (page - 1) * limit
        qs = Finding.objects.filter(scan_id=scan_id, deleted=False)
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "findings": [cls.serialize(f) for f in rows],
            "pagination": {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @classmethod
    def find_by_project(cls, project_id: str):
        scan_ids = list(Scan.objects.filter(project_id=project_id).values_list("id", flat=True))
        if not scan_ids:
            return []
        rows = Finding.objects.filter(scan_id__in=scan_ids, deleted=False)
        return [cls.serialize(f) for f in rows]

    @classmethod
    def soft_delete(cls, finding_id: str):
        return Finding.objects.filter(id=finding_id).update(deleted=True)

    @classmethod
    def soft_delete_by_scan(cls, scan_id: str):
        return Finding.objects.filter(scan_id=scan_id).update(deleted=True)

    @classmethod
    def toggle_approved(cls, finding_id: str):
        finding = Finding.objects.filter(id=finding_id).first()
        if not finding:
            return None
        finding.approved = not finding.approved
        finding.save(update_fields=["approved"])
        return {"id": finding_id, "approved": finding.approved}
```

- [ ] **Step 4: Fix extract.py to pass string ids**

In `server/scanner/rag/extract.py`:
- Delete the import line `from bson import ObjectId`.
- Change line ~243 `"scan_id": ObjectId(scan_id),` to `"scan_id": scan_id,`.
- Change line ~262 `"created_by": ObjectId(triggered_by),` to `"created_by": triggered_by,`.

(The extra `"lines"` and `"affected"` keys are now safely ignored by `FindingModel.insert_many`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python manage.py test local.api_app.tests.test_finding_model -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/local/api_app/models/finding_models.py server/scanner/rag/extract.py server/local/api_app/tests/test_finding_model.py
git commit -m "feat(api): port FindingModel to ORM; pass string ids from extractor"
```

---

## Task 8: Rewrite SbomModel + fix sbom_pipeline.py

**Files:**
- Modify: `server/local/api_app/models/sbom_models.py`
- Modify: `server/scanner/services/sbom_pipeline.py`
- Test: `server/local/api_app/tests/test_sbom_model.py`

- [ ] **Step 1: Write failing test**

Create `server/local/api_app/tests/test_sbom_model.py`:

```python
from django.test import TestCase
from local.api_app.models.sbom_models import SbomModel


class SbomModelTests(TestCase):
    def test_create_defaults(self):
        s = SbomModel.create({"project_id": "p1", "scan_name": "SB", "triggered_by": "u"})
        self.assertEqual(s["status"], "queued")
        self.assertEqual(s["severity_counts"],
                         {"critical": 0, "high": 0, "medium": 0, "low": 0, "negligible": 0})
        self.assertEqual(s["sbom_format"], "syft-json")

    def test_insert_findings_and_serialize_shape(self):
        s = SbomModel.create({"project_id": "p", "scan_name": "SB"})
        SbomModel.insert_findings([{
            "scan_id": s["id"], "package_name": "lodash", "package_version": "1.0.0",
            "package_type": "npm", "cve_id": "CVE-1", "severity": "High",
            "description": "x", "cvss": [{"type": "Primary", "version": "3.1",
            "vector": "v", "metrics": {"baseScore": 9.8}}], "fix_versions": ["1.0.1"],
        }])
        page = SbomModel.find_by_sbom_scan(s["id"], page=1, limit=10)
        f = page["findings"][0]
        self.assertEqual(f["package"], {"name": "lodash", "version": "1.0.0", "type": "npm"})
        self.assertEqual(f["severity"], "high")
        self.assertEqual(f["cvss_score"], 9.8)
        self.assertEqual(f["cvss"][0]["base_score"], 9.8)

    def test_insert_license_findings_and_find_by_risk(self):
        s = SbomModel.create({"project_id": "p", "scan_name": "SB"})
        SbomModel.insert_license_findings([{
            "scan_id": s["id"], "package_name": "pkg", "package_version": "1",
            "package_type": "npm", "license": {"id": "GPL", "risk_level": "high"},
            "decision": "deny", "locations": ["/x"],
        }])
        high = SbomModel.find_license_by_risk(s["id"], "high")
        self.assertEqual(high[0]["license"]["id"], "GPL")
        self.assertEqual(high[0]["decision"], "deny")

    def test_update_scan_fields_and_progress(self):
        s = SbomModel.create({"project_id": "p", "scan_name": "SB"})
        SbomModel.update_progress(s["id"], dependencies_scanned=5, vulnerabilities=2)
        self.assertEqual(SbomModel.find_by_id(s["id"])["dependencies_scanned"], 5)
        SbomModel.update_scan_fields(s["id"], {"sbom_artifact": "/tmp/sbom.json"})
        # no crash; field persisted (not in serialize output, but stored)

    def test_delete_scan_removes_findings(self):
        s = SbomModel.create({"project_id": "p", "scan_name": "SB"})
        SbomModel.insert_findings([{"scan_id": s["id"], "package_name": "a"}])
        self.assertTrue(SbomModel.delete_scan(s["id"]))
        self.assertEqual(SbomModel.find_sbom_findings_all(s["id"]), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python manage.py test local.api_app.tests.test_sbom_model -v 2`
Expected: FAIL.

- [ ] **Step 3: Rewrite SbomModel**

Replace `server/local/api_app/models/sbom_models.py` entirely:

```python
from datetime import datetime, timezone
from local.api_app.models.orm import SbomScan, SbomFinding, SbomLicenseFinding

_FINDING_FIELDS = ["scan_id", "package_name", "package_version", "package_type",
                   "cve_id", "severity", "description", "cvss", "fix_versions", "created_at"]
_LICENSE_FIELDS = ["scan_id", "package_name", "package_version", "package_type",
                   "license", "decision", "locations", "created_at"]


def _iso(dt):
    return dt.isoformat() if dt else None


class SbomModel:
    @staticmethod
    def serialize(scan):
        if scan is None:
            return None
        return {
            "id": str(scan.id),
            "project_id": str(scan.project_id),
            "scan_name": scan.scan_name or "",
            "status": scan.status or "queued",
            "created_at": _iso(scan.created_at),
            "triggered_by": str(scan.triggered_by or ""),
            "dependencies_scanned": scan.dependencies_scanned,
            "vulnerabilities": scan.vulnerabilities,
            "severity_counts": scan.severity_counts,
            "ecosystems": scan.ecosystems,
            "sbom_format": scan.sbom_format or "syft-json",
            "end_time": _iso(scan.end_time),
        }

    @staticmethod
    def finding_serialize(f):
        if f is None:
            return None
        cvss = [
            {
                "type": c.get("type"), "version": c.get("version"), "vector": c.get("vector"),
                "base_score": c.get("metrics", {}).get("baseScore"),
                "exploitability_score": c.get("metrics", {}).get("exploitabilityScore"),
                "impact_score": c.get("metrics", {}).get("impactScore"),
            }
            for c in (f.cvss or [])
        ]
        return {
            "id": str(f.id),
            "scan_id": str(f.scan_id),
            "package": {"name": f.package_name or "", "version": f.package_version or "",
                        "type": f.package_type or ""},
            "cve_id": f.cve_id or "",
            "severity": (f.severity or "").lower(),
            "description": f.description or "",
            "cvss": cvss,
            "cvss_score": (f.cvss[0].get("metrics", {}).get("baseScore") if f.cvss else None),
            "fix_versions": f.fix_versions or [],
            "created_at": _iso(f.created_at),
        }

    @staticmethod
    def license_finding_serialize(f):
        if f is None:
            return None
        lic = f.license or {}
        return {
            "id": str(f.id),
            "scan_id": str(f.scan_id),
            "package": {"name": f.package_name or "", "version": f.package_version or "",
                        "type": f.package_type or ""},
            "license": {
                "id": lic.get("id"), "reference": lic.get("reference"),
                "osi_approved": lic.get("osi_approved"),
                "risk_category": lic.get("risk_category"), "risk_level": lic.get("risk_level"),
            },
            "decision": f.decision or "",
            "locations": f.locations or [],
            "created_at": _iso(f.created_at),
        }

    @classmethod
    def create(cls, data: dict):
        scan = SbomScan.objects.create(
            project_id=str(data["project_id"]),
            scan_name=data.get("scan_name", ""),
            triggered_by=str(data.get("triggered_by", "")),
            status="queued",
            created_at=datetime.now(timezone.utc),
            deleted=False,
            dependencies_scanned=0, vulnerabilities=0,
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0, "negligible": 0},
            ecosystems=[], sbom_format="syft-json", end_time=None,
        )
        return cls.find_by_id(scan.id)

    @classmethod
    def update_status(cls, scan_id: str, new_status: str):
        SbomScan.objects.filter(id=scan_id).update(status=new_status)
        return cls.find_by_id(scan_id)

    @classmethod
    def update_progress(cls, scan_id: str, **kwargs):
        allowed = ["dependencies_scanned", "vulnerabilities", "severity_counts",
                   "ecosystems", "status", "end_time"]
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if fields:
            SbomScan.objects.filter(id=scan_id).update(**fields)
        return cls.find_by_id(scan_id)

    @classmethod
    def update_scan_fields(cls, scan_id: str, fields: dict):
        """Persist extra scan metadata (sbom_signing, sbom_artifact, license_policy)."""
        allowed = ["sbom_signing", "sbom_artifact", "license_policy"]
        data = {k: v for k, v in fields.items() if k in allowed}
        if data:
            SbomScan.objects.filter(id=scan_id).update(**data)

    @classmethod
    def insert_findings(cls, findings: list[dict]):
        objs = []
        for f in findings:
            data = {k: f[k] for k in _FINDING_FIELDS if k in f}
            data["scan_id"] = str(data.get("scan_id", ""))
            data.setdefault("created_at", datetime.now(timezone.utc))
            objs.append(SbomFinding(**data))
        SbomFinding.objects.bulk_create(objs)

    @classmethod
    def insert_license_findings(cls, findings: list[dict]):
        objs = []
        for f in findings:
            data = {k: f[k] for k in _LICENSE_FIELDS if k in f}
            data["scan_id"] = str(data.get("scan_id", ""))
            data.setdefault("created_at", datetime.now(timezone.utc))
            objs.append(SbomLicenseFinding(**data))
        SbomLicenseFinding.objects.bulk_create(objs)

    @classmethod
    def find_by_id(cls, scan_id: str):
        return cls.serialize(SbomScan.objects.filter(id=scan_id).first())

    @classmethod
    def find_by_project(cls, project_id: str, page=1, limit=10):
        skip = (page - 1) * limit
        qs = SbomScan.objects.filter(project_id=project_id)
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "scans": [cls.serialize(s) for s in rows],
            "pagination": {"total": total, "page": page, "limit": limit,
                           "pages": (total + limit - 1) // limit if limit else 0},
        }

    @classmethod
    def delete_scan(cls, scan_id: str):
        try:
            deleted, _ = SbomScan.objects.filter(id=scan_id).delete()
            SbomFinding.objects.filter(scan_id=scan_id).delete()
            SbomLicenseFinding.objects.filter(scan_id=scan_id).delete()
            return bool(deleted)
        except Exception:
            return False

    @classmethod
    def find_sbom_findings_all(cls, scan_id: str):
        return [cls.finding_serialize(f) for f in SbomFinding.objects.filter(scan_id=scan_id)]

    @classmethod
    def find_by_sbom_scan(cls, scan_id: str, page=1, limit=10):
        skip = (page - 1) * limit
        qs = SbomFinding.objects.filter(scan_id=scan_id)
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "findings": [cls.finding_serialize(f) for f in rows],
            "pagination": {"total": total, "page": page, "limit": limit,
                           "pages": (total + limit - 1) // limit if limit else 0},
        }

    @classmethod
    def find_license_findings_all(cls, scan_id: str):
        return [cls.license_finding_serialize(f)
                for f in SbomLicenseFinding.objects.filter(scan_id=scan_id)]

    @classmethod
    def find_license_findings_by_scan(cls, scan_id: str, page=1, limit=10):
        skip = (page - 1) * limit
        qs = SbomLicenseFinding.objects.filter(scan_id=scan_id)
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "licenses": [cls.license_finding_serialize(f) for f in rows],
            "pagination": {"total": total, "page": page, "limit": limit,
                           "pages": (total + limit - 1) // limit if limit else 0},
        }

    @classmethod
    def find_license_by_risk(cls, scan_id: str, risk_level: str):
        rows = SbomLicenseFinding.objects.filter(scan_id=scan_id, license__risk_level=risk_level)
        return [cls.license_finding_serialize(f) for f in rows]
```

- [ ] **Step 4: Fix sbom_pipeline.py to use repo methods (no collections, no ObjectId)**

In `server/scanner/services/sbom_pipeline.py`:

1. Delete the import `from bson import ObjectId`.
2. In `_parse_grype_results`, change `"scan_id": ObjectId(scan_id),` → `"scan_id": scan_id,`.
3. In `_parse_grant_results`, change `"scan_id": ObjectId(scan_id),` → `"scan_id": scan_id,`.
4. In `_parse_grant_check_results`, change both `"scan_id": ObjectId(scan_id),` occurrences → `"scan_id": scan_id,`.
5. In `run_project_pipeline`, delete the two lines:
   ```python
   vuln_db = SbomModel.findings_collection
   license_db = SbomModel.licenses_findings_collection
   ```
   Replace `vuln_db.insert_many(findings)` with `SbomModel.insert_findings(findings)`.
   Replace `license_db.insert_many(license_findings)` with `SbomModel.insert_license_findings(license_findings)`.
   Replace the two `SbomModel.scans_collection.update_one({"_id": ObjectId(scan_id)}, {"$set": {...}})` blocks with:
   ```python
   SbomModel.update_scan_fields(scan_id, {"sbom_signing": signing_status, "sbom_artifact": str(sbom_path)})
   ```
   and
   ```python
   SbomModel.update_scan_fields(scan_id, {"license_policy": grant_output.get("run", {}).get("policy", {})})
   ```
6. Apply the same replacements in `run_sbom_pipeline` (remove `vuln_db`/`license_db`, use `SbomModel.insert_findings` / `insert_license_findings`, and the `update_scan_fields` for `sbom_signing`).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python manage.py test local.api_app.tests.test_sbom_model -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/local/api_app/models/sbom_models.py server/scanner/services/sbom_pipeline.py server/local/api_app/tests/test_sbom_model.py
git commit -m "feat(api): port SbomModel to ORM; route sbom pipeline through repo methods"
```

---

## Task 9: Port dashboard aggregations to the ORM

**Files:**
- Modify: `server/local/api_app/views/dashboard_views.py`
- Test: `server/local/api_app/tests/test_dashboard.py`

- [ ] **Step 1: Write failing test**

Create `server/local/api_app/tests/test_dashboard.py`:

```python
from datetime import datetime, timezone
from django.test import TestCase
from local.api_app.views.dashboard_views import DashboardView
from local.api_app.models.orm import Project, Scan, Finding


class DashboardAggregationTests(TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.p = Project.objects.create(name="P", created_at=now)
        self.s = Scan.objects.create(project_id=self.p.id, scan_name="S", status="completed",
                                     source="zip", findings=2, created_at=now,
                                     metrics={"total_loc": 10, "total_functions": 2,
                                              "languages": ["Python", "Go"]})
        Finding.objects.create(scan_id=self.s.id, severity="critical", cwe="CWE-89: SQLi",
                               created_at=now)
        Finding.objects.create(scan_id=self.s.id, severity="high", cwe="CWE-79: XSS",
                               created_at=now)
        self.view = DashboardView()

    def test_system_status(self):
        out = self.view._get_system_status()
        self.assertEqual(out["total_scans"], 1)
        self.assertEqual(out["counts"].get("completed"), 1)

    def test_severity_counts(self):
        self.assertEqual(self.view._get_severity_counts(),
                         {"critical": 1, "high": 1, "medium": 0, "low": 0})

    def test_language_distribution(self):
        langs = {row["language"]: row for row in self.view._get_language_distribution()}
        self.assertIn("Python", langs)
        self.assertEqual(langs["Python"]["scans"], 1)
        self.assertEqual(langs["Python"]["vulnerabilities"], 2)

    def test_top_cwe(self):
        ids = [row["id"] for row in self.view._get_top_cwe()]
        self.assertIn("CWE-89", ids)

    def test_scans_by_project(self):
        rows = self.view._get_scans_by_project()
        self.assertEqual(rows[0]["project"], "P")
        self.assertEqual(rows[0]["scans"], 1)
        self.assertEqual(rows[0]["critical"], 1)

    def test_scan_distribution(self):
        rows = self.view._get_scan_distribution()
        self.assertEqual(rows[0]["name"], "ZIP Upload")
        self.assertEqual(rows[0]["value"], 1)

    def test_findings_trend_has_seven_days(self):
        self.assertEqual(len(self.view._get_findings_trend()), 7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python manage.py test local.api_app.tests.test_dashboard -v 2`
Expected: FAIL (current methods take a Mongo `db` arg and use pipelines).

- [ ] **Step 3: Rewrite dashboard_views.py with ORM aggregations**

Replace `server/local/api_app/views/dashboard_views.py` entirely:

```python
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from django.db.models import Count
from local.auth_app.permissions.decorators import require_authentication
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from local.api_app.models.orm import Project, Scan, Finding


def _severity_defaults() -> dict:
    return {"critical": 0, "high": 0, "medium": 0, "low": 0}


class DashboardView(APIView):
    @require_authentication()
    def get(self, request):
        try:
            response_data = {
                "top_counts": {
                    "users": _user_count(),
                    "projects": Project.objects.filter(deleted=False).count(),
                    "scans": Scan.objects.filter(deleted=False).count(),
                    "findings": Finding.objects.filter(deleted=False).count(),
                },
                "system_status": self._get_system_status(),
                "count_by_severity": self._get_severity_counts(),
                "language_distribution": self._get_language_distribution(),
                "findings_trend": self._get_findings_trend(),
                "top_cwe": self._get_top_cwe(),
                "scans_by_project": self._get_scans_by_project(),
                "scan_distribution": self._get_scan_distribution(),
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_system_status(self):
        rows = (Scan.objects.filter(deleted=False).values("status")
                .annotate(count=Count("id")))
        counts = {r["status"]: r["count"] for r in rows}
        return {"counts": counts, "total_scans": sum(counts.values())}

    def _get_severity_counts(self):
        counts = _severity_defaults()
        rows = (Finding.objects.filter(deleted=False).values("severity")
                .annotate(count=Count("id")))
        for r in rows:
            sev = str(r["severity"] or "").lower()
            if sev in counts:
                counts[sev] = r["count"]
        return counts

    def _get_language_distribution(self):
        acc = {}
        for scan in Scan.objects.filter(deleted=False).only("metrics", "findings"):
            langs = (scan.metrics or {}).get("languages") or []
            for lang in langs:
                bucket = acc.setdefault(lang, {"language": lang, "vulnerabilities": 0, "scans": 0})
                bucket["vulnerabilities"] += scan.findings or 0
                bucket["scans"] += 1
        rows = sorted(acc.values(),
                      key=lambda r: (-r["vulnerabilities"], -r["scans"], r["language"]))
        return rows[:8]

    def _get_findings_trend(self):
        start_date = datetime.now(timezone.utc) - timedelta(days=6)
        grouped = {}
        for f in Finding.objects.filter(deleted=False, created_at__gte=start_date).only(
            "created_at", "severity"
        ):
            date_key = f.created_at.strftime("%Y-%m-%d")
            sev = str(f.severity or "").lower()
            day_bucket = grouped.setdefault(
                date_key, {"critical": 0, "high": 0, "medium": 0, "low": 0}
            )
            if sev in day_bucket:
                day_bucket[sev] += 1

        trend = []
        for offset in range(7):
            day = (start_date + timedelta(days=offset)).date()
            key = day.strftime("%Y-%m-%d")
            values = grouped.get(key, {"critical": 0, "high": 0, "medium": 0, "low": 0})
            total = values["critical"] + values["high"] + values["medium"] + values["low"]
            trend.append({"date": day.strftime("%b %d"), **values, "total": total})
        return trend

    def _get_top_cwe(self):
        rows = (Finding.objects.filter(deleted=False)
                .exclude(cwe__in=["", None])
                .values("cwe").annotate(count=Count("id"))
                .order_by("-count", "cwe")[:10])
        results = []
        for r in rows:
            cwe_value = str(r["cwe"] or "")
            parts = cwe_value.split(":", 1)
            cwe_id = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else cwe_id
            results.append({"id": cwe_id, "name": name, "count": r["count"]})
        return results

    def _get_scans_by_project(self):
        scans = list(Scan.objects.filter(deleted=False).only(
            "project_id", "findings"
        ))
        if not scans:
            return []
        project_ids = {s.project_id for s in scans}
        names = {str(p.id): p.name for p in Project.objects.filter(id__in=project_ids)}

        # critical findings per project (join findings -> scans by scan_id)
        scan_to_project = {str(s.id): s.project_id for s in
                           Scan.objects.filter(deleted=False).only("project_id")}
        crit_by_project = defaultdict(int)
        for f in Finding.objects.filter(deleted=False, severity="critical").only("scan_id"):
            pid = scan_to_project.get(str(f.scan_id))
            if pid is not None:
                crit_by_project[pid] += 1

        agg = {}
        for s in scans:
            row = agg.setdefault(s.project_id, {"_id": s.project_id, "scans": 0, "findings": 0})
            row["scans"] += 1
            row["findings"] += s.findings or 0

        rows = []
        for pid, row in agg.items():
            rows.append({
                "project": names.get(str(pid), "Unknown Project"),
                "scans": row["scans"],
                "findings": row["findings"],
                "critical": crit_by_project.get(pid, 0),
            })
        rows.sort(key=lambda r: (-r["findings"], -r["scans"], r["project"]))
        return rows[:10]

    def _get_scan_distribution(self):
        palette = {"zip": "#8b5cf6", "github": "#ec4899"}
        labels = {"zip": "ZIP Upload", "github": "GitHub Repo"}
        rows = (Scan.objects.filter(deleted=False).values("source")
                .annotate(value=Count("id")).order_by("-value", "source"))
        results = []
        for r in rows:
            source = str(r["source"] or "zip")
            results.append({
                "name": labels.get(source, source.title()),
                "value": r["value"],
                "color": palette.get(source, "#bf0000"),
            })
        return results


def _user_count():
    from local.auth_app.models.orm import User
    return User.objects.filter(deleted=False).count()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python manage.py test local.api_app.tests.test_dashboard -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/local/api_app/views/dashboard_views.py server/local/api_app/tests/test_dashboard.py
git commit -m "feat(api): port dashboard aggregations to ORM"
```

---

## Task 10: First-run setup endpoint + account-integrity cleanup

**Files:**
- Create: `server/local/auth_app/services/setup.py`
- Create: `server/local/auth_app/views/setup_views.py`
- Modify: `server/local/auth_app/urls/__init__.py`
- Modify: `server/local/auth_app/utils/account_integrity.py`
- Test: `server/local/auth_app/tests/test_setup.py`

- [ ] **Step 1: Replace `.collection` access in account_integrity.py**

In `server/local/auth_app/utils/account_integrity.py`, replace the body of `sync_protected_accounts` (lines ~89-95) with:

```python
def sync_protected_accounts(created_by="provisioning"):
    registry = {}
    for user in UserModel.find_protected(list(PROTECTED_ROLES)):
        snapshot = _user_snapshot(user, created_by=created_by)
        registry[snapshot["email"]] = snapshot
    _save_registry(registry)
```

(`UserModel.find_protected` returns raw dicts with `_id`/`password`, exactly what `_user_snapshot` reads.)

- [ ] **Step 2: Write failing test**

Create `server/local/auth_app/tests/test_setup.py`:

```python
from django.test import TestCase
from local.auth_app.services.setup import is_setup_needed, create_initial_admin
from local.auth_app.models.permission_model import PermissionModel


class SetupServiceTests(TestCase):
    def test_setup_needed_when_no_admin(self):
        self.assertTrue(is_setup_needed())

    def test_create_initial_admin_seeds_admin_and_blocks_second_run(self):
        admin = create_initial_admin("root@x.com", "Str0ng!Pass1", "Root")
        self.assertEqual(admin["role"], "Admin")
        self.assertFalse(is_setup_needed())
        # default role permissions seeded
        self.assertEqual(PermissionModel.get_permissions_for_role("user"),
                         {k: False for k in PermissionModel.get_all_permission_keys()})
        with self.assertRaises(RuntimeError):
            create_initial_admin("second@x.com", "Str0ng!Pass1", "Second")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd server && python manage.py test local.auth_app.tests.test_setup -v 2`
Expected: FAIL (module does not exist).

- [ ] **Step 4: Create the setup service**

Create `server/local/auth_app/services/setup.py`:

```python
from local.auth_app.models.user_model import UserModel
from local.auth_app.models.orm import User
from local.auth_app.models.permission_model import PermissionModel
from local.auth_app.utils.password import hash_password


def is_setup_needed() -> bool:
    """True until at least one Admin account exists."""
    return not User.objects.filter(role__iexact="admin", deleted=False).exists()


def _seed_default_permissions():
    keys = PermissionModel.get_all_permission_keys()
    for role in ("user", "manager"):
        if not PermissionModel.get_permissions_for_role(role):
            PermissionModel.set_permissions_for_role(role, {k: False for k in keys})


def create_initial_admin(email: str, password: str, name: str, company: str = None):
    if not is_setup_needed():
        raise RuntimeError("Setup already completed: an admin account already exists.")
    admin = UserModel.create_user(
        email=email, hashed_password=hash_password(password),
        name=name, company=company, role="Admin",
    )
    _seed_default_permissions()
    return admin
```

- [ ] **Step 5: Create the setup views**

Create `server/local/auth_app/views/setup_views.py`:

```python
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from local.auth_app.services.setup import is_setup_needed, create_initial_admin


class SetupStatusView(APIView):
    def get(self, request):
        return Response({"setup_needed": is_setup_needed()}, status=status.HTTP_200_OK)


class SetupCreateAdminView(APIView):
    def post(self, request):
        if not is_setup_needed():
            return Response({"detail": "Setup already completed."}, status=status.HTTP_409_CONFLICT)
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""
        name = (request.data.get("name") or "").strip()
        company = request.data.get("company")
        if not email or not password or not name:
            return Response({"detail": "email, password, and name are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        admin = create_initial_admin(email, password, name, company)
        return Response({"user": admin}, status=status.HTTP_201_CREATED)
```

- [ ] **Step 6: Register the routes**

In `server/local/auth_app/urls/__init__.py`, add the imports and URL patterns (place alongside the existing `login`/`register` routes):

```python
from local.auth_app.views.setup_views import SetupStatusView, SetupCreateAdminView

# add to urlpatterns:
path("setup/", SetupStatusView.as_view()),
path("setup/admin/", SetupCreateAdminView.as_view()),
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd server && python manage.py test local.auth_app.tests.test_setup -v 2`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add server/local/auth_app/services/setup.py server/local/auth_app/views/setup_views.py server/local/auth_app/urls/__init__.py server/local/auth_app/utils/account_integrity.py server/local/auth_app/tests/test_setup.py
git commit -m "feat(auth): first-run setup endpoint and account-integrity ORM cleanup"
```

---

## Task 11: Final cleanup — remove pymongo, full test + smoke run

**Files:**
- Modify: `server/requirements.txt`
- Keep: `server/common/db/__init__.py` (lazy stub — still imported by `licenses/models.py` until Phase 4)

- [ ] **Step 1: Confirm no remaining ACTIVE Mongo/bson usage**

Run: `cd server && grep -rn "pymongo\|from bson\|import bson\|MongoDBClient\|ObjectId\|\.collection\b\|aggregate(" --include="*.py" . | grep -v "/migrations/" | grep -v "/tests/" | grep -v "^\./licenses/" | grep -v "^\./common/db/"`
Expected: **no output**. The two excluded paths are intentional: `licenses/models.py` still references the lazy `MongoDBClient` stub (rewritten in Phase 4), and `common/db/__init__.py` is the stub itself. If any *other* line prints, fix that file (replace with the repository method or a string id) before continuing.

- [ ] **Step 2: Keep the lazy db stub (do NOT delete it)**

Leave `server/common/db/__init__.py` in place. Django imports every installed app's `models` module at startup, and `licenses/models.py` does `from common.db import MongoDBClient` at module load. The lazy stub (from Task 1) resolves that import without connecting to anything, so the server boots; the stub raises only if a license query actually runs, which Phase 4 removes. Deleting it now would break startup.

- [ ] **Step 3: Drop pymongo from requirements**

In `server/requirements.txt`, delete the line `pymongo>=4.8,<5`.

- [ ] **Step 4: Run the full test suite**

Run: `cd server && python manage.py test -v 2`
Expected: PASS — all tests across `local.auth_app.tests` and `local.api_app.tests` green, 0 failures, 0 errors.

- [ ] **Step 5: Smoke-test the server boots and setup endpoint works**

Run:
```bash
cd server && python manage.py migrate && python manage.py runserver 127.0.0.1:8585 &
sleep 3 && curl -s http://127.0.0.1:8585/api/auth/setup/ ; kill %1
```
Expected: `{"setup_needed": true}` and no Mongo connection errors in the server log.

- [ ] **Step 6: Commit**

```bash
git add server/requirements.txt server/common server/codesense/settings.py
git commit -m "chore(db): remove MongoDB/pymongo; SQLite migration complete"
```

---

## Self-Review

**Spec coverage (spec §5 + §9 backend):**
- Model classes ported preserving signatures → Tasks 3, 5, 6, 7, 8. ✓
- JSON fields for nested documents (`metrics`, `severity_counts`, `cvss`, `license`, `locations`, `ecosystems`) → Task 4 ORM models. ✓
- UUID-hex string ids exposed as `id` → `common/orm.py` (Task 1) + serializers. ✓
- 9 aggregations hand-ported → Task 9 (7 dashboard methods; the other 2 `aggregate` sites were the dashboard's `$facet` sub-pipelines, all covered). ✓
- `LicenseModel` NOT migrated (superseded by Phase 4) → correctly omitted; `licenses/models.py` is untouched here and its Mongo client import is removed in Phase 4. ✓
- DB bootstrap / first-run admin seeding (spec §9 backend half) → Tasks 10. Frontend wizard is Phase 5. ✓
- Drop Mongo dependency → Task 11. ✓

**Placeholder scan:** No "TBD"/"handle later" steps; every code step shows full code; every consumer edit shows exact old→new strings. ✓

**Type consistency:** Repository method names and return shapes match the originals (`find_all`→`{users/projects/scans/findings, pagination}`, `serialize`→same keys). New methods referenced across tasks are defined where used: `UserModel.find_protected` (defined Task 3, used Task 10), `SbomModel.insert_findings`/`insert_license_findings`/`update_scan_fields` (defined Task 8, used Task 8 pipeline edits). `DashboardView._get_*` signatures changed from `(self, db)` to `(self)` consistently across the rewrite and its tests. ✓

**Open follow-ups handed to later phases (not gaps in this plan):**
- `licenses/models.py` still imports the lazy `MongoDBClient` stub at module load. It is harmless (the stub never connects) and is only exercised by the licensing flow, which Phase 4 rewrites. The stub is deliberately kept in Task 11 so the server boots; Phase 4 removes both the stub and `licenses/models.py`'s dependence on it.
- `scan_views.py` / `finding_views.py` were confirmed to pass string ids straight to repository methods (no direct `ObjectId`), so they need no change here; the Task 11 grep gate will catch any missed spot.
