from __future__ import annotations

from shared.tools.local_vector_store import build_kcmo_vector_index, default_kcmo_index_path


if __name__ == "__main__":
    count = build_kcmo_vector_index()
    print(f"Indexed {count} Kansas City knowledge records at {default_kcmo_index_path()}")
