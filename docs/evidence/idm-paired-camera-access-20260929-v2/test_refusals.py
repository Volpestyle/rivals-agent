"""Synthetic boundary checks only; never call the audit's main()."""
import hashlib
import json
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

import audit


class BoundaryTests(unittest.TestCase):
    def test_independent_identity_refusals(self):
        source = ('fake-live', PureWindowsPath('C:/FAKE/clip.mkv'), 'a' * 64)
        control = {'session_id': 'other', 'media_path': 'C:/fake/other.mkv', 'media_sha256': 'b' * 64}
        audit.refuse_sealed((source,), [control])
        for field, value in (
            ('session_id', 'fake-live'), ('session_group', 'fake-live'),
            ('media_sha256', 'a' * 64), ('media_path', 'c:/fake/clip.mkv'),
            ('media_path', 'c:\\fake\\clip.mkv'),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(RuntimeError, 'sealed source'):
                    audit.refuse_sealed((source,), [dict(control, **{field: value})])

    def test_authenticated_loader_single_read_and_crlf(self):
        doc = {'schema_version': 1, 'sessions': [
            {'session_id': 'fake-sealed', 'media_sha256': 'b' * 64}]}
        lf = (json.dumps(doc, indent=2) + '\n').encode('utf-8')
        pin = hashlib.sha256(lf).hexdigest()
        with patch.object(Path, 'read_bytes', return_value=lf.replace(b'\n', b'\r\n')) as read:
            self.assertEqual(audit.I.load_denylist(Path('fake'), sha256_pin=pin), doc)
            read.assert_called_once()
        with patch.object(Path, 'read_bytes', return_value=lf):
            with self.assertRaises(audit.H.DemoError):
                audit.I.load_denylist(Path('fake'), sha256_pin='0' * 64)

    def test_authenticated_bad_row_refused(self):
        raw = json.dumps({'schema_version': 1, 'sessions': [{'session_id': 'fake'}]}).encode()
        with patch.object(Path, 'read_bytes', return_value=raw):
            with self.assertRaises(audit.H.DemoError):
                audit.I.load_denylist(Path('fake'), sha256_pin=hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    unittest.main()
