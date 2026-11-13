# Project Summary — Crop Recommendation System ("CropAI")

_Reviewed module by module on 2026-11-13, at commit `bfd2bf5` (clean working tree)._

## Update 2026-11-13: training pipeline and model change (panel comments 5 & 8)

- **New pipeline:** `python manage.py train_model` (`backend/ml/training.py`) runs load → validate → harmonise rainfall → split → compare 8 models (10-fold CV, grid search, significance tests) → select the best → evaluate → save the model with `model_card.json`. The admin's **Model Information** page shows that record, and every prediction stores the model version that made it.
- **Rainfall fix:** Kaggle rainfall is monthly-scale (20–300 mm); the synthetic Uganda crops were annual (200–2,600 mm). Rainfall alone could tell the two sources apart 99.8% of the time, and any realistic annual input gave Soyabean. The synthetic values are now ÷12. Farmers still enter annual mm; `ml/features.py` converts.
- **Deployed model is now Gaussian Naive Bayes**, not XGBoost: test accuracy 0.975, macro F1 0.975, CV 0.967. It's significantly better than XGBoost (p = 0.004) and 5 other models, and tied with SVM. Its advantage is on the synthetic crops; on Kaggle rows it ties XGBoost (0.993). The "why this crop" panel uses exact per-feature log-likelihood contributions instead of SHAP. Sections below that say XGBoost/SHAP describe the earlier model.

## What it is

A server-rendered Django web app for **smallholder farmers in Uganda**. A farmer registers farms, logs soil tests (N, P, K, pH, temperature, humidity, rainfall), and gets:

- **Crop recommendations** from a pre-trained XGBoost model (top 5 crops, each with a confidence score, a check against ideal ranges, a SHAP "why" breakdown, and a "what if you fertilized" comparison).
- A **4-season crop rotation plan** that simulates how each crop drains or rebuilds the soil.
- A **knowledge base** of growing guides (38 crops × 8 stages) and a **season tracker** that shows the right advice for the current week of growth.
- **Harvest feedback** that automatically writes a new, simulated soil record, so the soil state changes over time without a new lab test.
- An **AI chat assistant** (Gemini, with an offline keyword fallback), private **farming notes**, and a **dashboard** with soil alerts and charts.
- A branded **Django admin** with system-wide stats.

## Tech stack

| Layer | Details |
|---|---|
| Framework | Django 6.0.6, function-based views, Django templates (MVT) |
| Python | Written for 3.12 (see the environment warning below) |
| Database | MySQL via `mysqlclient`; all config comes from `backend/.env` via `python-decouple` |
| ML | XGBoost 3.3, scikit-learn 1.9, SHAP 0.52, pandas 3, numpy 2.4, joblib |
| Frontend | Bootstrap 5.3.8 + Font Awesome 6.7.2 from CDN, "Outfit" font, custom CSS (`static/css/style.css` 700 lines, `admin-theme.css` 978 lines), 32 lines of JS. No build step. |
| Media | Pillow, for profile pictures (`MEDIA_ROOT = backend/media/`) |
| Serving | gunicorn + whitenoise (enabled automatically if installed) |
| Email | Console backend by default; SMTP through `EMAIL_*` env vars |
| Timezone | `Africa/Kampala` |

Size: about 4,100 lines of Python (excluding migrations), about 5,300 lines of templates and CSS, and 197 tracked files.

## Repository layout

```
crop_recommendation_system/
├── CLAUDE.md, LICENSE (MIT), requirements.txt, .claude/launch.json (dev server on :8765)
├── documentation/developer_journal.md   # Day-1 setup notes only
├── raw/                                 # 3 original Kaggle CSVs (~2.2k rows each), not used at runtime
└── backend/                             # Django project root (manage.py)
    ├── config/        settings, urls, admin_site.py (admin branding + stats)
    ├── accounts/ farms/ recommendations/ rotation/ advisory/ feedback/
    ├── dashboard/ ai/ notes/             # installed apps
    ├── common/                          # empty scaffold, NOT installed
    ├── configurations/                  # empty directory
    ├── ml/                              # plain Python package (model + datasets)
    ├── templates/                       # per-app folders + base/ + admin/ + home/
    ├── static/                          # css, js, images/crops (37 crop photos)
    ├── media/  logs/                    # gitignored, created at runtime
    └── .env (gitignored), .evn (empty, typo'd stray file)
```

