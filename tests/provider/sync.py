import sys
sys.path.insert(0, '..')
from settings import TOKEN
from everpad.provider.sync import SyncAgent
from everpad.provider.tools import get_db_session, get_note_store
from everpad.provider.models import (
    Note, Notebook, Tag, Resource, ACTION_CREATE, ACTION_CHANGE,
    ACTION_NONE, ACTION_DELETE,
)
from sqlalchemy.orm.exc import NoResultFound
from itertools import ifilter
from datetime import datetime
import unittest
import os


note_store = get_note_store(TOKEN)  # prevent reconecting


class FakeSyncThread(SyncAgent):
    def __init__(self):
        self.app = type('fake', (object,), {
            'log': self.log,
        })
        self.update_count = 0
        self.session = get_db_session()
        self.sq = self.session.query
        self.auth_token = TOKEN
        self.note_store = note_store
        if self._need_to_update():
            self.need_to_update = True
            self.all_notes = list(self._iter_all_notes())
        else:
            self.need_to_update = False
            self.all_notes = []

    def log(self, val):
        pass


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.sync = FakeSyncThread()
        self.session = self.sync.session
        self.sq = self.sync.session.query
        self.auth_token = self.sync.auth_token
        self.note_store = self.sync.note_store

    def test_local_notebooks(self):
        """Test sync local notebooks"""
        name = str(datetime.now())
        notebook = Notebook(
            name=name, action=ACTION_CREATE,
        )
        self.session.add(notebook)
        self.session.commit()
        self.sync.notebooks_local()
        self.assertEqual(notebook.action, ACTION_NONE)
        notebook_remote = self.note_store.getNotebook(self.auth_token, notebook.guid)
        self.assertEqual(notebook.name, notebook_remote.name)
        notebook.name += '*'
        notebook.action = ACTION_CHANGE
        self.sync.notebooks_local()
        self.assertEqual(notebook.action, ACTION_NONE)
        notebook_remote = self.note_store.getNotebook(self.auth_token, notebook.guid)
        self.assertEqual(notebook.name, notebook_remote.name)

    def test_local_tags(self):
        """Test sync local tags"""
        name = str(datetime.now())
        tag = Tag(
            name=name, action=ACTION_CREATE,
        )
        self.session.add(tag)
        self.session.commit()
        self.sync.tags_local()
        self.assertEqual(tag.action, ACTION_NONE)
        tag_remote = self.note_store.getTag(self.auth_token, tag.guid)
        self.assertEqual(tag.name, tag_remote.name)
        tag.name += '*'
        tag.action = ACTION_CHANGE
        self.sync.tags_local()
        self.assertEqual(tag.action, ACTION_NONE)
        tag_remote = self.note_store.getTag(self.auth_token, tag.guid)
        self.assertEqual(tag.name, tag_remote.name)

    def test_local_notes(self):
        """Test local notes sync"""
        remote_notebook = self.note_store.getDefaultNotebook(self.auth_token)
        notebook = Notebook(guid=remote_notebook.guid)
        notebook.from_api(remote_notebook)
        self.session.add(notebook)
        self.session.commit()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
        )
        self.session.add(note)
        self.session.commit()
        self.sync.notes_local()
        self.assertEqual(note.action, ACTION_NONE)
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, False, False, False,
        )
        self.assertEqual(notebook.guid, note_remote.notebookGuid)
        note.title += '*'
        note.action = ACTION_CHANGE
        self.sync.notes_local()
        self.assertEqual(note.action, ACTION_NONE)
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, False, False, False,
        )
        self.assertEqual(note.title, note_remote.title)
        note.action = ACTION_DELETE
        self.sync.notes_local()
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, False, False, False,
        )
        self.assertFalse(note_remote.active)
        with self.assertRaises(NoResultFound):
            self.sq(Note).filter(
                Note.guid == note_remote.guid,
            ).one()

    def test_local_resources(self):
        """Test local resources"""
        remote_notebook = self.note_store.getDefaultNotebook(self.auth_token)
        notebook = Notebook(guid=remote_notebook.guid)
        notebook.from_api(remote_notebook)
        self.session.add(notebook)
        self.session.commit()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
        )
        self.session.add(note)
        self.session.commit()
        path = os.path.join(os.path.dirname(__file__), '../test.png')
        res = Resource(
            note_id=note.id, file_name='test.png',
            file_path=path, mime='image/png',
            action=ACTION_CREATE,
        )
        self.session.add(res)
        self.session.commit()
        self.sync.notes_local()
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, True, False, False,
        )
        self.assertEqual('test.png', note_remote.resources[0].attributes.fileName)
        self.session.delete(res)
        self.session.commit()
        note.action = ACTION_CHANGE
        self.sync.notes_local()
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, True, False, False,
        )
        self.assertIsNone(note_remote.resources)


if __name__ == '__main__':
    unittest.main()