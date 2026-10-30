"""Structural regressions only: never evidence of live Agent/GPU acceptance."""
from pathlib import Path
import shutil
import tempfile
import unittest

from host_contract import (explicit_anchors, parse_yaml, resolve_reference,
                           validate_documents, validate_host_contract)

ROOT = Path(__file__).resolve().parents[1]


class HostContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('SKILL.md', 'agents/claude-code.yaml',
                     'references/07_integration_pack/retrieval_policy.md',
                     'references/07_integration_pack/task_routing_rules.md',
                     'references/00_expert_entry/response_formats.md',
                     'references/00_expert_entry/hard_rules.md',
                     'references/00_expert_entry/debug_priority.md',
                     'references/00_expert_entry/performance_priority.md'):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def change(self, name, old, new):
        path = self.root / name
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))

    def test_repository_contract(self):
        self.assertEqual(validate_host_contract(ROOT), [])

    def test_old_startup_rejected(self):
        self.change('agents/claude-code.yaml', '../SKILL.md"\n    -', '../references/00_expert_entry/role.md"\n    -')
        self.assertTrue(validate_host_contract(self.root))

    def test_fragment_only_hard_rules_rejected(self):
        self.change('agents/claude-code.yaml', 'hard_rules.md"', 'hard_rules.md#partial"')
        self.assertTrue(validate_host_contract(self.root))

    def test_entry_drift_rejected(self):
        self.change('SKILL.md', 'task_routing_rules.md#routing-entry', 'task_routing_rules.md#missing')
        self.assertTrue(validate_host_contract(self.root))

    def test_retrieval_drift_rejected(self):
        self.change('references/07_integration_pack/retrieval_policy.md', '`../../SKILL.md`', '`../../OLD.md`')
        self.assertTrue(validate_host_contract(self.root))

    def test_four_scenario_route_and_template_drift(self):
        # Android black screen uses debug+android; sync/VUID also uses api.
        for kind in ('debug', 'android', 'api', 'performance', 'architecture'):
            for name, anchor in (('references/07_integration_pack/task_routing_rules.md', 'route-'),
                                 ('references/00_expert_entry/response_formats.md', 'format-')):
                with self.subTest(kind=kind, name=name):
                    p = self.root / name
                    original = p.read_text()
                    p.write_text(original.replace(f'id="{anchor}{kind}"', f'id="missing-{kind}"'))
                    self.assertTrue(validate_host_contract(self.root))
                    p.write_text(original)

    def test_duplicate_yaml_rejected(self):
        with self.assertRaises(ValueError):
            parse_yaml('name: first\nname: second\n')

    def test_unsafe_yaml_rejected(self):
        with self.assertRaises(Exception):
            parse_yaml('!!python/object/apply:os.system ["echo never-run"]')

    def test_fenced_and_inline_anchor_examples_not_targets(self):
        text = '```html\n<a id="fake"></a>\n```\nExample `<a id="fake"></a>`\n<a id="real"></a>'
        self.assertEqual(explicit_anchors(text), ['real'])

    def test_path_escape_rejected(self):
        for path in ('../outside.md', '%2e%2e/outside.md', '/absolute.md', r'..\outside.md'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                resolve_reference('SKILL.md', path)

    def test_pack_documents(self):
        paths = [ROOT / p for p in ('SKILL.md', 'LICENSE', 'README_EN.md')]
        paths += list((ROOT / 'references').rglob('*.md'))
        texts = {p.relative_to(ROOT).as_posix(): p.read_text() for p in paths}
        self.assertEqual(validate_documents(texts), [])
        route = 'references/07_integration_pack/task_routing_rules.md'
        texts[route] = texts[route].replace('id="routing-entry"', 'id="missing"')
        self.assertTrue(validate_documents(texts))

    def test_yaml_types_and_duplicate_frontmatter(self):
        for fields in ('name: []\ndescription: valid', 'name: first\nname: second\ndescription: valid'):
            self.assertTrue(validate_documents({'SKILL.md': f'---\n{fields}\nmetadata:\n  version: 1.0.9\n---\n'}))

    def test_duplicate_anchor_rejected(self):
        text = '---\nname: valid\ndescription: valid\nmetadata:\n  version: 1.0.9\n---\n'
        self.assertEqual(validate_documents({'SKILL.md': text}), [])
        errors = validate_documents({'SKILL.md': text + '\n<a id="dup"></a>\n<a id="dup"></a>\n'})
        self.assertEqual(errors, ['SKILL.md: duplicate explicit anchors'])


if __name__ == '__main__':
    unittest.main()