## URL map

| Prefix | App | Routes (namespaced) |
|---|---|---|
| `/` | dashboard | `home` (landing page for anonymous users, dashboard for logged-in users), `credits` (photo attribution) |
| `/accounts/` | accounts | `register`, `login`, `logout` (POST only), `profile`, `password_reset_request`, `password_reset_confirm` |
| `/farms/` | farms | `list` (+ create), `detail/<id>` (+ add soil record) |
| `/recommendations/` | recommendations | `predict_crop` |
| `/rotation/` | rotation | `planner` |
| `/advisory/` | advisory | `list` (knowledge base), `tracker` |
| `/feedback/` | feedback | `submit` |
| `/ai/` | ai | `chat`, `clear_chat` |
| `/notes/` | notes | `list` (+ create), `edit/<id>`, `delete/<id>` (POST only) |
| `/admin/` | Django admin | Branded "CropAI Administration" |

## Data model

```
User (accounts) ── role: farmer | officer | admin, phone_number, profile_picture
 ├── Farm (farms) ── name, district, subcounty, size_acres, soil_type, lat/lng
 │    ├── SoilRecord ── N, P, K, pH, temp, humidity, rainfall   (newest first)
 │    ├── RotationPlan (rotation) ── RotationStep × 4 (crop, family, fertilizer, N/P/K/pH before→after)
 │    ├── SeasonTracker (advisory) ── crop_name, start_date, status Active|Completed
 │    ├── HarvestFeedback (feedback) ── crop, yield_rating, satisfaction 1–5, residue mgmt, comments
 │    └── Note (SET_NULL) ──┐
 ├── Prediction (recommendations) ── inputs + predicted_crop, optional farm (SET_NULL)
 └── Note (notes) ── title, content, optional farm

CropAdvisory (advisory) ── crop_name × stage (unique together); 304 rows seeded from fixtures
```

Migrations: accounts 0001–0004 (0003 is a data migration that runs `setup_groups`, 0004 adds `profile_picture`). recommendations has 0001–0002. Every other app has only 0001.

## Module by module

### `accounts`
- Custom `User(AbstractUser)`. `save()` forces superusers to have the `admin` role.
- Hand-written register, login, and logout views. Registration logs the user in straight away. The form removes the `admin` role from the choices, which also blocks a hand-crafted POST.
- **Password reset**: emails a signed `default_token_generator` link. The confirmation message is the same whether or not the email exists, so it can't be used to find accounts.
- **Profile page**: edit username, email (checked for uniqueness, case-insensitive), phone, and picture (5 MB limit). If the form is invalid, the view calls `refresh_from_db()` so the navbar doesn't show unsaved values.
- `setup_groups` management command: creates Farmer / Extension Officer / System Admin permission groups.
- This is the only app with a real test: `LoginPageTests`.
- The file uses dense docstrings and comments throughout.

### `farms`
- Farm list and create on one page. Farm detail page with soil-record history and an add form, pre-filled with the latest values.
- `SoilRecordForm.clean()` enforces ranges: N/P/K 0–1000, pH 3.5–8.5, temperature −10–60, humidity 0–100, rainfall 0–10000.
- This is the hub model. Everything else links to `Farm`.

### `recommendations`
- `predict_crop` view: you can pick a farm (`?farm_id=`), which pre-fills the form from that farm's latest soil record.
- `services/recommendation_services.py`, `RecommendationService.create_prediction`:
  1. Runs `CropPredictor.predict_top_n(n=5)` and saves a `Prediction` for the top crop.
  2. For each of the 5 crops, runs `SuitabilityService.analyze` on the current inputs **and** on fertilizer-boosted inputs, gets a SHAP explanation, and writes a plain-language reason.
- `services/suitability_service.py` compares each input to `Uganda_Crop_Suitability_Ranges.csv` (loaded once and cached on the class), labels it Too Low / Suitable / Too High, and returns a score out of 7 plus a percentage.

