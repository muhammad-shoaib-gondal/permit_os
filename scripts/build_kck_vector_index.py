from shared.tools.local_vector_store import build_kck_vector_index, default_kck_index_path


if __name__ == "__main__":
    count = build_kck_vector_index()
    print(f"Indexed {count} KCK knowledge records at {default_kck_index_path()}")
