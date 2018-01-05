from __future__ import absolute_import, unicode_literals

from future import standard_library
from pkg_resources import resource_filename

from dulwich.repo import Repo
from dulwich import porcelain
from dulwich.diff_tree import tree_changes, CHANGE_DELETE, CHANGE_ADD, CHANGE_MODIFY

import os
import shutil

from pyload.__about__ import __package__
from pyload.core.manager.base import BaseManager

standard_library.install_aliases()


class UpdateManager(BaseManager):

    plugin_repo = 'https://github.com/pyload/pyload-plugins.git'
    plugin_folder = 'core/plugin'

    HEAD = b'HEAD'

    def setup(self):
        self.repo_folder = resource_filename(__package__, 'core/plugin')
        self.repo = self.init_plugin_repo()

        self.update()

    def init_plugin_repo(self):
        self.pyload.log.info(self._('Initialising plugin repository.'))
        if os.path.exists(os.path.join(self.repo_folder, '.git')):
            return Repo(self.repo_folder)

        if os.path.exists(self.repo_folder):
            shutil.rmtree(self.repo_folder)

        self.pyload.log.info(self._('Cloning plugin repository'))
        return porcelain.clone(self.plugin_repo, self.repo_folder)

    def update(self):
        self.pyload.log.info(self._('Update plugin repository'))
        prev = self.repo.head()

        # builds new tree from index, but does not do any deletes.
        # see: https://github.com/jelmer/dulwich/issues/452
        # and https://github.com/jelmer/dulwich/issues/588
        porcelain.pull(self.repo, self.plugin_repo)

        prev_commit = self.repo.get_object(prev)
        last_commit = self.repo.get_object(self.repo.head())

        self.check_changes(prev_commit, last_commit)

    def check_changes(self, prev_commit, last_commit):
        delta = tree_changes(self.repo, prev_commit.tree, last_commit.tree)
        for tree_change in delta:
            if tree_change.type == CHANGE_MODIFY:
                self.pyload.log.info(self._('Modified plugin {}'.format(tree_change.old.path)))
            elif tree_change.type == CHANGE_ADD:
                self.pyload.log.info(self._('Added plugin {}'.format(tree_change.old.path)))
            elif tree_change.type == CHANGE_DELETE:
                self.pyload.log.info(self._('Deleted plugin {}'.format(tree_change.old.path)))
                delete_path = os.path.join(self.repo.path, tree_change.old.path.decode())
                if os.path.exists(delete_path):
                    os.remove(delete_path)


