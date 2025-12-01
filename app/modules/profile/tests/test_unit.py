import pytest

from app import db
from app.modules.auth.models import User
from app.modules.conftest import logout
from app.modules.profile.models import UserProfile


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extiende el test_client para agregar datos específicos para pruebas de módulo.
    """
    with test_client.application.app_context():
        # Crear usuario de prueba
        user_test = User(email="user@example.com", password="test1234")
        db.session.add(user_test)
        db.session.commit()

        # Crear perfil asociado
        profile = UserProfile(user_id=user_test.id, name="Name", surname="Surname")
        db.session.add(profile)
        db.session.commit()

    yield test_client


def test_edit_profile_page_get(test_client):
    """
    Testea el flujo completo de login + 2FA + acceso a /profile/edit.
    """
    # 1️⃣ Login inicial
    resp = test_client.post(
        "/login",
        data={"email": "user@example.com", "password": "test1234"},
        follow_redirects=False
    )
    assert resp.status_code == 302
    # Permite login directo o con 2FA según config
    assert resp.location == "/" or "/two-factor/" in resp.location

    # 2️⃣ Obtener el usuario y su código de 2FA
    user = User.query.filter_by(email="user@example.com").first()
    assert user is not None
    if test_client.application.config.get("TWO_FACTOR_ENABLED", True):
        assert user.two_factor_code is not None
        # 3️⃣ Enviar el código al endpoint correcto
        two_factor_url = f"/two-factor/{user.id}"
        resp = test_client.post(
            two_factor_url,
            data={"code": user.two_factor_code},
            follow_redirects=True
        )
        # Si el login fue correcto, debería redirigir a alguna vista interna (no 404 ni login)
        assert resp.status_code == 200
        assert b"Welcome" in resp.data or b"Profile" in resp.data or b"Steam" in resp.data
    # 4️⃣ Acceder a la página de edición de perfil (requiere sesión)
    response = test_client.get(f"/profile/edit/{user.id}")
    # Verificaciones claras
    assert response.status_code == 200, "El acceso a /profile/edit no devolvió 200 OK"
    assert b"Edit" in response.data or b"Profile" in response.data, \
        "La página de edición de perfil no contiene texto esperado"
    # 5️⃣ Logout al final del test
    logout(test_client)


def test_change_preference_save_drafts(test_client):
    """
    Tests to modify the profile attribute "save_drafts" via a PUT request.
    """
    # 1️⃣ Login inicial
    resp = test_client.post(
        "/login",
        data={"email": "user@example.com", "password": "test1234"},
        follow_redirects=False
    )
    assert resp.status_code == 302
    # Permite login directo o con 2FA según config
    assert resp.location == "/" or "/two-factor/" in resp.location

    # 2️⃣ Obtener el usuario y su código de 2FA
    user = User.query.filter_by(email="user@example.com").first()
    assert user is not None
    if test_client.application.config.get("TWO_FACTOR_ENABLED", True):
        assert user.two_factor_code is not None
        # 3️⃣ Enviar el código al endpoint correcto
        two_factor_url = f"/two-factor/{user.id}"
        resp = test_client.post(
            two_factor_url,
            data={"code": user.two_factor_code},
            follow_redirects=True
        )
        # Si el login fue correcto, debería redirigir a alguna vista interna (no 404 ni login)
        assert resp.status_code == 200
        assert b"Welcome" in resp.data or b"Profile" in resp.data or b"Steam" in resp.data
    response = test_client.put("/profile/save_drafts")
    assert response.status_code == 200, "The preference was changed succesfully"
    logout(test_client)
    