# CLAUDE.md

Onboarding notes for working in this repo. Originally written from a full read-through on 2026-09-07; refreshed on 2026-11-13 (notes app, profile, password reset, admin dashboard, `USE_HTTPS`, Python 3.14 venv). `PROJECT_SUMMARY.md` at the repo root has a longer module-by-module write-up and a list of known issues.

## Tech stack & key dependencies

- **Django 6.0.6** (Python 3.14 locally; `requirements.txt` also resolves on 3.12), server-rendered MVT app — no separate frontend framework/build step.
- **MySQL** via `mysqlclient`, configured entirely through `python-decouple` reading `backend/.env` (see "Environment" below for the full variable list).
- **ML stack**: `scikit-learn`, `xgboost`, `shap`, `pandas`, `numpy`, `joblib`. The trained model is checked in as pickles plus a `model_card.json` in `backend/ml/model/`, produced by `python manage.py train_model` (see "ML layer"). Nothing trains at deploy time. Since 2026-11-13 the deployed model is **Gaussian Naive Bayes**, auto-selected as the best of 8 compared models; don't assume XGBoost.
- **Pillow** for `User.profile_picture` uploads (`MEDIA_ROOT = backend/media/`, gitignored).
- **Frontend**: Bootstrap 5.3.8 + Font Awesome 6.7.2, both loaded from CDN in `templates/base/base.html` (no npm/webpack). `django-crispy-forms` + `crispy-bootstrap5` are dependencies but most forms hand-roll Bootstrap widget classes instead of using crispy tags. Google Font "Outfit" + a green/earth-toned custom theme in `backend/static/css/style.css`; the Django admin has its own theme in `backend/static/css/admin-theme.css`. Crop photos for recommendation results live in `backend/static/images/crops/` (Wikimedia Commons; attribution on the `/credits/` page).
- **Serving**: `gunicorn` + `whitenoise` for production static files (whitenoise middleware and `STORAGES` are only configured if the package is importable — see `config/settings.py`).
- **Email**: used only for password reset. Defaults to the console backend, so reset links print to the runserver console in dev; real SMTP is configured through `EMAIL_*` env vars.
- No JS build tooling, no test runner beyond Django's built-in `manage.py test`, no linter/formatter config found (no ruff/flake8/black/pyproject.toml).
- Use the single local virtualenv `.venv/` (gitignored, Python 3.14), rebuilt 2026-11-13 after the OS dropped Python 3.12.

## Architecture overview

Django project root is `backend/` (`manage.py` lives there); everything is relative to it.

**Apps** (all in `INSTALLED_APPS`, each a standard `models.py` / `views.py` (function-based, not CBVs) / `forms.py` / `urls.py` (namespaced with `app_name`) / `admin.py` / `migrations/`):

- `accounts` — custom `User(AbstractUser)` with `role` (`farmer` / `officer` / `admin`), `phone_number`, and `profile_picture` (`ImageField`, `upload_to="profile_pictures/"`). Registration/login/logout are hand-written views, not Django's auth views.
  - `User.save()` forces superusers to the `admin` role, since `createsuperuser` doesn't know about the field.
  - `UserRegistrationForm` removes `admin` from the role choices, so self-registration as Administrator is rejected even for a hand-crafted POST. Admins are created through the Django admin or `createsuperuser`.
  - **Profile** (`accounts:profile`, `ProfileForm`): lets users edit their username, email (checked for uniqueness, case-insensitive), phone, and picture (5 MB limit). If the form is invalid, the view calls `request.user.refresh_from_db()` so the navbar doesn't show values that weren't saved. Keep this when touching that view.
  - **Password reset** (`accounts:password_reset_request` → `accounts:password_reset_confirm`): hand-written views using `default_token_generator` and `urlsafe_base64_encode(pk)`, sent with `send_mail`. The request view shows the same success message whether or not the email exists, so it can't be used to discover accounts. Don't add an "email not found" error. `SetNewPasswordForm` wraps Django's `SetPasswordForm`, so `AUTH_PASSWORD_VALIDATORS` apply.
  - A data migration (`0003_setup_groups.py`) runs the `setup_groups` management command to create Farmer / Extension Officer / System Admin permission groups. **Note:** nothing ever adds users to these groups, and no view checks `role`. Roles are currently display-only (shown in the navbar and profile page), and there are no officer-specific features.
