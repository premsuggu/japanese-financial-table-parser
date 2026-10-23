## Agent Guidelines
### Code Quality & Maintenance
- Ensure the codebase is well-maintained and follows best practices in terms of modularity, readability, documentation, and performance.
- Always use best practices for code quality, including but not limited to:
    - Code reviews before merging changes
    - Static analysis tools for linting and type checking
    - Adherence to established coding standards and conventions
- Use coding examples wherever necessary to explain concepts in a simple and understandable way.

### Planning & Implementation Process
- **Before starting any task:** Always propose a detailed implementation plan and obtain explicit approval before proceeding.
- **Implementation plan must include:**
    - Clear description of the task objectives and scope
    - All technical details (algorithms, data structures, design patterns)
    - Complete list of dependencies, libraries, and frameworks that will be used
    - Important code snippets or pseudocode to illustrate the approach
    - Estimated timeline and potential risks or challenges
    - After each implementation step, provide a summary of the changes made and any relevant code snippets or examples to illustrate the modifications.

### Testing & Quality Assurance
- After completing any task, ensure the code is properly tested with:
    - Unit tests for individual components and functions
    - Integration tests to verify interactions between modules
    - All tests should pass before considering a task complete
- **Important:** Never create test or debug related files in the root directory. All test files must be placed in the `tests/` directory with appropriate subdirectories matching the source structure.

### Version Control & Deployment
- **Never push code to git independently.** Only push code to git after obtaining explicit approval from the user.
- Wait for user confirmation at each milestone before committing changes to the repository.

### Documentation Standards
- After each completed task, update the documentation to reflect all changes made to the codebase.
- Provide documentation in a modular way:
    - High-level documentation explaining overall concepts and workflows
    - Detailed explanations with in-depth technical details
    - All documentation should be placed in the `docs/` directory with clear organization
    - Explanatory docs and work logs shall be maintained separately in modular way.
- Always include references to relevant code snippets in the documentation.
- Provide both conceptual explanations and practical examples to help users understand the codebase better. Provide clear explanations such that even a new developer can understand the codebase and its functionality.

### Communication & Clarification
- Never assume anything about requirements or implementation details.
- Always ask for clarifications if any requirements, specifications, or details are unclear.
- Request explicit approval before making architectural decisions or significant changes.

### Dependency Management
- Never install unnecessary packages or libraries in the system without explicit user permission.
- If you have installed packages without prior permission, immediately inform the user with:
    - A list of packages that were installed
    - Reasons why they were needed
    - A request for permission to keep or remove them
- Follow up accordingly based on user feedback.

### Privilege & Capability Limitations
- If you lack the necessary privileges to perform any task, inform the user immediately.
- Provide a detailed explanation of:
    - What task requires elevated privileges
    - Why those privileges are needed
    - Step-by-step instructions for the user to complete the task manually

## Project context (added 2026-10-23; the rules above are unchanged)
- Goal: parse a Japanese consolidated balance-sheet page (text PDF or scan) into a structured table with labels, values,
  columns, hierarchy, units and signs. **No hard-coded coordinates**: every tolerance must be a fraction of a length
  measured on the page (see `tests/integration/test_layout_invariance.py`).
- Start with `README.md`, then `docs/README.md` (index) and `docs/worklog/phase2-worklog.md` (current status).
- Code map: only `pdf_io.py` imports PyMuPDF; extraction in `strategies/`; checks in `validate.py` and
  `rules/statement_rules.yaml`; OCR engines run as workers in their own venv (`tools/ocr/`), never imported directly.
- Quality gates before calling a task done: `python -m pytest -q`, `ruff check src tests`, `ruff format --check src tests`, `mypy`.
- Every install goes into `docs/worklog/installed-packages.md`; deletions of installs or caches need the user's OK, and
  nothing in `~/.cache/huggingface` or `~/.cache/torch` that this project did not create may be touched.
- The UI handles financial documents: it must stay bound to localhost.
- Corpus PDFs in `data/corpus/` are untrusted input: run ad-hoc Python that reads them with `python -I`.
- Ground truth in `tests/fixtures/ground_truth/` was written by the agent and awaits human review; do not present
  scores against it as independent.
- Docs hygiene: update the README status table and the work log after each task; keep explanations and work logs separate.
