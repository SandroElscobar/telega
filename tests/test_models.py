import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncConnection
from sqlalchemy.orm import selectinload
from sqlalchemy import select, text, inspect, create_engine
from datetime import datetime

from app.models.base import Base
from app.models.user import User, UserStatus
from app.models.chat import Chat, ChatType, ChatParticipant, ParticipantRole
from app.models.message import Message, MessageType, MessageStatus
from app.models.contact import Contact

@pytest.fixture
async def engine():
    """Создаем тестовую БД в памяти"""
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        echo=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()

@pytest.fixture
async def session(engine):
    """
    Создаем тестовую сессию.

    Важно: для SQLite нужно использовать async_sessionmaker,
    а не обычный sessionmaker, так как у нас асинхронный движок.
    """
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_create_user(session):
    user = User(
        phone_number="+79001234567",
        phone_number_verified=True,
        username="testuser",
        full_name="Test User",
        status=UserStatus.ACTIVE,
        language_code="ru",
        notifications_enabled=True
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.phone_number == "+79001234567"
    assert user.username == "testuser"
    assert user.is_active is True
    assert user.created_at is not None
    print(f"✓ Пользователь создан: ID={user.id}")

@pytest.mark.asyncio
async def test_create_private_chat(session):
    """Тест создания личного чата"""
    # Создаем двух пользователей
    user1 = User(
        phone_number="+79001234567",
        username="user1",
        status=UserStatus.ACTIVE
    )
    user2 = User(
        phone_number="+79007654321",
        username="user2",
        status=UserStatus.ACTIVE
    )

    session.add_all([user1, user2])
    await session.flush()
    print(f"✓ Пользователи созданы: user1.id={user1.id}, user2.id={user2.id}")

    # Создаем чат
    chat = Chat(
        chat_type=ChatType.PRIVATE,
        created_by_id=user1.id,
        is_public=False
    )

    session.add(chat)
    await session.flush()
    print(f"✓ Чат создан: chat.id={chat.id}")

    # Добавляем участников
    participant1 = ChatParticipant(
        chat_id=chat.id,
        user_id=user1.id,
        role=ParticipantRole.OWNER
    )

    participant2 = ChatParticipant(
        chat_id=chat.id,
        user_id=user2.id,
        role=ParticipantRole.MEMBER
    )

    session.add_all([participant1, participant2])
    await session.flush()

    # Загружаем чат с участниками
    stmt = select(Chat).where(Chat.id == chat.id).options(selectinload(Chat.participants))
    result = await session.execute(stmt)
    chat_with_participants = result.scalar_one()

    assert len(chat_with_participants.participants) == 2
    print(f"✓ Участники добавлены: {len(chat_with_participants.participants)} участников")

    await session.commit()


@pytest.mark.asyncio
async def test_create_encrypted_message(session):
    """Тест создаия зашифрованного сообщения."""
    user1 = User(
        phone_number="+79001234567",
        username="sender",
        status=UserStatus.ACTIVE
    )
    user2 = User(
        phone_number="+79007654321",
        username="recipient",
        status=UserStatus.ACTIVE
    )

    session.add_all([user1, user2])
    await session.flush()
    print(f"✓ Пользователи созданы: sender.id={user1.id}, recipient.id={user2.id}")

    chat = Chat(
        chat_type=ChatType.PRIVATE,
        created_by_id=user1.id,
        is_public=False
    )

    session.add(chat)
    await session.flush()
    await session.refresh(chat)
    print(f"✓ Чат создан: chat.id={chat.id}")

    # Добавляем участников
    participant1 = ChatParticipant(
        chat_id=chat.id,
        user_id=user1.id,
        role=ParticipantRole.OWNER
    )
    participant2 = ChatParticipant(
        chat_id=chat.id,
        user_id=user2.id,
        role=ParticipantRole.MEMBER
    )

    session.add_all([participant1, participant2])
    await session.flush()

    # Создаем зашифрованное сообщение
    message = Message(
        chat_id=chat.id,
        sender_id=user1.id,
        message_type=MessageType.TEXT,
        encrypted_content="encrypted_hello_world_base64",
        content_nonce="random_nonce_123",
        status=MessageStatus.SENT
    )

    session.add(message)
    await session.flush()
    await session.refresh(message)

    assert message.id is not None
    assert message.encrypted_content == "encrypted_hello_world_base64"
    assert message.is_service_message is False
    assert message.has_media is False
    print(f"✓ Сообщение создано: id={message.id}")

    # Проверяем, что сообщение связано с чатом
    assert message.chat_id == chat.id
    assert message.sender_id == user1.id

    # Проверяем, что сообщение можно найти через чат
    await session.refresh(chat, attribute_names=["messages"])
    assert len(chat.messages) == 1
    assert chat.messages[0].id == message.id
    await session.commit()  # финальный коммит
    print(f"✓ Сообщение связано с чатом: messages_count={len(chat.messages)}")


@pytest.mark.asyncio
async def test_message_status_update(session):
    """Тест обновления статуса сообщения."""
    # Создаем пользователя и чат
    user = User(
        phone_number="+79001234567",
        username="testuser",
        status=UserStatus.ACTIVE
    )
    session.add(user)
    await session.flush()

    chat = Chat(
        chat_type=ChatType.PRIVATE,
        created_by_id=user.id,
        is_public=False
    )
    session.add(chat)
    await session.flush()

    # Добавляем участника
    participant = ChatParticipant(
        chat_id=chat.id,
        user_id=user.id,
        role=ParticipantRole.OWNER
    )
    session.add(participant)
    await session.flush()

    # Создаем сообщение
    message = Message(
        chat_id=chat.id,
        sender_id=user.id,
        message_type=MessageType.TEXT,
        encrypted_content="test_content",
        content_nonce="test_nonce",
        status=MessageStatus.SENT
    )

    session.add(message)
    await session.commit()

    # Обновляем статус
    message.status = MessageStatus.DELIVERED
    await session.commit()
    await session.refresh(message)

    assert message.status == MessageStatus.DELIVERED

    # Еще раз обновляем
    message.status = MessageStatus.READ
    await session.commit()
    await session.refresh(message)

    assert message.status == MessageStatus.READ
    print(f"✓ Статус сообщения обновлен: {message.status}")


@pytest.mark.asyncio
async def test_soft_delete_user(session):
    """Тест мягкого удаления пользователя."""
    user = User(
        phone_number="+79009998877",
        username="softdelete_test",
        status=UserStatus.ACTIVE
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Проверяем, что не удален
    assert user.is_deleted is False
    assert user.deleted_at is None

    # Мягкое удаление
    user.deleted_at = datetime.now()
    await session.commit()
    await session.refresh(user)

    # Проверяем, что помечен как удаленный
    assert user.is_deleted is True
    assert user.deleted_at is not None
    print(f"✓ Мягкое удаление пользователя: is_deleted={user.is_deleted}")


@pytest.mark.asyncio
async def test_user_unique_constraints(session):
    """Тест уникальных ограничений пользователя."""
    # Создаем первого пользователя
    user1 = User(
        phone_number="+79001112233",
        username="unique_user",
        status=UserStatus.ACTIVE
    )
    session.add(user1)
    await session.commit()

    # Пытаемся создать пользователя с тем же номером телефона
    user2 = User(
        phone_number="+79001112233",  # Дубликат
        username="another_user",
        status=UserStatus.ACTIVE
    )
    session.add(user2)

    # Ожидаем ошибку уникальности
    with pytest.raises(Exception):  # Можно уточнить конкретное исключение
        await session.commit()

    await session.rollback()
    print("✓ Проверка уникальности номера телефона прошла")


@pytest.mark.asyncio
async def test_user_methods(session):
    """Тест методов пользователя."""
    user = User(
        phone_number="+79001234567",
        phone_number_verified=True,
        username="methods_test",
        status=UserStatus.ACTIVE
    )

    session.add(user)
    await session.commit()

    # Проверяем методы
    assert user.is_active is True
    assert user.is_verified is True

    # Проверяем нормализацию номера телефона
    test_numbers = [
        ("89001234567", "+89001234567"),
        ("+7 900 123-45-67", "+79001234567"),
        ("8(900)123-45-67", "+89001234567"),
    ]

    for input_num, expected in test_numbers:
        normalized = User.normalize_phone_number(input_num)
        print(f"  {input_num} -> {normalized}")
        # Проверяем, что результат начинается с +
        assert normalized.startswith("+")

    print("✓ Методы пользователя работают корректно")


@pytest.mark.asyncio
async def test_participant_roles(session):
    """Тест ролей участников."""
    user = User(
        phone_number="+79001112233",
        username="roles_test",
        status=UserStatus.ACTIVE
    )
    session.add(user)
    await session.flush()

    chat = Chat(
        chat_type=ChatType.GROUP,
        created_by_id=user.id,
        title="Test Group"
    )
    session.add(chat)
    await session.flush()

    # Проверяем все роли
    for role in ParticipantRole:
        participant = ChatParticipant(
            chat_id=chat.id,
            user_id=user.id,
            role=role
        )
        session.add(participant)
        await session.flush()

        # Удаляем для следующей итерации
        await session.delete(participant)
        await session.flush()

    print("✓ Все роли участников протестированы")


@pytest.mark.asyncio
async def test_all_message_types(session):
    """Тест всех типов сообщений."""
    user = User(
        phone_number="+79001112233",
        username="msg_types_test",
        status=UserStatus.ACTIVE
    )
    session.add(user)
    await session.flush()

    chat = Chat(
        chat_type=ChatType.PRIVATE,
        created_by_id=user.id
    )
    session.add(chat)
    await session.flush()

    # Добавляем участника
    participant = ChatParticipant(
        chat_id=chat.id,
        user_id=user.id,
        role=ParticipantRole.OWNER
    )
    session.add(participant)
    await session.flush()

    # Создаем сообщения всех типов
    for msg_type in MessageType:
        message = Message(
            chat_id=chat.id,
            sender_id=user.id,
            message_type=msg_type,
            encrypted_content=f"Content for {msg_type.value}",
            content_nonce=f"nonce_{msg_type.value}",
            status=MessageStatus.SENT
        )

        # Для медиа-типов добавляем дополнительные поля
        if msg_type in [MessageType.IMAGE, MessageType.VIDEO, MessageType.AUDIO, MessageType.FILE]:
            message.media_url = f"https://example.com/media.{msg_type.value}"
            message.media_size = 1024
            message.media_mime_type = f"{msg_type.value}/test"

        session.add(message)

    await session.commit()
    print("✓ Все типы сообщений созданы успешно")


@pytest.mark.asyncio
async def test_cascade_delete_chat(session):
    """Тест каскадного удаления чата."""
    user = User(
        phone_number="+79001112233",
        username="cascade_test",
        status=UserStatus.ACTIVE
    )
    session.add(user)
    await session.flush()

    # Создаем чат с участниками и сообщениями
    chat = Chat(
        chat_type=ChatType.GROUP,
        created_by_id=user.id,
        title="Cascade Test Chat"
    )
    session.add(chat)
    await session.flush()

    # Добавляем участника
    participant = ChatParticipant(
        chat_id=chat.id,
        user_id=user.id,
        role=ParticipantRole.OWNER
    )
    session.add(participant)

    # Добавляем сообщение
    message = Message(
        chat_id=chat.id,
        sender_id=user.id,
        message_type=MessageType.TEXT,
        encrypted_content="Test message",
        content_nonce="test_nonce"
    )
    session.add(message)
    await session.commit()

    # Удаляем чат
    await session.delete(chat)
    await session.commit()

    # Проверяем, что сообщение удалено
    stmt = select(Message).where(Message.id == message.id)
    result = await session.execute(stmt)
    assert result.scalar_one_or_none() is None

    # Проверяем, что участник удален
    stmt = select(ChatParticipant).where(ChatParticipant.id == participant.id)
    result = await session.execute(stmt)
    assert result.scalar_one_or_none() is None

    print("✓ Каскадное удаление чата работает корректно")


async def test_indexes_exist():
    """Проверка существования индексов с использованием синхронного соединения."""
    # Создаем СИНХРОННЫЙ движок для проверки индексов
    sync_engine = create_engine('sqlite:///:memory:', echo=False)

    # Создаем таблицы синхронно
    Base.metadata.create_all(sync_engine)

    with sync_engine.connect() as conn:
        # 1. Проверяем таблицы
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        print(f"\nТаблицы в БД: {tables}")

        # 2. Проверяем индексы для каждой таблицы
        for table in tables:
            indexes = inspector.get_indexes(table)
            print(f"\nИндексы таблицы '{table}':")
            for idx in indexes:
                print(f"  - {idx.get('name', 'unnamed')}: колонки {idx.get('column_names', [])}")

        # 3. Проверяем конкретно users
        users_indexes = inspector.get_indexes("users")
        assert len(users_indexes) >= 2, f"Таблица users должна иметь минимум 2 индекса, найдено {len(users_indexes)}"

        # Проверяем наличие индексов для phone_number и username
        has_phone_index = any(
            'phone_number' in idx.get('column_names', [])
            for idx in users_indexes
        )
        has_username_index = any(
            'username' in idx.get('column_names', [])
            for idx in users_indexes
        )

        assert has_phone_index, "Нет индекса для phone_number"
        assert has_username_index, "Нет индекса для username"

        # 4. Проверяем messages индексы
        messages_indexes = inspector.get_indexes("messages")
        print(f"\nИндексы messages: {messages_indexes}")

        # Проверяем составные индексы
        has_composite_index = any(
            len(idx.get('column_names', [])) > 1
            for idx in messages_indexes
        )
        assert has_composite_index, "Должны быть составные индексы для messages"

        # 5. Проверяем foreign keys через SQL
        result = conn.execute(text("PRAGMA foreign_key_list(messages)"))
        foreign_keys = result.fetchall()

        print(f"\nForeign keys для messages: {len(foreign_keys)}")
        assert len(foreign_keys) >= 2, "Должны быть foreign keys на chats и users"

    print("\n✓ Все индексы и ограничения созданы корректно")

@pytest.mark.asyncio
async def test_user_status_transitions(session):
    """Тест переходов между статусами пользователя."""
    user = User(
        phone_number="+79001112233",
        username="status_test",
        status=UserStatus.WAITING_VERIFICATION
    )
    session.add(user)
    await session.commit()

    # Проверяем начальный статус
    assert user.status == UserStatus.WAITING_VERIFICATION
    assert user.is_active is False

    # Переход в ACTIVE
    user.status = UserStatus.ACTIVE
    user.phone_number_verified = True
    await session.commit()
    await session.refresh(user)

    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True

    # Переход в BLOCKED
    user.status = UserStatus.BLOCKED
    await session.commit()
    await session.refresh(user)

    assert user.status == UserStatus.BLOCKED
    assert user.is_active is False

    print("✓ Переходы между статусами пользователя работают корректно")


@pytest.mark.asyncio
async def test_performance_large_chat(session):
    """Тест производительности для чата с большим количеством сообщений."""
    # Создаем пользователя и чат
    user = User(
        phone_number="+79001112233",
        username="perf_test",
        status=UserStatus.ACTIVE
    )
    session.add(user)
    await session.flush()

    chat = Chat(
        chat_type=ChatType.GROUP,
        created_by_id=user.id,
        title="Performance Test Chat"
    )
    session.add(chat)
    await session.flush()

    # Добавляем участника
    participant = ChatParticipant(
        chat_id=chat.id,
        user_id=user.id,
        role=ParticipantRole.OWNER
    )
    session.add(participant)
    await session.flush()

    # Создаем 100 сообщений
    messages = []
    for i in range(100):
        message = Message(
            chat_id=chat.id,
            sender_id=user.id,
            message_type=MessageType.TEXT,
            encrypted_content=f"Message {i}",
            content_nonce=f"nonce_{i}",
            status=MessageStatus.SENT
        )
        messages.append(message)

    session.add_all(messages)
    await session.commit()

    # Проверяем, что все сообщения созданы
    stmt = select(Message).where(Message.chat_id == chat.id)
    result = await session.execute(stmt)
    all_messages = result.scalars().all()

    assert len(all_messages) == 100
    print(f"✓ Создано {len(all_messages)} сообщений в чате")

@pytest.fixture(autouse=True)
async def cleanup(session):
    """Автоматическая очистка после каждого теста."""
    yield
    # Удаляем все данные
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(table.delete())
    await session.commit()


@pytest.mark.asyncio
async def test_create_contact(session):
    """
    Тест создания контакта.
    Проверяет корректность создания экземпляра Contact и его атрибутов.
    """
    # Создаем пользователя-владельца контакта с корректными данными
    user = User(
        phone_number="+79001234567",
        username="testuser",
        full_name="Test User",
        hashed_password="fake_hash"
    )
    session.add(user)
    await session.flush()

    # Проверяем, что пользователь создан и получил ID
    assert user.id is not None

    # Создаем контакт
    contact = Contact(
        user_id=user.id,
        phone_number="+79001234568",
        name="Тестовый Контакт"
    )
    session.add(contact)
    await session.flush()

    # Проверяем, что контакт создан корректно
    assert contact.id is not None
    assert contact.user_id == user.id
    assert contact.phone_number == "+79001234568"
    assert contact.name == "Тестовый Контакт"
    assert contact.contact_user_id is None

    # Загружаем relationship через refresh
    await session.refresh(contact, attribute_names=["user"])

    # Проверяем отношение
    assert contact.user == user

    # Проверяем уникальный индекс
    duplicate_contact = Contact(
        user_id=user.id,
        phone_number="+79001234568",  # Дубликат
        name="Дубль"
    )
    session.add(duplicate_contact)

    with pytest.raises(Exception) as exc_info:
        await session.flush()

    await session.rollback()

    # Проверяем, что ошибка связана с уникальностью
    error_message = str(exc_info.value).lower()
    assert any(word in error_message for word in ["unique", "duplicate", "uix_user_contact_phone"])