from urlparse import urljoin
from urlnormalizer import normalize_url
from normality import collapse_spaces

from memorious.helpers.rule import Rule
from memorious.helpers.dates import parse_date
from memorious.util import make_key


URL_TAGS = [('.//a', 'href'),
            ('.//img', 'src'),
            ('.//link', 'href'),
            ('.//iframe', 'src')]


def parse_html(context, data, result):
    context.log.info('Parse: %r', result.url)

    title = result.html.findtext('.//title')
    if title is not None and 'title' not in data:
        data['title'] = title

    include = context.params.get('include_paths')
    if include is None:
        roots = [result.html]
    else:
        roots = []
        for path in include:
            roots = roots + result.html.findall(path)

    seen = set()
    for root in roots:
        for tag_query, attr_name in URL_TAGS:
            for element in root.findall(tag_query):
                attr = element.get(attr_name)
                if attr is None:
                    continue

                url = normalize_url(urljoin(result.url, attr))
                if url is None or url in seen:
                    continue
                seen.add(url)

                tag = make_key(context.run_id, url)
                if context.check_tag(tag):
                    continue
                context.set_tag(tag, None)
                print url
                data = {'url': url}
                # Option to set the document title from the link text.
                if context.get('link_title', False):
                    data['title'] = collapse_spaces(element.text_content())
                elif element.get('title'):
                    data['title'] = collapse_spaces(element.get('title'))
                context.emit(rule='fetch', data=data)


def parse_for_metadata(context, data, result):
    meta = context.params.get('meta', {})
    date = context.params.get('date', {})

    meta_paths = meta
    meta_paths.update(date)

    for key, xpath in meta_paths.items():
        if result.html.find(xpath) is not None:
            value = collapse_spaces(result.html.find(xpath).text_content())
            if key in date.keys():
                value = parse_date(value)
            data[key] = value
            context.log.info("Metadata extracted [%s]: %s" % (key, value))

    return data


def parse(context, data):
    with context.http.rehash(data) as result:
        if result.html is not None:
            parse_html(context, data, result)

            # Get extra metadata from the DOM
            if context.params.get('meta') is not None or context.params.get('meta_date') is not None:
                meta = parse_for_metadata(context, data, result)
                data.update(meta)

        rules = context.params.get('store') or {'match_all': {}}
        if Rule.get_rule(rules).apply(result):
            context.emit(rule='store', data=data)
