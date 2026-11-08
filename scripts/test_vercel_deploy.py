"""The committed Vercel archive must match the verified frontend source."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import vercel_deploy as deploy
from scripts import render_deploy as render


class FrontendArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.test')
        self.git('config', 'user.name', 'Release Test')
        (self.root / 'web').mkdir()
        self.source = self.root / 'web' / 'page.jsx'
        self.source.write_text('export default function Page() {}\n')
        (self.root / '.gitignore').write_text('web/out/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial frontend')
        root = patch.object(deploy, 'ROOT', self.root)
        root.start()
        self.addCleanup(root.stop)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def test_clean_committed_frontend_can_publish(self):
        deploy.require_committed_frontend()

    def test_render_requires_committed_backend_and_pins_local_head(self):
        with patch.object(render, 'ROOT', self.root):
            self.assertEqual(render.committed_release(), self.git('rev-parse', 'HEAD').strip())
            (self.root / 'demo').mkdir()
            (self.root / 'demo' / 'new_store.py').write_text('new backend source')
            with self.assertRaisesRegex(render.RenderError, 'Commit'):
                render.committed_release()

    def test_untracked_frontend_source_cannot_be_omitted_from_archive(self):
        (self.root / 'web' / 'NewComponent.jsx').write_text('export default null;\n')
        with self.assertRaisesRegex(SystemExit, 'Commit'):
            deploy.require_committed_frontend()

    def test_ignored_source_is_not_mistaken_for_committed_source(self):
        (self.root / '.gitignore').write_text('web/hidden.jsx\ndemo/hidden.py\n')
        self.git('add', '.gitignore')
        self.git('commit', '-qm', 'Ignore local source')
        (self.root / 'web' / 'hidden.jsx').write_text('export default null;')
        with self.assertRaisesRegex(SystemExit, 'ignored'):
            deploy.require_committed_frontend()
        with patch.object(render, 'ROOT', self.root):
            with self.assertRaisesRegex(render.RenderError, 'ignored'):
                render.committed_release()

    def test_tracked_staged_and_deleted_changes_cannot_publish(self):
        self.source.write_text('export default null;\n')
        with self.assertRaises(SystemExit):
            deploy.require_committed_frontend()
        self.git('add', 'web')
        with self.assertRaises(SystemExit):
            deploy.require_committed_frontend()
        self.source.unlink()
        with self.assertRaises(SystemExit):
            deploy.require_committed_frontend()

    def test_ignored_build_output_and_unrelated_work_do_not_block(self):
        (self.root / 'web' / 'out').mkdir()
        (self.root / 'web' / 'out' / 'index.html').write_text('built')
        (self.root / 'notes.txt').write_text('unrelated')
        deploy.require_committed_frontend()


if __name__ == '__main__':
    unittest.main()
