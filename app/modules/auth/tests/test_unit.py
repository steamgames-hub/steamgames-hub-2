import pytest
from flask import url_for
from datetime import datetime, timedelta
from app import db
from app.modules.auth.models import User, PasswordResetToken
from app.modules.auth.repositories import UserRepository
from app.modules.auth.services import AuthenticationService
from app.modules.profile.repositories import UserProfileRepository


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    """
    with test_client.application.app_context():
        # Add HERE new elements to the database that you want to exist in the test context.
        # DO NOT FORGET to use db.session.add(<element>) and db.session.commit() to save the data.
        pass

    yield test_client


def test_login_success(test_client):
    response = test_client.post(
        "/login", data=dict(email="test@example.com", password="test1234"), follow_redirects=True
    )

    assert response.request.path != url_for("auth.login"), "Login was unsuccessful"

    test_client.get("/logout", follow_redirects=True)


def test_login_unsuccessful_bad_email(test_client):
    response = test_client.post(
        "/login", data=dict(email="bademail@example.com", password="test1234"), follow_redirects=True
    )

    assert response.request.path == url_for("auth.login"), "Login was unsuccessful"

    test_client.get("/logout", follow_redirects=True)


def test_login_unsuccessful_bad_password(test_client):
    response = test_client.post(
        "/login", data=dict(email="test@example.com", password="basspassword"), follow_redirects=True
    )

    assert response.request.path == url_for("auth.login"), "Login was unsuccessful"

    test_client.get("/logout", follow_redirects=True)


def test_signup_user_no_name(test_client):
    response = test_client.post(
        "/signup", data=dict(surname="Foo", email="test@example.com", password="test1234"), follow_redirects=True
    )
    assert response.request.path == url_for("auth.show_signup_form"), "Signup was unsuccessful"
    assert b"This field is required" in response.data, response.data


def test_signup_user_unsuccessful(test_client):
    email = "test@example.com"
    response = test_client.post(
        "/signup", data=dict(name="Test", surname="Foo", email=email, password="test1234"), follow_redirects=True
    )
    assert response.request.path == url_for("auth.show_signup_form"), "Signup was unsuccessful"
    assert f"Email {email} in use".encode("utf-8") in response.data


def test_signup_user_successful(test_client):
    response = test_client.post(
        "/signup",
        data=dict(name="Foo", surname="Example", email="foo@example.com", password="foo1234"),
        follow_redirects=True,
    )
    assert response.request.path == url_for("public.index"), "Signup was unsuccessful"


def test_service_create_with_profie_success(clean_database):
    data = {"name": "Test", "surname": "Foo", "email": "service_test@example.com", "password": "test1234"}

    AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 1
    assert UserProfileRepository().count() == 1


def test_service_create_with_profile_fail_no_email(clean_database):
    data = {"name": "Test", "surname": "Foo", "email": "", "password": "1234"}

    with pytest.raises(ValueError, match="Email is required."):
        AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 0
    assert UserProfileRepository().count() == 0


def test_service_create_with_profile_fail_no_password(clean_database):
    data = {"name": "Test", "surname": "Foo", "email": "test@example.com", "password": ""}

    with pytest.raises(ValueError, match="Password is required."):
        AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 0
    assert UserProfileRepository().count() == 0

def test_generate_reset_token_success(clean_database):
    """Debe generar un token válido y guardarlo en BD."""
    service = AuthenticationService()

    # Crear usuario
    user = User(email="reset@example.com", password="hashed")
    db.session.add(user)
    db.session.commit()

    # Generar token
    service.generate_reset_token("reset@example.com")

    # Comprobar que se haya creado el token en BD
    token = PasswordResetToken.query.filter_by(user_id=user.id).first()
    assert token is not None, "No se generó ningún token"
    assert token.token_hash is not None
    assert token.is_used is False
    assert token.is_expired is False

def test_validate_reset_token_expired(clean_database):
    """Debe devolver None si el token está expirado."""
    service = AuthenticationService()

    user = User(email="expired@example.com", password="1234")
    db.session.add(user)
    db.session.commit()

    # Token expirado manualmente
    token = PasswordResetToken(
        user_id=user.id,
        token_hash="abcd1234",
        expires_at=datetime.utcnow() - timedelta(minutes=5),  # pasado
    )
    db.session.add(token)
    db.session.commit()

    # Validación → None
    result = service.validate_reset_token("abcd1234")
    assert result is None, "Debería devolver None si está expirado"
    
def test_consume_reset_token_success(clean_database):
    """Debe actualizar la contraseña y marcar el token como usado."""
    service = AuthenticationService()

    user = User(email="consume@example.com", password="oldpass")
    db.session.add(user)
    db.session.commit()

    # Crear token válido
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=service._hash_token("validtoken"),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.session.add(token)
    db.session.commit()

    # Consumir token
    result = service.consume_reset_token("validtoken", "newpass123")
    db.session.refresh(token)
    db.session.refresh(user)

    # Validaciones
    assert result is True, "La función debería devolver True"
    assert token.is_used is True, "El token no fue marcado como usado"
    assert user.password != "oldpass", "La contraseña no se actualizó"