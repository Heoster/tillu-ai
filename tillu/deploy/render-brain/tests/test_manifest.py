import pytest
from pydantic import ValidationError
from app.manifest import UIManifest

def test_manifest_rejects_arbitrary_component():
    with pytest.raises(ValidationError):
        UIManifest(version=1,layout='chat',components=[{'type':'ExecuteJavaScript'}])
