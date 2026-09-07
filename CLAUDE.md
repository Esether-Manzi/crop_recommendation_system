# CLAUDE.md

Onboarding notes for working in this repo. Written from a full read-through of the codebase on 2026-09-07.

## Tech stack & key dependencies

- **Django 6.0.6** (Python 3.12), server-rendered MVT app — no separate frontend framework/build step.
- **MySQL** via `mysqlclient`, configured entirely through `python-decouple` reading `backend/.env` (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`; `ai` app additionally reads `GEMINI_API_KEY` the same way).
- **ML stack**: `scikit-learn`, `xgboost`, `shap`, `pandas`, `numpy`, `joblib`. A pre-trained XGBoost crop classifier is checked in as pickles (`backend/ml/model/*.pkl`) — there is no training step run at deploy time.
- **Frontend**: Bootstrap 5.3.8 + Font Awesome 6.7.2, both loaded from CDN in `templates/base/base.html` (no npm/webpack). `django-crispy-forms` + `crispy-bootstrap5` are dependencies but most forms hand-roll Bootstrap widget classes instead of using crispy tags. Google Font "Outfit" + a green/earth-toned custom theme in `backend/static/css/style.css`.
- **Serving**: `gunicorn` + `whitenoise` for production static files (whitenoise middleware auto-inserts itself only if the package is importable — see `config/settings.py`).
- No JS build tooling, no test runner beyond Django's built-in `manage.py test`, no linter/formatter config found (no ruff/flake8/black/pyproject.toml).
- Two local virtualenvs exist (`venv/`, `.venv/`), both gitignored — check which one is active before installing packages.

## Architecture overview

Django project root is `backend/` (`manage.py` lives there); everything is relative to it.

**Apps** (all in `INSTALLED_APPS`, each a standard `models.py` / `views.py` (function-based, not CBVs) / `forms.py` / `urls.py` (namespaced with `app_name`) / `admin.py` / `migrations/`):

- `accounts` — custom `User(AbstractUser)` with a `role` field (`farmer` / `officer` / `admin`) and `phone_number`. Registration/login/logout are hand-written views (not Django's auth views). A data migration (`0003_setup_groups.py`) runs the `setup_groups` management command to provision permission groups per role.
- `farms` — `Farm` (owned by a user) and `SoilRecord` (N/P/K/pH/temp/humidity/rainfall log entries, newest-first). This is the hub model everything else hangs off of.
- `recommendations` — `Prediction` model + `services/recommendation_services.py` (`RecommendationService`), which is the orchestration point: calls the ML predictor, `SuitabilityService`, and the SHAP explainer together and builds the recommendation payload shown to the user (see below).
- `rotation` — `RotationPlan`/`RotationStep`, simulates a 4-season crop rotation using `ml/datasets/sequential_pipeline.py` (`recommend_sequence`), tracking simulated nutrient depletion/recovery per step.
- `advisory` — `CropAdvisory` (static stage-by-stage crop guidance, seeded via `advisory/fixtures/`) and `SeasonTracker` (per-farm active-season tracking; `advisory/views.py` maps elapsed weeks since `start_date` to advisory stages).
- `feedback` — `HarvestFeedback`. Submitting feedback both records the harvest outcome *and* synthesizes a new `SoilRecord` by applying nutrient-depletion math (`ml/datasets/Crop_Nutrient_Depletion_Table_All38.csv`) scaled by yield rating and residue-management choice — this is how soil state evolves over time without manual re-entry.
- `dashboard` — landing/home view, aggregates farms/trackers/predictions/feedback and generates soil-alert banners (e.g. low nitrogen, out-of-range pH).
- `ai` — a chat assistant. Calls the Gemini API directly via `urllib` (no SDK) with a hardcoded Uganda-agronomy system prompt; if `GEMINI_API_KEY` is unset or the call fails, falls back to a keyword-matching canned-response function (`get_keyword_fallback`). Chat history lives in the session, not the DB (`ai/models.py` is empty).
- `common` — scaffolded but **not** in `INSTALLED_APPS` and not referenced anywhere; treat as dead/unfinished, don't assume it's wired up.
- `backend/configurations/` — an empty directory, no files. Likely a placeholder for a future settings split; currently unused.

**ML layer** (`backend/ml/`, a plain Python package, not a Django app):
- `loader.py` loads `model/crop_model.pkl`, `model/crop_encoder.pkl`, `model/feature_names.pkl` once at import time.
- `predictor.py` (`CropPredictor`) — `predict()` and `predict_top_n()` wrap the XGBoost model + label encoder.
- `explainer.py` — SHAP `TreeExplainer` (cached module-level singleton) producing per-feature contribution breakdowns per crop, plus fertilizer-boost constants used to simulate "what if you fertilized" scenarios.
- `datasets/sequential_pipeline.py` — multi-season rotation simulation logic (`recommend_sequence`), used only by `rotation`.
- `datasets/*.csv` — training data, Uganda crop suitability ranges, and the nutrient depletion table; these are read directly with `pandas` at request time (not loaded into the DB).

**Cross-cutting pattern**: multi-tenancy is enforced ad hoc in views via `get_object_or_404(Farm, id=farm_id, user=request.user)` (and similar chained lookups like `farm__user=request.user`) rather than a shared mixin/permission class — follow this pattern rather than introducing DRF-style permissions.

**Templates**: `backend/templates/<app>/...` plus a shared `base/` (`base.html`, `navbar.html`, `footer.html`). All pages extend `base.html` and use Bootstrap 5 classes directly in template markup.

## Current state / what's implemented vs in progress

Implemented and wired into `config/urls.py`: auth (register/login/logout), farm + soil record CRUD, ML-backed crop prediction with suitability + SHAP explanation, 4-season rotation planning, crop advisory library + season tracker, harvest feedback with automatic soil-state update, dashboard with soil alerts, and a Gemini-backed chat assistant with offline fallback.

Rough edges to be aware of:
- Tests are mostly untouched Django boilerplate (`# Create your tests here.`) in every app except `accounts`, which has one real test (`LoginPageTests`). Don't assume test coverage exists elsewhere.
- No CI configuration in the repo.
- No root `README.md`. `documentation/developer_journal.md` only has informal Day-1 environment-setup notes (MySQL install, venv) — not a running dev log.
- `common` app and `backend/configurations/` are unused scaffolding — don't extend them without checking with the user first, they may be leftovers.
- Business-logic placement is inconsistent: `recommendations` factors logic into `services/`, while `rotation` and `feedback` do the equivalent work inline in `views.py`. Match whichever pattern the file you're editing already uses rather than "fixing" the inconsistency unprompted.
- Working tree currently has uncommitted changes across most apps (see `git status`) — many migrations, `urls.py` files, and `forms.py` files are untracked. Don't assume `git log` reflects the current state of the tree.

## Conventions to follow for future edits

- Function-based views with `@login_required` (and `@require_POST` where a view should only accept POST), not class-based views.
- Ownership checks via `get_object_or_404(Model, id=x, user=request.user)` or `related__user=request.user` filters — never trust an ID from the request without scoping to `request.user`.
- `ModelForm`s in `forms.py` set Bootstrap classes directly in `widgets` (`"class": "form-control"` / `"form-select"`), not via crispy-forms tags, even though crispy is installed.
- `urls.py` per app sets `app_name = "<app>"` and names every path; views/templates reference routes via the namespaced name (e.g. `"farms:detail"`, `"dashboard:home"`).
- Comments are sparing; a few files (`accounts`) have explanatory docstrings/comments on every block, most others have none — match the surrounding file's density rather than a repo-wide rule.
- Money/measurement fields use `help_text` on the model field to document units (e.g. `"Nitrogen (N) value in mg/kg"`) instead of comments.
- `Meta.ordering` is set explicitly on time-series-like models (`SoilRecord`, `Prediction`, `RotationPlan`, `HarvestFeedback`) — newest first.
- f-strings throughout; no `.format()` or `%`-style formatting.
- Admin classes are customized per model (`list_display`, `list_filter`, `search_fields`, `raw_id_fields`) rather than using the bare `admin.site.register(Model)` — follow the existing per-app style when adding new admin registrations.
- Settings toggle production security headers only when `DEBUG=False`; don't hardcode security settings elsewhere.

## Environment / running locally

- `backend/.env` (gitignored) must define `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`; optionally `GEMINI_API_KEY` for live AI chat (falls back to canned responses otherwise). Note: a stray `backend/.evn` (typo) file also exists — don't confuse it with the real `.env`.
- MySQL server must be running and the DB/user created (see `documentation/developer_journal.md` for the original setup steps).
- Typical local run: from `backend/`, `python manage.py migrate` then `python manage.py runserver`.
- Logs go to `backend/logs/django.log` (dir auto-created by settings) and console.