- `farms` — `Farm` (owned by a user) and `SoilRecord` (N/P/K/pH/temp/humidity/rainfall log entries, newest-first). This is the hub model everything else hangs off of. `SoilRecordForm.clean()` enforces input ranges.
- `recommendations` — `Prediction` model + `services/recommendation_services.py` (`RecommendationService`), which is the orchestration point: calls the ML predictor, `SuitabilityService` (`services/suitability_service.py`), and the explainer together and builds the recommendation payload shown to the user (see below).
- `rotation` — `RotationPlan`/`RotationStep`, simulates a 4-season crop rotation using `ml/datasets/sequential_pipeline.py` (`recommend_sequence`), tracking simulated nutrient depletion/recovery per step.
- `advisory` — `CropAdvisory` (static stage-by-stage crop guidance, 38 crops × 8 stages = 304 rows, seeded from `advisory/fixtures/advisory_seed.json`; that JSON is produced by the one-off script `fixtures/generate_advisory_seed.py`) and `SeasonTracker` (per-farm active-season tracking). `advisory/services.py` → `compute_season_progress(tracker)` maps elapsed weeks since `start_date` to advisory stages, a 4-step milestone, and a % progress (assumes 14 weeks to maturity for every crop). Both the tracker page and the dashboard use it, so change thresholds there rather than in either view.
- `feedback` — `HarvestFeedback`. Submitting feedback both records the harvest outcome *and* synthesizes a new `SoilRecord` by applying nutrient-depletion math (`ml/datasets/Crop_Nutrient_Depletion_Table_All38.csv`) scaled by yield rating and residue-management choice — this is how soil state evolves over time without manual re-entry. It also closes matching Active `SeasonTracker`s.
- `dashboard` — `dashboard_home` shows the public marketing page (`templates/home/index.html`) to anonymous users. Logged-in users get the farmer dashboard (`dashboard/home.html`): counts, active trackers, recent predictions and feedback, a 6-month prediction chart, their top crop, the latest soil record across all their farms, and soil-alert banners (N < 30, P < 20, K < 30, pH outside 5.0–8.0). `image_credits` (`dashboard:credits`) is the crop-photo attribution page.
- `ai` — a chat assistant. Calls the Gemini API directly via `urllib` (no SDK) with a hardcoded Uganda-agronomy system prompt; if `GEMINI_API_KEY` is unset or the call fails, falls back to a keyword-matching function (`get_keyword_fallback`) that answers from `CropAdvisory` rows. Chat history lives in the session, not the DB (`ai/models.py` is empty). The hardcoded model is `gemini-1.5-flash`, which Google has likely retired. Errors are swallowed, so a dead model just looks like "always fallback".
- `notes` — private farming notes. `Note(user, farm?, title, content, created_at, updated_at)`, ordered by `-updated_at`. `farm` is optional (`SET_NULL`), and `NoteForm(user=...)` limits the farm dropdown to the user's own farms. Views: `notes:list` (list + create on one page), `notes:edit`, `notes:delete` (`@require_POST`). It follows the farms pattern exactly; use it as the reference for a simple owned-CRUD app.
- `common` — scaffolded but **not** in `INSTALLED_APPS` and not referenced anywhere; treat as dead/unfinished, don't assume it's wired up.
- `backend/configurations/` — an empty directory, no files. Likely a placeholder for a future settings split; currently unused.

**Project config** (`backend/config/`):
- `settings.py` — see "Settings worth knowing" below.
- `urls.py` — mounts each app under its prefix (`/`, `/accounts/`, `/farms/`, `/recommendations/`, `/rotation/`, `/advisory/`, `/feedback/`, `/ai/`, `/notes/`, `/admin/`). Media is served by Django **only when `DEBUG=True`**.
- `admin_site.py` — **custom admin dashboard**. Imported for its side effect from `config/urls.py`, it swaps the class of the already-created `admin.site` to `CropAIAdminSite` (`admin.site.__class__ = ...`), so every app's existing `@admin.register` keeps working.
  - Adds "CropAI Administration" branding.
  - Sorts apps by `APP_PRIORITY`; `accounts`/`auth` are shown less prominently via `LOW_PRIORITY_APPS`.
  - `index()` passes extra context: six stat cards (farmers, farms, 7-day and all-time predictions, active seasons, harvest reports), a 14-day predictions-per-day chart, and a recent-predictions feed with crop icons (`CROP_ICONS`).
  - Templates are overridden in `templates/admin/` (`base_site.html`, `index.html`, `app_list.html`, `nav_sidebar.html`), styled by `static/css/admin-theme.css`.
  - When adding a new app, add its label to `APP_PRIORITY` or it sorts last.
  - Day-range queries deliberately use `created_at__gte/__lt` instead of `__date`, because `__date` breaks on MySQL installs without timezone tables. Keep that pattern.

