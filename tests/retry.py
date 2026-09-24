import pytest
from app.retry import with_retry

def test_with_retry():
    @with_retry
    def test_function():
        return 1
    assert test_function() == 1

def test_with_retry_failure():
    @with_retry
    def test_function():
        raise Exception("Test failure")
    assert test_function() == 1