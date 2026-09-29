"""Regression tests for input validation on links rendered in the admin UI."""

import pytest
from pydantic import ValidationError

from schemas.member import MemberCreate, MemberUpdate
from schemas.registration import RegistrationCreate
from utils.sanitizer import is_safe_link

BASE_REGISTRATION = {
    "student_id": "2410511999",
    "full_name": "Link Test",
    "program_of_study": "S1 Informatika",
    "email": "link_test@upnvj.ac.id",
}


@pytest.mark.parametrize("url", ["javascript:alert(1)", " JavaScript:alert(1)", "data:text/html,<script>", "vbscript:x"])
def test_script_links_rejected(url):
    assert not is_safe_link(url)
    with pytest.raises(ValidationError):
        RegistrationCreate(**BASE_REGISTRATION, portfolio_url=url)
    with pytest.raises(ValidationError):
        MemberUpdate(portfolio_url=url)
    with pytest.raises(ValidationError):
        MemberCreate(**BASE_REGISTRATION, portfolio_url=url)


@pytest.mark.parametrize("url", [None, "", "https://github.com/user", "http://example.com", "github.com/user"])
def test_normal_links_accepted(url):
    assert is_safe_link(url)
    assert RegistrationCreate(**BASE_REGISTRATION, portfolio_url=url).portfolio_url == url
