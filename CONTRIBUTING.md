# Contributing to UrbanLens

Thank you for contributing to UrbanLens! This document explains how to get started.

## Getting Started

1. **Fork** the repository and clone it locally.
2. Create a branch: `git checkout -b feature/your-feature-name`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the app: `streamlit run app.py`

## Code Style

- Python 3.10+, typed where practical.
- Follow existing module structure — one concern per file.
- Use parameterized SQL queries only; never format user data into SQL strings.
- All DB functions that touch restricted data must call `require_permission()`.
- Avoid TODOs in merged code.

## Adding a New Issue Type

1. Add the class name to `ISSUE_CLASSES` in `core/config.py`.
2. Add a human-readable label to `ISSUE_LABELS`.
3. Ensure your YOLOv8 model supports the class, or update `_BOX_COLORS` in `core/detect.py`.

## Testing

Run `python seed.py` to reset to a clean demo state.
Manually verify each role can only access its permitted pages and actions.

## Pull Request Checklist

- [ ] No broken imports or runtime errors on `streamlit run app.py`
- [ ] All RBAC checks preserved
- [ ] No hardcoded credentials or secrets
- [ ] `seed.py` still produces a working demo

## License

By contributing, you agree your contributions will be licensed under the MIT License.
