def test_imports():
    try:
        import fastapi
        import sqlalchemy
        import cryptography
        import jwt
        import firebase_admin
        print("Все библиотеки успешно импортированы!")
        print(f"FastAPI version: {fastapi.__version__}")
        print(f"SQLAlchemy version: {sqlalchemy.__version__}")
        return True
    except ImportError as e:
        print(f"Ошибка импорта: {e}")
        return False

if __name__ == "__main__":
    test_imports()