**ML layer** (`backend/ml/`, a plain Python package, not a Django app):
- `training.py` + `recommendations/management/commands/train_model.py` — the reproducible training pipeline. It runs load → validate → **harmonise rainfall** → stratified 80/20 split → compare 8 models (10-fold CV, grid search, held-out test, accuracy split by Kaggle vs synthetic origin, corrected paired t-tests) → select the best by CV macro F1 (`--deploy best`, the default; or pass a model name) → evaluate (per-class report, confusion matrix, permutation importance) → save.
  - It writes `crop_model.pkl`, `crop_encoder.pkl`, `feature_names.pkl`, `model_card.json`, the comparison/significance/report CSVs and `training_dataset_harmonised.csv` into `ml/model/`. It also regenerates `datasets/Uganda_Crop_Suitability_Ranges.csv` from the same data, so the suitability display can't contradict the model.
  - The deployed model is fit on the training split, so the card's test scores describe exactly what is served.
  - Use `--output-dir <dir>` for experiments so the live model isn't overwritten; `--no-tune --folds 3` for a fast check. A full run takes ~12 minutes. **Restart the server after retraining** (models load at import).
- **Rainfall units (important):** the Kaggle rows are on a monthly scale (20–300 mm) and the synthetic Uganda rows came from annual ranges, so the pipeline divides synthetic rainfall by 12. The model therefore works in **monthly** mm, while farmers enter and see **annual** mm. `ml/features.py` (`build_model_input`, `RAINFALL_MONTHS`) is the only place that converts. Every caller that feeds the model must use it (the recommendation service and the rotation view do). `SoilRecord.rainfall` and `Prediction.rainfall` store annual mm. **N, P and K are mg/kg everywhere** (user decision 2026-11-13): labels, help text, and the soil-change maths, which converts crop uptake from kg/ha with ÷2.6. The Kaggle source never documents its units, so mg/kg is a stated assumption; don't switch to kg/ha without changing that maths too. `templates/farms/_soil_test_help.html` ("How do I fill this in?" guide + unit converter: K cmol/kg ×391, kg/ha ÷2.6, monthly rainfall ×12) is included by both soil forms; its converter fills inputs by Django's default `id_<field>` ids. `SoilRecord.source = "simulated"` marks records the feedback flow calculates after a harvest; the soil form hides that choice.
- `input_checks.py` — validation of farmer-entered values (panel comment 7), in three layers.
  - `HARD_LIMITS` are rejected by both `PredictionForm` and `SoilRecordForm`; keep them as the single source of limits.
  - `check_inputs()` gives soft warnings and the prediction still runs: likely unit slips (N/P/K below 1, rainfall under 300 mm/yr), values outside the training data's range, and "unusual soil". For Gaussian NB that last one uses the model's own likelihood (flagged if less likely than 99% of training soils); for other models it counts how many values fall inside some crop's range.
  - `check_soil_test()` warns based on the soil record's `source` (lab / kit / estimate / simulated) and `tested_on` age.
  - Warnings are saved on `Prediction.input_warnings` (JSON), shown above results, flashed as messages when a soil record is saved, and summarised on the Model Information admin page. Ranges come from the pipeline's own outputs, so they follow the deployed model.