### `ml/` (not a Django app)
- `loader.py` loads `crop_model.pkl`, `crop_encoder.pkl`, and `feature_names.pkl` once at import. The features are `Nitrogen, Phosphorus, Potassium, Temperature, Humidity, pH_Value, Rainfall`.
- `predictor.py`: `predict()` and `predict_top_n()`.
- `explainer.py`: a cached SHAP `TreeExplainer` that returns per-feature contribution, direction, and share of the total. It also defines `FERTILIZER_BOOST`: N +40, P +20, K +15 kg/ha, divided by 2.6 to convert to mg/kg.
- `datasets/sequential_pipeline.py`, `recommend_sequence()`: predict a crop, apply that crop's nutrient uptake or nitrogen fixation, nudge pH (−0.03 for heavy feeders, +0.01 otherwise), and repeat. Each season excludes the previous crop and its whole plant family. The docstring describes this as a "rule-based sequential layer" wrapped around the single-season model, which reads as written for an academic report or proposal.
- `datasets/regenerate_suitability_ranges.py`: a one-off script that rebuilds the suitability ranges from the training data's min/max per crop, so the UI can't call a value "Too Low" for a crop the model just recommended.
- Datasets:
  - `Uganda_Expanded_Crop_Recommendation_Dataset.csv` (3,800 rows, training data)
  - `Uganda_New_Crops_Synthetic_Only.csv` (1,600 synthetic rows)
  - `Uganda_Crop_Suitability_Ranges.csv` and `Crop_Nutrient_Depletion_Table_All38.csv` (38 crops each)
  - A `.docx` methodology note
- **38 crops**, including Rice, Maize, Beans varieties, Cassava, SweetPotato, Banana, Plantain, Coffee, Tea, Cocoa, Vanilla, Groundnut, Soyabean, SesameSeed, Sugarcane, Tobacco, and some carried over from the India dataset (e.g. Apple, Grapes, Jute, Coconut).

### `rotation`
- `planner` view: pick a farm, choose whether to apply fertilizer (yes/no, the same for all 4 seasons), run `recommend_sequence(n_seasons=4)`, and save a `RotationPlan` with 4 `RotationStep`s. It needs at least one soil record.
- The logic lives directly in `views.py`, not in a services layer.

### `advisory`
- `advisory_list`: the knowledge base, with crop pills and stage tabs.
- `season_tracker`: start tracking a crop on a farm, or mark it complete (which sends you to the feedback form).
- `services.py`, `compute_season_progress()`: maps weeks since `start_date` to advisory stages and a 4-step milestone. Weeks 1–2 are Preparation/Planting, 3–5 Weeding/Fertilizer, 6–9 Pests/Diseases, and 10+ Harvest/Storage. Full maturity is assumed to be 14 weeks for every crop. The dashboard uses this function too.
- `fixtures/advisory_seed.json` holds 304 entries (38 crops × 8 stages), generated by `generate_advisory_seed.py`.

### `feedback`
- `feedback_submit`: saves a `HarvestFeedback`, then creates a new `SoilRecord`. Nutrient uptake is scaled by yield (Good 1.0, Average 0.75, Poor 0.45, Failed 0.15). If residue was incorporated, 30% of the P and K is returned to the soil. pH drifts as in the rotation simulation. It also closes any matching Active season trackers.
- The logic is inline in `views.py`.

### `dashboard`
- Anonymous visitors get the `home/index.html` landing page.
- Logged-in users get counts, active trackers with progress, recent predictions and feedback, a 6-month prediction chart, their most-recommended crop, a latest-soil panel, and soil alerts (N < 30, P < 20, K < 30, pH outside 5.0–8.0).
- `image_credits` page lists the Wikimedia Commons sources for the crop photos.

### `ai`
- Session-based chat (no database model). The prompt includes the selected farm's latest soil data. It calls Gemini `gemini-1.5-flash` through `urllib` with a 10-second timeout.
- The fallback, `get_keyword_fallback`, matches crop aliases and stage keywords to `CropAdvisory` entries, falls back to generic stage advice, and adds a note about the farm's own soil when relevant.

### `notes`
- Newest app. Not mentioned in CLAUDE.md.
- Private CRUD notes, optionally tagged to one of the user's own farms (the farm dropdown only lists that user's farms). Ownership is checked on edit and delete; delete is POST only.

