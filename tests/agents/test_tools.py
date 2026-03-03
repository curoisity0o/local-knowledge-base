import pytest
from src.agents.tools import safe_eval

def test_safe_eval_basic_operations():
    """测试安全表达式求值基本操作"""
    assert safe_eval("2 + 3", {}) == 5
    assert safe_eval("10 - 4", {}) == 6
    assert safe_eval("3 * 4", {}) == 12
    assert safe_eval("12 / 3", {}) == 4

def test_safe_eval_with_variables():
    """测试带变量的表达式求值"""
    names = {"x": 5, "y": 3}
    assert safe_eval("x + y", names) == 8
    assert safe_eval("x * y - 2", names) == 13

def test_safe_eval_security():
    """测试安全性 - 危险表达式应被阻止"""
    with pytest.raises(Exception):
        safe_eval("__import__('os').system('ls')", {})
    
    with pytest.raises(Exception):
        safe_eval("open('/etc/passwd').read()", {})