- `loader.py` loads the model pickles plus `model_card.json` once at import time; it exposes `model_version`, which is saved on every `Prediction`.
- `predictor.py` (`CropPredictor`) — `predict()` and `predict_top_n()` wrap the model + label encoder (any sklearn-style classifier with `predict_proba`).
- `explainer.py` — per-feature contributions for the "why this crop" panel. The method depends on the deployed model type: Gaussian NB uses exact log-likelihood ratios against the average crop; tree models use SHAP `TreeExplainer`; anything else returns `[]`. It also holds the fertilizer-boost constants used to simulate "what if you fertilized" scenarios. Pass `display_values={"Rainfall": annual}` so farmers see annual rainfall.
- `datasets/sequential_pipeline.py` — multi-season rotation simulation logic (`recommend_sequence`), used only by `rotation`. It reloads the pickles from disk itself.
- `datasets/` — raw inputs: `Crop_Recommendation_kaggle_dataset.csv` (22 crops) and `Uganda_New_Crops_Synthetic_Only.csv` (16 crops) are the pipeline's sources. `Uganda_Expanded_Crop_Recommendation_Dataset.csv` is the older un-harmonised merge (kept for reference; the pipeline doesn't read it). Also the suitability ranges, the nutrient depletion table (38 crops), and the methodology note. These are read with `pandas` at request time, not loaded into the DB.
- Admin **Model Information** page (`admin:model_info`, `/admin/model-info/`, in `config/admin_site.py` + `templates/admin/model_info.html`) renders the model card as the pipeline's data track, plus predictions served per model version.
- Repo-root `raw/` holds the original Kaggle CSVs. They're reference only and not used at runtime.

**Cross-cutting pattern**: multi-tenancy is enforced ad hoc in views via `get_object_or_404(Farm, id=farm_id, user=request.user)` (and similar chained lookups like `farm__user=request.user`) rather than a shared mixin/permission class — follow this pattern rather than introducing DRF-style permissions.

**Templates**: `backend/templates/<app>/...` plus a shared `base/` (`base.html`, `navbar.html`, `bottom_nav.html`, `footer.html`), `home/index.html` (anonymous landing page), and `admin/` overrides. All pages extend `base.html` and use Bootstrap 5 classes directly in template markup. `base.html` renders Django `messages` site-wide, and `MESSAGE_TAGS` maps `error` to Bootstrap's `danger`. Navigation exists twice: the desktop navbar (`navbar.html`) and the mobile bottom nav (`bottom_nav.html`). **A new page needs a link added in both.** The navbar shows the user's profile picture and role.

## Current state / what's implemented vs in progress

Implemented and wired into `config/urls.py`:
- auth (register/login/logout), self-service password reset, and a profile page with picture upload
- farm + soil record CRUD
- ML-backed crop prediction with suitability + per-feature explanation, and a reproducible training pipeline with a Model Information admin page
- 4-season rotation planning
- crop advisory library + season tracker
- harvest feedback with automatic soil-state update
- farmer dashboard with soil alerts, and a public landing page for anonymous users
- private farming notes
- Gemini-backed chat assistant with offline fallback
- branded admin dashboard with system stats

