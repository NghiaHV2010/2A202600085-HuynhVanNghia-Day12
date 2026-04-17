"""Production readiness checker for Day 12 lab submission."""
from __future__ import annotations

import sys
from pathlib import Path


def check(name: str, passed: bool, detail: str = "") -> dict[str, object]:
    icon = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"  [{icon}] {name}{suffix}")
    return {"name": name, "passed": passed}


def has_any(text: str, candidates: list[str]) -> bool:
    return any(candidate in text for candidate in candidates)


def run_checks() -> bool:
    base = Path(__file__).parent
    results: list[dict[str, object]] = []

    print("\n" + "=" * 60)
    print(" Day 12 - Production Readiness Check")
    print("=" * 60)

    print("\nRequired files")
    required_files = [
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".env.example",
        "requirements.txt",
        "app/main.py",
        "app/config.py",
        "app/auth.py",
        "app/rate_limiter.py",
        "app/cost_guard.py",
        "utils/mock_llm.py",
    ]
    for rel_path in required_files:
        results.append(check(f"Exists: {rel_path}", (base / rel_path).exists()))

    results.append(
        check(
            "Cloud config available",
            (base / "railway.toml").exists() or (base / "render.yaml").exists(),
        )
    )

    print("\nSecurity and configuration")
    repo_root_gitignore = base.parent / ".gitignore"
    local_gitignore = base / ".gitignore"
    env_ignored = False
    for candidate in [local_gitignore, repo_root_gitignore]:
        if candidate.exists() and ".env" in candidate.read_text(encoding="utf-8"):
            env_ignored = True
            break
    results.append(check(".env ignored by git", env_ignored, "Add .env to .gitignore" if not env_ignored else ""))

    config_text = (base / "app/config.py").read_text(encoding="utf-8")
    results.append(
        check(
            "Rate limit env is configured",
            "RATE_LIMIT_PER_MINUTE" in config_text and '"10"' in config_text,
        )
    )
    results.append(
        check(
            "Monthly budget env is configured",
            "MONTHLY_BUDGET_USD" in config_text and '"10.0"' in config_text,
        )
    )

    secrets_hits: list[str] = []
    for rel_path in ["app/main.py", "app/config.py", "app/auth.py"]:
        text = (base / rel_path).read_text(encoding="utf-8")
        for marker in ["sk-", "password123", "hardcoded-secret"]:
            if marker in text:
                secrets_hits.append(f"{rel_path}:{marker}")
    results.append(
        check(
            "No obvious hardcoded secrets",
            len(secrets_hits) == 0,
            ", ".join(secrets_hits),
        )
    )

    print("\nAPI and reliability")
    main_text = (base / "app/main.py").read_text(encoding="utf-8")
    results.append(check("/ask endpoint defined", has_any(main_text, ['"/ask"', "'/ask'"])))
    results.append(check("/health endpoint defined", has_any(main_text, ['"/health"', "'/health'"])))
    results.append(check("/ready endpoint defined", has_any(main_text, ['"/ready"', "'/ready'"])))
    results.append(check("API key auth dependency used", "verify_api_key" in main_text))
    results.append(check("Rate limiter used", "rate_limiter.check(" in main_text))
    results.append(check("Cost guard used", "cost_guard.record_usage(" in main_text))
    results.append(check("Graceful SIGTERM handling", "SIGTERM" in main_text))
    results.append(check("Redis-backed history key present", "history:" in main_text))

    print("\nDocker quality")
    dockerfile_text = (base / "Dockerfile").read_text(encoding="utf-8")
    results.append(check("Multi-stage Docker build", "AS builder" in dockerfile_text and "AS runtime" in dockerfile_text))
    results.append(check("Non-root runtime user", "USER agent" in dockerfile_text))
    results.append(check("HEALTHCHECK configured", "HEALTHCHECK" in dockerfile_text))
    results.append(check("Slim base image used", "slim" in dockerfile_text.lower()))

    dockerignore_text = (base / ".dockerignore").read_text(encoding="utf-8")
    results.append(check(".dockerignore excludes .env", ".env" in dockerignore_text))
    results.append(check(".dockerignore excludes __pycache__", "__pycache__" in dockerignore_text))

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    pct = round((passed / total) * 100)

    print("\n" + "=" * 60)
    print(f" Result: {passed}/{total} checks passed ({pct}%)")
    print("=" * 60 + "\n")
    return pct == 100


if __name__ == "__main__":
    is_ready = run_checks()
    sys.exit(0 if is_ready else 1)
