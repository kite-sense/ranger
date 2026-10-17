from __future__ import (absolute_import, division, print_function)

from io import open
import os

import pytest

from ranger.config.commands import rename
from ranger.container.file import File
from ranger.core.shared import FileManagerAware


class _StubDirectory(object):  # pylint: disable=too-few-public-methods

    def __init__(self, path):
        self.path = path
        self.pointed_obj = None


class _StubPathUpdater(object):  # pylint: disable=too-few-public-methods

    def update_path(self, path_old, path_new):
        pass


class _StubFM(object):  # pylint: disable=too-few-public-methods
    """Minimal ``fm`` substitute providing what ``rename`` touches."""

    def __init__(self, thisdir, thisfile):
        self.thisdir = thisdir
        self.thisfile = thisfile
        self.bookmarks = _StubPathUpdater()
        self.tags = _StubPathUpdater()
        self.messages = []

    def notify(self, text, bad=False):  # pylint: disable=unused-argument
        self.messages.append(text)

    def rename(self, src, dest):
        """Same as ``ranger.core.actions.Actions.rename``."""
        if hasattr(src, 'path'):
            src = src.path
        try:
            os.makedirs(os.path.dirname(dest))
        except OSError:
            pass
        try:
            os.rename(src, dest)
        except OSError as err:
            self.notify(err)
            return False
        return True


@pytest.fixture(name='tree')
def fixture_tree(tmpdir):
    """``a/``, ``b/`` (both with ``sub/``), ``s -> a`` and ``a/lb -> b``."""
    root = os.path.realpath(str(tmpdir))
    for subdir in ('a/sub', 'b/sub'):
        os.makedirs(os.path.join(root, subdir))
    os.symlink(os.path.join(root, 'a'), os.path.join(root, 's'))
    os.symlink(os.path.join(root, 'b'), os.path.join(root, 'a', 'lb'))
    cwd = os.getcwd()
    yield root
    os.chdir(cwd)


def _rename_in(directory, new_name):
    """Rename ``f`` inside ``directory`` the way ranger would after entering it.

    Like ``Tab.enter_dir``, chdir into the (possibly logical) path and keep
    that path in ``thisdir``.
    """
    with open(os.path.join(directory, 'f'), 'w', encoding='utf-8'):
        pass
    os.chdir(directory)
    fm = _StubFM(_StubDirectory(directory),
                 File(os.path.join(directory, 'f'), path_is_abs=True))
    FileManagerAware.fm = fm
    command = rename('rename ' + new_name)
    command.fm = fm
    command.execute()
    return fm


def test_rename_plain_dir(tree):
    fm = _rename_in(os.path.join(tree, 'b'), 'x')
    assert os.path.isfile(os.path.join(tree, 'b', 'x'))
    assert fm.thisfile.path == os.path.join(tree, 'b', 'x')
    assert fm.thisdir.pointed_obj is fm.thisfile


def test_rename_under_symlink(tree):
    """Regression test for #3175."""
    fm = _rename_in(os.path.join(tree, 's'), 'x')
    assert os.path.isfile(os.path.join(tree, 'a', 'x'))
    assert fm.thisfile.path == os.path.join(tree, 's', 'x')
    assert fm.thisdir.pointed_obj is fm.thisfile


def test_rename_absolute_physical_under_symlink(tree):
    fm = _rename_in(os.path.join(tree, 's'), os.path.join(tree, 'a', 'x'))
    assert os.path.isfile(os.path.join(tree, 'a', 'x'))
    assert fm.thisfile.path == os.path.join(tree, 's', 'x')


def test_rename_parent_under_nested_symlink(tree):
    """``..`` is resolved physically, like ``mv f ../x`` in a shell."""
    fm = _rename_in(os.path.join(tree, 'a', 'lb'), '../x')
    assert os.path.isfile(os.path.join(tree, 'x'))
    assert not os.path.lexists(os.path.join(tree, 'a', 'x'))
    assert fm.thisfile.path == os.path.join(tree, 'x')


def test_rename_into_subdir(tree):
    fm = _rename_in(os.path.join(tree, 's'), 'sub/x')
    assert os.path.isfile(os.path.join(tree, 'a', 'sub', 'x'))
    assert fm.thisfile.path == os.path.join(tree, 'a', 'sub', 'x')


def test_rename_existing_target(tree):
    with open(os.path.join(tree, 'b', 'x'), 'w', encoding='utf-8'):
        pass
    fm = _rename_in(os.path.join(tree, 'b'), 'x')
    assert fm.messages == ["Can't rename: file already exists!"]
    assert os.path.isfile(os.path.join(tree, 'b', 'f'))
    assert fm.thisfile.path == os.path.join(tree, 'b', 'f')