Rough edges to be aware of:
- Tests: `accounts` (`LoginPageTests`), `dashboard` (`DashboardLatestSoilTests`) and `recommendations` (14 `SimpleTestCase`s for `ml/input_checks.py` and `PredictionForm`) have real tests; every other app has boilerplate. Because they're `SimpleTestCase`s, `manage.py test recommendations` runs even without the test-DB grant below; the DB-backed suites don't.
- `manage.py test` currently fails before running anything: MySQL user `crop_admin` lacks privileges to create `test_crop_recommendation_db`. It needs a `GRANT ALL ON test_crop_recommendation_db.* TO 'crop_admin'@'localhost'` run as MySQL root (the user's action). Until then, verify changes with a Django test `Client` script inside `transaction.atomic()` that raises at the end to roll back, so the dev DB is untouched.
- No CI configuration in the repo.
- No root `README.md`. `documentation/developer_journal.md` only has informal Day-1 environment-setup notes (MySQL install, venv) — not a running dev log.
- `common` app and `backend/configurations/` are unused scaffolding — don't extend them without checking with the user first, they may be leftovers.
- Business-logic placement is inconsistent: `recommendations` factors logic into `services/` (and `advisory` has a small `services.py`), while `rotation` and `feedback` do the equivalent work inline in `views.py`. Match whichever pattern the file you're editing already uses rather than "fixing" the inconsistency unprompted.
- Duplicated constants: soil-alert thresholds appear in `dashboard/views.py`, `ai/views.py` (`_farm_soil_note`), and the dashboard template. The fertilizer/depletion math (2.6 kg/ha↔mg/kg factor, pH drift) appears in `ml/explainer.py`, `ml/datasets/sequential_pipeline.py`, and `feedback/views.py`. Change all copies together.
- `CustomUserAdmin` fieldsets don't include `profile_picture` yet.

## Conventions to follow for future edits

- Function-based views with `@login_required` (and `@require_POST` where a view should only accept POST), not class-based views.
- Ownership checks via `get_object_or_404(Model, id=x, user=request.user)` or `related__user=request.user` filters — never trust an ID from the request without scoping to `request.user`. When a form has a FK dropdown to user-owned objects, restrict its queryset in `__init__` (see `NoteForm`).
- `ModelForm`s in `forms.py` set Bootstrap classes directly in `widgets` (`"class": "form-control"` / `"form-select"`), not via crispy-forms tags, even though crispy is installed. (`accounts` forms instead loop over `self.fields` in `__init__` to set the class; either is fine — match the file.)
- `urls.py` per app sets `app_name = "<app>"` and names every path; views/templates reference routes via the namespaced name (e.g. `"farms:detail"`, `"dashboard:home"`).
- User feedback after actions goes through `django.contrib.messages` (`messages.success/error/warning`), followed by a redirect (POST-redirect-GET).
- Comments are sparing; a few files (`accounts`, `config/admin_site.py`) have explanatory docstrings/comments on every block, most others have none — match the surrounding file's density rather than a repo-wide rule.
- Money/measurement fields use `help_text` on the model field to document units (e.g. `"Nitrogen (N) value in mg/kg"`) instead of comments.
- `Meta.ordering` is set explicitly on time-series-like models (`SoilRecord`, `Prediction`, `RotationPlan`, `HarvestFeedback`, `SeasonTracker`, `Note`) — newest first.
- f-strings throughout; no `.format()` or `%`-style formatting.
- Admin classes are customized per model (`list_display`, `list_filter`, `search_fields`, `raw_id_fields`) rather than using the bare `admin.site.register(Model)` — follow the existing per-app style when adding new admin registrations.
- User-facing copy is written for farmers without formal agronomy training: plain language, no jargon (commit `abdcb31` rewrote the app's copy this way). Keep new UI text in that voice.
- Settings toggle production security headers only when `DEBUG=False`; don't hardcode security settings elsewhere.

## Settings worth knowing (`config/settings.py`)

- `DEBUG` is parsed leniently (`1/true/yes/on/debug` → True).
- **`USE_HTTPS`** (default `False`): with `DEBUG=False`, the non-TLS hardening (nosniff, XSS filter, `X_FRAME_OPTIONS=DENY`) is always on. The HTTPS-only settings (`SECURE_SSL_REDIRECT`, HSTS with preload, secure session/CSRF cookies) turn on only when `USE_HTTPS=True` as well. Set it only once the site is actually served over https://, or the site will redirect-loop or drop cookies on plain HTTP.
- `STORAGES` is only set when whitenoise is installed, and it must define **both** `default` (FileSystemStorage, used for uploads) and `staticfiles` (whitenoise). Assigning `STORAGES` replaces Django's whole default dict, so leaving out `default` made every profile-picture upload return a 500 (fixed in `bfd2bf5`).
- `MEDIA_URL=/media/`, `MEDIA_ROOT=backend/media`. Media is only served by Django when `DEBUG=True`; production needs a web server (e.g. nginx) to serve `/media/`.
- `TIME_ZONE = "Africa/Kampala"`, `USE_TZ = True`.
- `EMAIL_BACKEND` defaults to the console backend; see env vars below.

## Environment / running locally

- `backend/.env` (gitignored):
  - Required: `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
  - Optional: `DEBUG`, `ALLOWED_HOSTS` (default `127.0.0.1,localhost`), `USE_HTTPS`, `GEMINI_API_KEY` (live AI chat), `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT` (587), `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` (True), `DEFAULT_FROM_EMAIL`
  - Note: a stray, empty `backend/.evn` (typo) file is tracked in git — don't confuse it with the real `.env`.
- MySQL server must be running and the DB/user created (see `documentation/developer_journal.md` for the original setup steps).
- Typical local run: `.venv/bin/python backend/manage.py migrate` then `.venv/bin/python backend/manage.py runserver`. In the desktop app, use the `crop-dev` launch config (`.claude/launch.json`, port 8765).
- Advisory content: `python manage.py loaddata advisory_seed` (from `backend/`) if the `CropAdvisory` table is empty.
- Password reset emails print to the runserver console unless SMTP is configured.
- Logs go to `backend/logs/django.log` (dir auto-created by settings) and console.