### `config`
- `settings.py`:
  - `DEBUG` accepts several truthy spellings.
  - whitenoise is enabled only if installed. When it is, the `STORAGES` setting defines a `default` backend; that is the recent upload-500 fix.
  - `DEBUG=False` turns on basic security headers. HTTPS-only settings (SSL redirect, HSTS, secure cookies) are behind a separate `USE_HTTPS` flag.
  - Logging goes to `backend/logs/django.log` and the console, at WARNING level.
- `admin_site.py` swaps the class of the existing `admin.site` object. It adds branding, sorts apps by priority, and shows 6 stat cards, a 14-day prediction chart, and a recent-predictions feed on the admin index page.

### `common`, `configurations/`
- Empty scaffolding. Not installed, not referenced anywhere.

## Environment variables (`backend/.env`)
- Required: `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Optional: `DEBUG`, `ALLOWED_HOSTS`, `USE_HTTPS`, `GEMINI_API_KEY`, `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`

## History (main milestones)
Kaggle datasets and MIT license → Django + MySQL setup → auth system → suitability service → farms, rotation, advisory, feedback, and AI modules → mobile bottom nav and growth tracker → real crop photos → branded admin → dashboard redesigns → `USE_HTTPS` flag → advisory seeded for all 38 crops, P/K alerts, self-registration as admin removed → suitability ranges regenerated from training data → superuser gets admin role automatically → password reset → mobile and copy redesign → profile pictures → whitenoise upload fix.

---

## Findings from this review

### Environment (resolved 2026-11-13)
The OS upgrade removed Python 3.12, which broke both old venvs. `.venv` has been rebuilt on **Python 3.14**, and the old `venv/` is deleted. The pinned `requirements.txt` resolves to the same packages on 3.12 and 3.14, so it supports both without changes. A full smoke test (every page plus all main forms) passes. `manage.py test` still needs a MySQL grant: `crop_admin` can't create `test_crop_recommendation_db`.

### Bugs and likely issues
1. ~~**The dashboard's latest-soil panel could show the wrong farm.**~~ **Fixed 2026-11-13.** The alerts loop overwrote `latest_soil`; it now uses its own variable. A regression test is in `dashboard/tests.py`.
2. **The live AI chat probably never works.** The code calls `gemini-1.5-flash`, which Google has retired. The broad `except Exception: return None` means users would silently get the keyword fallback even with a valid API key. Updating the model name should be checked against Google's current model list.
3. **Profile pictures won't be served in production.** Media URLs are only added when `DEBUG=True`, and whitenoise doesn't serve media files. A production deployment needs nginx or another web server to serve `/media/`.
4. **The admin can't see or edit `profile_picture`.** `CustomUserAdmin` fieldsets list only `role` and `phone_number`.
5. **Roles don't control anything.** `setup_groups` creates permission groups, but nothing ever adds users to them. The `role` field is only displayed; there are no officer-only views or checks.

### Inconsistencies (not bugs, but worth knowing)
- **Soil thresholds are defined in three places.** The dashboard alerts, `ai._farm_soil_note`, and the dashboard template's soil bars each have their own. The template marks potassium as "low" below 20, while the alert uses below 30.
- **Fertilizer and depletion constants are copied in three files** (`explainer.py`, `sequential_pipeline.py`, `feedback/views.py`), along with the 2.6 conversion factor and the pH drift rule.
- **The rotation planner reloads the model pickles on every request.** `recommend_sequence` → `load_artifacts` reads them from disk instead of reusing the copies `ml/loader.py` already loaded.
- **Feedback and rotation take free-text crop names.** Feedback has to match crop names case-insensitively against the CSV, so a typo silently skips the soil update and only shows a warning.
- **Every crop is assumed to mature in 14 weeks** in the season tracker. That's wrong for Banana, Coffee, Cassava, Sugarcane, and other perennials.

### CLAUDE.md is out of date
It was written on 2026-09-07 and doesn't mention:
- the `notes` app
- `config/admin_site.py`
- `advisory/services.py`
- the profile page and profile pictures (Pillow, `MEDIA_*` settings)
- password reset and the `EMAIL_*` settings
- the `USE_HTTPS` flag
- the anonymous landing page and the credits page
- the `raw/` Kaggle data

It also says "uncommitted changes across most apps", but the tree is now clean.

### Testing
Two real tests: `accounts.LoginPageTests` and `dashboard.DashboardLatestSoilTests`. There is no CI.
