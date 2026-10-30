"""Release-only static checks; not a host loader or an Agent behavior test.

YAML is parsed by PyYAML SafeLoader, rejecting duplicate keys. Markdown support is
intentionally restricted: ordinary inline links, backtick file references in the
entry, and standalone explicit HTML anchors. No implicit heading slug guessing,
reference-style links, remote URL validation, or model execution is performed.
"""
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote, urlsplit
import yaml


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def parse_yaml(text):
    return yaml.load(text, Loader=UniqueSafeLoader)


def prose(text):
    """Remove fenced blocks, respecting marker type and closing length."""
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            continue
        if match:
            fence = match[1]
        else:
            lines.append(line)
    return '\n'.join(lines)


def explicit_anchors(text):
    return re.findall(r'^\s*<a id=[\"\']([A-Za-z0-9_-]+)[\"\']></a>\s*$', prose(text), re.M)


def resolve_reference(source, reference):
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if path.startswith('/') or '\\' in path:
        raise ValueError(f'non-relative local reference: {reference}')
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path)) if path else source
    if target == '..' or target.startswith('../'):
        raise ValueError(f'local reference escapes package: {reference}')
    return target, unquote(parsed.fragment)


def validate_reference(texts, source, reference):
    resolved = resolve_reference(source, reference)
    if resolved is None:
        return
    target, fragment = resolved
    if target not in texts:
        raise ValueError(f'{source}: missing local reference {reference}')
    if fragment and explicit_anchors(texts[target]).count(fragment) != 1:
        raise ValueError(f'{source}: missing/duplicate explicit anchor {reference}')


def validate_documents(texts):
    errors = []
    try:
        entry = texts['SKILL.md']
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', entry, re.S)
        if not match:
            raise ValueError('SKILL.md: missing frontmatter')
        data = parse_yaml(match[1])
        if not isinstance(data, dict):
            raise ValueError('SKILL.md: frontmatter must be a mapping')
        for key in ('name', 'description'):
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError(f'SKILL.md: {key} must be a nonempty string')
        metadata = data.get('metadata')
        if not isinstance(metadata, dict) or not isinstance(metadata.get('version'), str) or not metadata['version'].strip():
            raise ValueError('SKILL.md: metadata.version must be a nonempty string')
    except (KeyError, ValueError, TypeError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    for source, text in texts.items():
        if not source.endswith('.md'):
            continue
        anchors = explicit_anchors(text)
        if len(set(anchors)) != len(anchors):
            errors.append(f'{source}: duplicate explicit anchors')
        links = re.findall(r'!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)', prose(text))
        if source == 'SKILL.md':
            links += re.findall(r'`(references/[^`\n]+)`', prose(text))
        for link in links:
            try:
                validate_reference(texts, source, link.strip('<>'))
            except ValueError as exc:
                errors.append(str(exc))
    return errors


MINIMUM = ['../SKILL.md', '../references/00_expert_entry/hard_rules.md',
           '../references/07_integration_pack/task_routing_rules.md#routing-entry']
ROUTES = 'references/07_integration_pack/task_routing_rules.md'
FORMATS = 'references/00_expert_entry/response_formats.md'


def validate_host_contract(root):
    root = Path(root)
    texts = {p.relative_to(root).as_posix(): p.read_text(encoding='utf-8')
             for p in root.rglob('*.md') if '.git' not in p.parts}
    errors = []
    try:
        config = parse_yaml((root / 'agents/claude-code.yaml').read_text(encoding='utf-8'))
        if config['startup']['required_files'] != MINIMUM:
            raise ValueError('startup.required_files must match the ordered minimum contract')
        if config['skill']['entry'] != '../SKILL.md':
            raise ValueError('skill.entry must point to SKILL.md')
        for group in ('required_files', 'debug_files', 'performance_files'):
            for reference in config['startup'][group]:
                validate_reference(texts, 'agents/claude-code.yaml', reference)
        for reference in config['usage']['routing']:
            validate_reference(texts, 'agents/claude-code.yaml', reference)
        entry_section = texts['SKILL.md'].split('## 最小启动协议\n', 1)[1].split('\n## ', 1)[0]
        for required in MINIMUM[1:]:
            if f'`{required.removeprefix("../")}`' not in entry_section:
                raise ValueError(f'SKILL minimum startup drift: {required}')
        baseline = texts['references/07_integration_pack/retrieval_policy.md'].split('必读基线只有', 1)[1].split('\n', 1)[0]
        for required in ('../../SKILL.md', '../00_expert_entry/hard_rules.md', 'task_routing_rules.md#routing-entry'):
            if f'`{required}`' not in baseline:
                raise ValueError(f'retrieval minimum startup drift: {required}')
        for kind in ('debug', 'android', 'api', 'performance', 'architecture'):
            validate_reference(texts, ROUTES, f'#route-{kind}')
            validate_reference(texts, FORMATS, f'#format-{kind}')
        validate_reference(texts, ROUTES, '#symptom-shortcuts')
        validate_reference(texts, ROUTES, '#route-verification')
    except (KeyError, IndexError, TypeError, ValueError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return errors


if __name__ == '__main__':
    import sys
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    errors = validate_host_contract(root)
    print('\n'.join(errors) if errors else 'PASS: illustrative host configuration and explicit route/template anchors (static only)')
    raise SystemExit(bool(errors))
