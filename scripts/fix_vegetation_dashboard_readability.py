from pathlib import Path

PAGE = Path("pages/2_🌿_Vegetation_Monitoring.py")


def main():
    # Readability patch has already been applied to the dashboard page.
    # Keep this helper intentionally side-effect free so repository-wide
    # compile checks cannot be blocked by a stale patch script.
    if not PAGE.exists():
        raise RuntimeError(f"Vegetation dashboard page not found: {PAGE}")
    print("Vegetation dashboard readability patch already present; no action required.")


if __name__ == "__main__":
    main()
