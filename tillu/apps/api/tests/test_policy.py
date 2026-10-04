from app.policy import validate_download_url

def test_rejects_plain_http():
    assert not validate_download_url('http://cbse.gov.in/a.pdf').allowed

def test_rejects_untrusted_domain():
    assert not validate_download_url('https://example.com/a.pdf').allowed
