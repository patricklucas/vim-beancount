import collections
import re

from deoplete.source.base import Base

try:
    from beancount.loader import load_file
    from beancount.core import data
    HAS_BEANCOUNT = True
except ImportError:
    HAS_BEANCOUNT = False

DIRECTIVES = [
    'open', 'close', 'commodity', 'txn', 'balance', 'pad', 'note', 'document',
    'price', 'event', 'query', 'custom'
]


class Source(Base):
    def __init__(self, vim):
        super().__init__(vim)
        self.vim = vim

        self.name = 'beancount'
        self.mark = '[bc]'
        self.matchers = ['matcher_full_fuzzy']
        self.filetypes = ['beancount']
        self.rank = 500
        self.min_pattern_length = 0
        self.attributes = collections.defaultdict(list)
        self.beancount_root = None
        self.auto_complete_delay = 10

    def on_init(self, context):
        if not HAS_BEANCOUNT:
            self.error('Importing beancount failed.')
        self.beancount_root = self.vim.eval("beancount#get_root()")

    def on_event(self, context):
        if context['event'] in ('Init', 'BufWritePost'):
            # Make cache on BufNewFile, BufRead, and BufWritePost
            self.__make_cache(context)

    def get_complete_position(self, context):
        m = re.search(r'\S*$', context['input'])
        return m.start() if m else -1

    def gather_candidates(self, context):
        attrs = self.attributes
        if re.match(r'^\d{4}[/-]\d\d[/-]\d\d \w*$', context['input']):
            return attrs['directives']
        # line that starts with whitespace (-> accounts)
        if re.match(r'^(\s)+[\w:]+$', context['input']):
            return attrs['accounts']
        # directive followed by account
        if re.search(
                r'(balance|document|note|open|close|pad(\s[\w:]+)?)'
                r'\s[\w:]+$',
                context['input']):
            return attrs['accounts']
        # events
        if re.search(r'event "[^"]*$', context['input']):
            return attrs['events']
        # commodity after number
        if re.search(r'\s([0-9]+|[0-9][0-9,]+[0-9])(\.[0-9]*)?\s\w+$',
                     context['input']):
            return attrs['commodities']
        if not context['complete_str']:
            return []
        first = context['complete_str'][0]
        if first == '#':
            return attrs['tags']
        elif first == '^':
            return attrs['links']
        elif first == '"':
            return attrs['payees']
        return []

    def __make_cache(self, context):
        if not HAS_BEANCOUNT:
            return

        entries, _, options = load_file(self.beancount_root)

        accounts = set()
        events = set()
        links = set()
        payees = set()
        tags = set()

        for entry in entries:
            if isinstance(entry, data.Open):
                accounts.add(entry.account)
            elif isinstance(entry, data.Transaction):
                if entry.payee:
                    payees.add(entry.payee)
            if hasattr(entry, 'links') and entry.links:
                links.update(entry.links)
            if hasattr(entry, 'tags') and entry.tags:
                tags.update(entry.tags)
            if isinstance(entry, data.Event):
                events.add(entry.type)

        self.attributes = {
            'accounts': [
                {'word': x, 'kind': 'account'} for x in sorted(accounts)],
            'events': [{
                'word': '"{}"'.format(x),
                'kind': 'event'
            } for x in sorted(events)],
            'commodities': [{
                'word': x,
                'kind': 'commodity'
            } for x in options['commodities']],
            'links': [{'word': '^' + w, 'kind': 'link'} for w in sorted(links)],
            'payees': [{
                'word': '"{}"'.format(w),
                'kind': 'payee'
            } for w in sorted(payees)],
            'tags': [{'word': '#' + w, 'kind': 'tag'} for w in sorted(tags)],
            'directives': [
                {'word': x, 'kind': 'directive'} for x in DIRECTIVES],
        }
