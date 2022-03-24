import re

emojis_pattern = re.compile(r"(::[\w\-]*::)")
emojis = {
    '::cross-mark::': '❌',
    '::check-mark::': '✅',
    '::warning::': '⚠',
    '::black-square-small::': '◾',
}

def parse_emoji(message):
    return emojis_pattern.sub(lambda m: emojis.get(m.group(), ''), message)
