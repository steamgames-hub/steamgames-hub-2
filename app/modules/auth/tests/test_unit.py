import json

import pytest
from flask import url_for

from app import db
from app.modules.auth.models import User, UserRole
from app.modules.auth.repositories import UserRepository
from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType
from app.modules.profile.models import UserProfile
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
    assert b"Please, verify your account" in response.data, "Signup was unsuccessful"


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


def test_curator_can_create_incident(test_client):
    # ensure test user exists and make them a curator
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    # ensure profile exists
    from app.modules.profile.models import UserProfile

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User", save_drafts=False)
        db.session.add(profile)
        db.session.commit()

    user.role = "curator"
    db.session.commit()

    # login
    # ensure any previously-authenticated test client is logged out first
    test_client.get("/logout", follow_redirects=True)
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True)
    assert resp.status_code == 200

    # create a DSMetaData and DataSet to reference
    md = DSMetaData(title="t", description="d", publication_type=PublicationType.NONE)
    db.session.add(md)
    db.session.commit()
    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id)
    db.session.add(ds)
    db.session.commit()

    payload = {"dataset_id": ds.id, "description": "Something wrong with DB"}
    r = test_client.post("/dataset/incidents", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201
    body = json.loads(r.data)
    assert body.get("id") is not None
    assert body.get("dataset_id") == ds.id


def test_non_curator_cannot_create_incident(test_client):
    # ensure test user exists and is not a curator
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    user.role = "user"
    db.session.commit()

    # login
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True)
    assert resp.status_code == 200

    payload = {"dataset_id": 1, "description": "Do not allow"}
    r = test_client.post("/dataset/incidents", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 403


def test_curator_can_create_incident(test_client):
    # ensure test user exists and make them a curator
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    # ensure profile exists
    from app.modules.profile.models import UserProfile

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User", save_drafts=False)
        db.session.add(profile)
        db.session.commit()

    user.role = UserRole.CURATOR
    db.session.commit()

    # login
    # ensure any previously-authenticated test client is logged out first
    test_client.get("/logout", follow_redirects=True)
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True)
    assert resp.status_code == 200

    # create a DSMetaData and DataSet to reference
    md = DSMetaData(title="t", description="d", publication_type=PublicationType.NONE)
    db.session.add(md)
    db.session.commit()
    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id)
    db.session.add(ds)
    db.session.commit()

    payload = {"dataset_id": ds.id, "description": "Something wrong with DB"}
    r = test_client.post("/dataset/incidents", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201
    body = json.loads(r.data)
    assert body.get("id") is not None
    assert body.get("dataset_id") == ds.id


def test_non_curator_cannot_create_incident(test_client):
    # ensure test user exists and is not a curator
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    user.role = UserRole.USER
    db.session.commit()

    # login
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True)
    assert resp.status_code == 200

    payload = {"dataset_id": 1, "description": "Do not allow"}
    r = test_client.post("/dataset/incidents", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 403


def test_upgrade_user_role_success(test_client):

    admin = User.query.filter_by(email="admin_test@example.com").first()
    if not admin:
        admin = User(email="admin_test@example.com", password="test1234", verified=True)
        db.session.add(admin)
        db.session.commit()

    if not admin.profile:
        profile = UserProfile(user_id=admin.id, name="Test", surname="Admin")
        db.session.add(profile)
        db.session.commit()

    admin.role = UserRole.ADMIN
    db.session.commit()

    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    user.role = UserRole.USER
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post(
        "/login", data={"email": "admin_test@example.com", "password": "test1234"}, follow_redirects=True
    )
    assert response.status_code == 200

    response = test_client.post(f"/user/upgrade/{user.id}", follow_redirects=True)
    assert response.status_code == 200, "Upgrade request failed"

    db.session.refresh(user)
    assert user.role == UserRole.CURATOR, "User role was not upgraded"


def test_upgrade_user_role_unsuccessful(test_client):

    user1 = User.query.filter_by(email="user1_test@example.com").first()
    if not user1:
        user1 = User(email="user1_test@example.com", password="test1234", verified=True)
        db.session.add(user1)
        db.session.commit()

    if not user1.profile:
        profile = UserProfile(user_id=user1.id, name="User1", surname="Test")
        db.session.add(profile)
        db.session.commit()

    user1.role = UserRole.USER
    db.session.commit()

    user2 = User.query.filter_by(email="user2_test@example.com").first()
    if not user2:
        user2 = User(email="user2_test@example.com", password="test1234", verified=True)
        db.session.add(user2)
        db.session.commit()

    if not user2.profile:
        profile = UserProfile(user_id=user2.id, name="User2", surname="Test")
        db.session.add(profile)
        db.session.commit()

    user2.role = UserRole.USER
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post(
        "/login", data={"email": "user1_test@example.com", "password": "test1234"}, follow_redirects=True
    )
    assert response.status_code == 200

    response = test_client.post(f"/user/upgrade/{user2.id}", follow_redirects=True)
    assert response.status_code == 403, "Upgrade request should have failed"

    db.session.refresh(user2)
    assert user2.role == UserRole.USER, "User role was incorrectly upgraded"


def test_downgrade_user_role_success(test_client):

    admin = User.query.filter_by(email="admin_test@example.com").first()
    if not admin:
        admin = User(email="admin_test@example.com", password="test1234", verified=True)
        db.session.add(admin)
        db.session.commit()

    if not admin.profile:
        profile = UserProfile(user_id=admin.id, name="Test", surname="Admin")
        db.session.add(profile)
        db.session.commit()

    admin.role = UserRole.ADMIN
    db.session.commit()

    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    user.role = UserRole.CURATOR
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post(
        "/login", data={"email": "admin_test@example.com", "password": "test1234"}, follow_redirects=True
    )
    assert response.status_code == 200

    response = test_client.post(f"/user/downgrade/{user.id}", follow_redirects=True)
    assert response.status_code == 200, "Downgrade request failed"

    db.session.refresh(user)
    assert user.role == UserRole.USER, "User role was not downgraded"


def test_downgrade_user_role_unsuccessful(test_client):

    user1 = User.query.filter_by(email="user1_test@example.com").first()
    if not user1:
        user1 = User(email="user1_test@example.com", password="test1234", verified=True)
        db.session.add(user1)
        db.session.commit()

    if not user1.profile:
        profile = UserProfile(user_id=user1.id, name="User1", surname="Test")
        db.session.add(profile)
        db.session.commit()

    user1.role = UserRole.USER
    db.session.commit()

    user2 = User.query.filter_by(email="user2_test@example.com").first()
    if not user2:
        user2 = User(email="user2_test@example.com", password="test1234", verified=True)
        db.session.add(user2)
        db.session.commit()

    if not user2.profile:
        profile = UserProfile(user_id=user2.id, name="User2", surname="Test")
        db.session.add(profile)
        db.session.commit()

    user2.role = UserRole.CURATOR
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post(
        "/login", data={"email": "user1_test@example.com", "password": "test1234"}, follow_redirects=True
    )
    assert response.status_code == 200

    response = test_client.post(f"/user/downgrade/{user2.id}", follow_redirects=True)
    assert response.status_code == 403, "Downgrade request should have failed"

    db.session.refresh(user2)
    assert user2.role == UserRole.CURATOR, "User role was incorrectly downgraded"


def test_list_all_users_admin_access(test_client):
    # Crear usuario admin y loguear
    admin = User(email="admin_list@example.com", password="test1234", verified=True, role=UserRole.ADMIN)
    db.session.add(admin)
    db.session.commit()
    if not admin.profile:
        profile = UserProfile(user_id=admin.id, name="Admin", surname="Test")
        db.session.add(profile)
        db.session.commit()
    test_client.get("/logout", follow_redirects=True)
    test_client.post("/login", data={"email": admin.email, "password": "test1234"}, follow_redirects=True)
    # Acceso permitido
    resp = test_client.get("/users")
    assert resp.status_code == 200
    assert b"Users" in resp.data or b"Role" in resp.data


def test_list_all_users_non_admin_forbidden(test_client):
    # Crear usuario normal y loguear
    user = User(email="user_list@example.com", password="test1234", verified=True, role=UserRole.USER)
    db.session.add(user)
    db.session.commit()
    if not user.profile:
        profile = UserProfile(user_id=user.id, name="User", surname="Test")
        db.session.add(profile)
        db.session.commit()
    test_client.get("/logout", follow_redirects=True)
    test_client.post("/login", data={"email": user.email, "password": "test1234"}, follow_redirects=True)
    # Acceso denegado
    resp = test_client.get("/users")
    assert resp.status_code == 403


def test_delete_user_admin_success(test_client):
    # Crear admin y usuario a borrar
    admin = User(email="admin_delete@example.com", password="test1234", verified=True, role=UserRole.ADMIN)
    user = User(email="user_delete@example.com", password="test1234", verified=True, role=UserRole.USER)
    db.session.add(admin)
    db.session.add(user)
    db.session.commit()
    if not admin.profile:
        profile = UserProfile(user_id=admin.id, name="Admin", surname="Test")
        db.session.add(profile)
        db.session.commit()
    if not user.profile:
        profile = UserProfile(user_id=user.id, name="User", surname="Test")
        db.session.add(profile)
        db.session.commit()
    test_client.get("/logout", follow_redirects=True)
    test_client.post("/login", data={"email": admin.email, "password": "test1234"}, follow_redirects=True)
    # Borrar usuario
    resp = test_client.delete(f"/user/delete/{user.id}")
    assert resp.status_code == 200
    assert b"deleted" in resp.data
    # Usuario ya no existe
    assert User.query.get(user.id) is None


def test_delete_user_non_admin_forbidden(test_client):
    # Crear usuario normal y otro usuario
    user1 = User(email="user1_delete@example.com", password="test1234", verified=True, role=UserRole.USER)
    user2 = User(email="user2_delete@example.com", password="test1234", verified=True, role=UserRole.USER)
    db.session.add(user1)
    db.session.add(user2)
    db.session.commit()
    if not user1.profile:
        profile = UserProfile(user_id=user1.id, name="User1", surname="Test")
        db.session.add(profile)
        db.session.commit()
    if not user2.profile:
        profile = UserProfile(user_id=user2.id, name="User2", surname="Test")
        db.session.add(profile)
        db.session.commit()
    test_client.get("/logout", follow_redirects=True)
    test_client.post("/login", data={"email": user1.email, "password": "test1234"}, follow_redirects=True)
    # Intentar borrar otro usuario
    resp = test_client.delete(f"/user/delete/{user2.id}")
    assert resp.status_code == 403 or resp.status_code == 400
    # Usuario sigue existiendo
    assert User.query.get(user2.id) is not None
