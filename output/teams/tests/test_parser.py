from snooze_mattermostbot.bot_parser import parser

class TestParserLogic:
    def test_set(self):
        result,_ = parser('a = b')
        assert result == [['SET', 'a', 'b']]

    def test_array_append(self):
        result,_ = parser('a << b')
        assert result == [['ARRAY_APPEND', 'a', 'b']]

    def test_delete(self):
        result,_ = parser('delete a')
        assert result == [['DELETE', 'a']]

    def test_array_delete(self):
        result,_ = parser('a - b')
        assert result == [['ARRAY_DELETE', 'a', 'b']]

    def test_and(self):
        result,_ = parser('a = b and del c')
        assert result == [['SET', 'a', 'b'], ['DELETE', 'c']]

    def test_and_implicit(self):
        result,_ = parser('a = b c = d')
        assert result == [['SET', 'a', 'b'], ['SET', 'c', 'd']]

    def test_quotes(self):
        result,_ = parser('a = "b c d"')
        assert result == [['SET', 'a', 'b c d']]

    def test_comment(self):
        result, comment = parser('a = b test')
        assert result == [['SET', 'a', 'b']]
        assert comment == 'test'

    def test_and_parenthesis(self):
        result,comment = parser('(a = b & c + d) and (e - f) ~ g comment')
        assert result == [['SET', 'a', 'b'], ['ARRAY_APPEND', 'c', 'd'], ['ARRAY_DELETE', 'e', 'f'], ['DELETE', 'g']]
        assert comment == 'comment'
