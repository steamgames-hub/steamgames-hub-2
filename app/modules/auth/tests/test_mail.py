import pytest

from app.modules.auth.mail_util.token import generate_token
from app.modules.auth.models import User
from app import db


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


def test_send_verification_email_authenticated(test_client):
    with test_client.application.app_context():
        db.session.reset()
        u = User(email="verify@example.com", password="verify1234", verified=False)
        db.session.add(u)
        db.session.commit()

    test_client.post(
        "/login", data=dict(email="verify@example.com", password="verify1234"), follow_redirects=True
    )

    response = test_client.get("/verify", follow_redirects=True)

    assert b"A verification email has been sent to your address." in response.data, "Verification email not sent"


def test_verify_token_success(test_client, clean_database):
    with test_client.application.app_context():
        db.session.reset()
        u = User(email="verify@example.com", password="verify1234", verified=False)
        db.session.add(u)
        db.session.commit()

    test_client.post(
        "/login", data=dict(email="verify@example.com", password="verify1234"), follow_redirects=True
    )
    
    token = generate_token("verify@example.com")
    response = test_client.get(f"/verify/{str(token)}", follow_redirects=True)

    assert b"Your account has been verified successfully!" in response.data, "Verification unsuccessful"

    with test_client.application.app_context():
        u = User.query.filter_by(email="verify@example.com").first()
        assert u is not None and u.verified is True, "User not verified as expected"


def test_verify_token_invalid(test_client, clean_database):
    with test_client.application.app_context():
        db.session.reset()
        u = User(email="verify@example.com", password="verify1234", verified=False)
        db.session.add(u)
        db.session.commit()

    test_client.post(
        "/login", data=dict(email="verify@example.com", password="verify1234"), follow_redirects=True
    )

    invalid_token = "invalid-token"
    response = test_client.get(f"/verify/{invalid_token}", follow_redirects=True)

    assert b"The confirmation link is invalid or has expired." in response.data, "Verification unsuccessful"

    with test_client.application.app_context():
        u = User.query.filter_by(email="verify@example.com").first()
        assert u is not None and u.verified is False, "User not verified as expected"