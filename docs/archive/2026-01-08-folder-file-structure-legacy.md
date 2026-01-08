project-root/
│
├── .windsurfrules              # Symlink → /opt/_project_management/windsurfrules
├── .env.example                # Template (never .env)
├── .gitignore
│
├── README.md                   # Project overview + quick start
├── CHANGELOG.md                # Versioned history
├── tasks.md                    # Phase > Task > Subtask tracking
├── AGENTS.md                   # (optional) Agent-specific instructions
│
├── src/ or app/                # Main source code
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Config loading
│   ├── models/                 # Data models
│   ├── services/               # Business logic
│   ├── api/                    # API endpoints
│   └── utils/                  # Helpers
│
├── tests/                      # Mirrors src/ structure
│
├── scripts/                    # Utility & watchdog scripts
│   ├── watchdog_api.sh
│   ├── start_all.sh
│   └── stop_all.sh
│
├── config/                     # YAML/JSON configs (gitignored sensitive ones)
│
├── data/                       # Data files (gitignored)
│   ├── input/
│   ├── output/
│   └── cache/
│
├── logs/                       # Log files (gitignored)
│
├── migrations/ or alembic/     # Database migrations
│
├── dist/                       # Build output (gitignored)
│
├── venv/                       # Virtual environment (gitignored)
│
├── docs/
│   ├── README.md               # Index + structure map (REQUIRED)
│   ├── QUICKSTART.md           # 5-min setup (REQUIRED)
│   ├── CONFIGURATION.md        # All settings (REQUIRED)
│   ├── TROUBLESHOOTING.md      # Common issues (REQUIRED)
│   ├── SERVICES.md             # If project has services
│   ├── BUSINESS_MODEL.md       # Monetization (create early)
│   │
│   ├── guides/                 # How-to docs
│   ├── reference/              # Technical specs
│   │   ├── api.md
│   │   └── database.md
│   ├── operations/             # Ops procedures
│   ├── development/            # Contributor docs
│   └── archive/                # YYYY-MM-DD-topic format
│
└── .factory/                   # Factory.ai specific
    ├── prompts/                # Reusable agent prompts
    └── consultations/          # LLM consultation logs (gitignored)
